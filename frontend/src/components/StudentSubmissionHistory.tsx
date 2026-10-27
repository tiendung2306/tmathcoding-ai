import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchStudentSubmissionHistory } from '../services/api';
import type { StudentSubmissionHistoryItemData } from '../types';
import { PaginationBar } from './PaginationBar';
import { SubmissionDetailModal } from './SubmissionDetailModal';
import { ErrorPanel } from './ErrorPanel';

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
        {history.data.items.map(item => {
          const tone = resultTone(item.result || item.status);
          return <button key={item.submission_id} type="button" onClick={() => openDetail(item.submission_id)} aria-label={`Xem bài nộp ${item.problem_name}, ${formatPoints(item.points)} điểm`} className="group flex w-full cursor-pointer items-center gap-3 p-3 text-left transition-colors hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary sm:gap-4 sm:px-5 sm:py-4">
            <span role="img" aria-label={`${formatPoints(item.points)} điểm, ${item.result || item.status || 'chưa rõ kết quả'}`} className={`flex h-[4.75rem] w-[4.75rem] shrink-0 flex-col items-center justify-center rounded-xl text-center ${tone.tile}`}>
              <strong className="max-w-full truncate px-1 text-base tabular-nums">{formatPoints(item.points)}</strong>
              <span className="mt-1 max-w-full truncate px-1 text-[10px] font-semibold uppercase tracking-wide">{item.result || item.status || '—'}{item.language ? ` · ${item.language}` : ''}</span>
            </span>
            <span className="min-w-0 flex-1">
              <span className="block max-w-full truncate text-sm font-semibold text-text-primary group-hover:text-brand-primary group-focus-visible:text-brand-primary sm:text-base">{item.problem_name}</span>
              <time className="mt-1 block text-xs text-text-secondary" dateTime={item.date} title={formatDate(item.date)}>{formatRelativeDate(item.date)}</time>
            </span>
            <span className="hidden shrink-0 text-right text-xs tabular-nums text-text-secondary sm:block">
              <strong className="block font-mono text-text-primary">{formatTime(item.time)}</strong>
              <span className="mt-1 block">{formatMemory(item.memory)}</span>
            </span>
          </button>;
        })}
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

function resultTone(result: string | null | undefined) {
  switch ((result || '').toUpperCase()) {
    case 'AC': return { tile: 'bg-emerald-500 text-white' };
    case 'WA': case 'RTE': case 'CE': case 'OLE': return { tile: 'bg-red-500 text-white' };
    case 'TLE': case 'MLE': case 'QU': return { tile: 'bg-amber-400 text-slate-900' };
    default: return { tile: 'bg-card-subtle text-text-secondary' };
  }
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

function formatPoints(value: number | null) {
  if (value === null) return '—';
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(value);
}

function formatTime(value: number | null) {
  return value === null ? '—' : `${value.toFixed(3)} giây`;
}

function formatMemory(value: number | null) {
  return value === null ? '—' : `${Math.round(value)} MB`;
}
