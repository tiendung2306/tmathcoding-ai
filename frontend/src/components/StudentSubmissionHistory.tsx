import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchStudentSubmissionHistory } from '../services/api';
import type { StudentSubmissionHistoryItemData } from '../types';
import { PaginationBar } from './PaginationBar';
import { SubmissionDetailModal } from './SubmissionDetailModal';
import { ErrorPanel } from './ErrorPanel';
import { SubmissionRow } from './SubmissionRow';

const dateFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

export function StudentSubmissionHistory({ studentId }: { studentId: number }) {
  const [params, setParams] = useSearchParams();
  const [modalSubmissionId, setModalSubmissionId] = useState<number | null>(null);
  const cursorsByPage = useRef(new Map<number, string | null>());
  const hasLegacyFilters = params.has('result') || params.has('period');
  const pageValue = Number(hasLegacyFilters ? '1' : params.get('page') || '1');
  const page = Number.isInteger(pageValue) && pageValue > 0 ? pageValue : 1;
  const cursor = hasLegacyFilters ? null : params.get('cursor');

  if (cursor !== null && !cursorsByPage.current.has(page)) cursorsByPage.current.set(page, cursor);
  if (page === 1) cursorsByPage.current.set(1, null);

  useEffect(() => {
    if (!hasLegacyFilters) return;
    cursorsByPage.current = new Map([[1, null]]);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      next.delete('result');
      next.delete('period');
      next.delete('page');
      next.delete('cursor');
      return next;
    }, { replace: true, preventScrollReset: true });
  }, [hasLegacyFilters, setParams]);

  const history = useQuery({
    queryKey: ['student', studentId, 'submission-history', cursor],
    queryFn: () => fetchStudentSubmissionHistory(studentId, cursor),
    enabled: !hasLegacyFilters,
  });
  const totalPages = history.data ? Math.max(1, Math.ceil(history.data.total / history.data.page_size)) : 1;
  const canGoBack = page > 1 && cursorsByPage.current.has(page - 1);
  const canGoNext = Boolean(history.data?.has_more && history.data.next_cursor);
  const visiblePages = [...new Set([
    1,
    ...[...cursorsByPage.current.keys()].filter(value => value >= Math.max(1, page - 2) && value <= page + 2),
    ...(canGoNext ? [page + 1] : []),
    ...(cursorsByPage.current.has(totalPages) ? [totalPages] : []),
  ])].sort((a, b) => a - b);

  const goToNextPage = () => {
    if (!history.data?.has_more || !history.data.next_cursor) return;
    const nextPage = page + 1;
    cursorsByPage.current.set(nextPage, history.data.next_cursor);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      next.set('page', String(nextPage));
      next.set('cursor', history.data!.next_cursor!);
      return next;
    }, { preventScrollReset: true });
  };

  const goToPreviousPage = () => {
    if (!canGoBack) return;
    const previousPage = page - 1;
    const previousCursor = cursorsByPage.current.get(previousPage);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (previousPage === 1) {
        next.delete('page');
        next.delete('cursor');
      } else {
        next.set('page', String(previousPage));
        if (previousCursor) next.set('cursor', previousCursor); else next.delete('cursor');
      }
      return next;
    }, { preventScrollReset: true });
  };

  const goToPage = (targetPage: number) => {
    if (!cursorsByPage.current.has(targetPage)) return;
    const targetCursor = cursorsByPage.current.get(targetPage);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (targetPage === 1) {
        next.delete('page');
        next.delete('cursor');
      } else {
        next.set('page', String(targetPage));
        if (targetCursor) next.set('cursor', targetCursor); else next.delete('cursor');
      }
      return next;
    }, { preventScrollReset: true });
  };

  const openDetail = (submissionId: number) => setModalSubmissionId(submissionId);

  return <section className="grid gap-4" aria-label="Lịch sử bài nộp">
    <div className="min-w-0 overflow-hidden rounded-lg border border-border bg-card shadow-xs">
      <div className="flex items-end justify-between gap-3 border-b border-border px-4 py-4 sm:px-5">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Lời giải gần đây</h3>
        </div>
      </div>
      {history.isPending ? <div className="space-y-3 p-4" role="status" aria-busy="true">
        <p className="text-sm text-text-secondary">Đang tải lịch sử bài nộp...</p>
        {[1, 2, 3].map(row => <div key={row} className="h-24 animate-pulse rounded-md bg-card-subtle" />)}
      </div> : history.isError ? <div className="p-4">
        <ErrorPanel title="Không tải được lịch sử bài nộp" message="Hãy thử tải lại danh sách." onRetry={() => { void history.refetch({ cancelRefetch: false }); }} />
      </div> : history.data.items.length === 0 ? <div className="px-4 py-12 text-center">
        <p className="text-sm font-medium text-text-primary">Chưa có bài nộp</p>
        <p className="mt-1 text-xs text-text-secondary">Lịch sử bài nộp của học sinh sẽ xuất hiện tại đây.</p>
      </div> : <div className="divide-y divide-border">
        {history.data.items.map(item => <SubmissionRow key={item.submission_id}
          points={item.points} result={item.result || item.status} language={item.language}
          name={item.problem_name}
          meta={<time dateTime={item.date} title={formatDate(item.date)}>{formatRelativeDate(item.date)}</time>}
          time={item.time} memory={item.memory} onOpen={() => openDetail(item.submission_id)} />)}
      </div>}
    </div>

    {history.data && history.data.total > history.data.page_size && <PaginationBar
      label="Phân trang bài nộp"
      page={page}
      totalPages={totalPages}
      visiblePages={visiblePages}
      canGoPrevious={canGoBack}
      canGoNext={canGoNext}
      onPage={goToPage}
      onPrevious={goToPreviousPage}
      onNext={goToNextPage}
    />}

    <SubmissionDetailModal
      submissionId={modalSubmissionId}
      isOpen={modalSubmissionId !== null}
      onClose={() => setModalSubmissionId(null)}
      initialTab="problem"
    />
  </section>;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

function formatRelativeDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86_400_000));
  if (days === 0) return 'Hôm nay';
  if (days === 1) return '1 ngày trước';
  if (days < 30) return `${days} ngày trước`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} tháng trước`;
  return `${Math.floor(months / 12)} năm trước`;
}
