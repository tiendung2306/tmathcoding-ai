import { useMemo, useState } from 'react';
import { useLoaderData } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Clock3 } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Card } from '../components/ui/card';
import { ErrorPanel } from '../components/ErrorPanel';
import { SubmissionDetailModal } from '../components/SubmissionDetailModal';
import { fetchContestLiveSubmissions } from '../services/api';
import type { ContestLiveSubmissionData, TeacherContestData } from '../types';

const dateTime = new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh',
});

export function ContestRoomPage() {
  const contest = useLoaderData() as TeacherContestData;
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null);
  const submissionsQuery = useQuery({
    queryKey: ['contest-live-submissions', contest.contest_id],
    queryFn: ({ signal }) => fetchContestLiveSubmissions(contest.contest_id, signal),
    refetchInterval: query => query.state.data?.is_active ? 5_000 : contest.status === 'active' ? 5_000 : false,
    refetchIntervalInBackground: false,
  });
  const submissions = useMemo(() => (submissionsQuery.data?.events || [])
    .flatMap(event => event.record ? [event.record] : [])
    .sort((left, right) => right.date.localeCompare(left.date)), [submissionsQuery.data]);
  const acceptedCount = submissions.filter(item => item.result === 'AC').length;
  const statusLabel = contest.status === 'active' ? 'Đang diễn ra'
    : contest.status === 'upcoming' ? 'Sắp diễn ra' : 'Đã kết thúc';

  return <section className="mx-auto max-w-7xl space-y-6 p-3.5 sm:p-5 lg:p-6">
    <header className="rounded-xl border border-border bg-card p-5 shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary sm:text-2xl">{contest.title}</h1>
          <p className="mt-1 text-sm text-text-secondary">Mã cuộc thi: {contest.code}</p>
        </div>
        <Badge variant={contest.status === 'active' ? 'ac' : 'outline'}>{statusLabel}</Badge>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-text-secondary">
        <span>Bắt đầu: {dateTime.format(new Date(contest.starts_at))}</span>
        <span>Kết thúc: {dateTime.format(new Date(contest.ends_at))}</span>
      </div>
      {contest.status === 'active' && <p className="mt-3 flex items-center gap-2 text-sm font-medium text-red-700">
        <Clock3 aria-hidden className="h-4 w-4" />Đang thu nhận bài nộp
      </p>}
    </header>

    {submissionsQuery.error && <ErrorPanel title="Không tải được bài nộp" message="Hãy thử tải lại dữ liệu cuộc thi." onRetry={() => { void submissionsQuery.refetch(); }} />}

    <section aria-label="Thống kê bài nộp" className="grid gap-3 sm:grid-cols-2">
      <Card className="p-4">
        <p className="text-sm text-text-secondary">Tổng bài nộp</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums text-text-primary">{submissions.length}</p>
      </Card>
      <Card className="p-4">
        <p className="text-sm text-text-secondary">Bài được chấp nhận</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums text-text-primary">{acceptedCount}</p>
      </Card>
    </section>

    <section aria-label="Bài nộp cuộc thi" className="space-y-3">
      <div className="flex items-center gap-4 border-b border-border pb-2">
        <h2 className="text-base font-semibold text-text-primary">Bài nộp</h2>
        {submissionsQuery.data?.is_active && <span className="text-xs text-text-secondary">Cập nhật trực tiếp</span>}
      </div>
      {submissionsQuery.isPending ? <p role="status" className="py-4 text-sm text-text-secondary">Đang tải bài nộp...</p>
        : submissionsQuery.error ? null
          : submissions.length ? <div className="space-y-3">
            {submissions.map((submission: ContestLiveSubmissionData) => <Card key={submission.id} className={`flex flex-col gap-3 border-l-4 p-4 sm:flex-row sm:items-center sm:justify-between ${submission.result === 'AC' ? 'border-l-emerald-500' : 'border-l-slate-300'}`}>
              <div className="min-w-0">
                <p className="font-semibold text-text-primary">{submission.problem_name}</p>
                <p className="mt-1 text-sm text-text-secondary">
                  <span className="font-medium text-text-primary">{submission.user_name}</span>
                  <span className="mx-2" aria-hidden="true">·</span>
                  {dateTime.format(new Date(submission.date))}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <div className="text-right">
                  <p className="font-mono text-sm font-semibold text-text-primary">{submission.points} điểm</p>
                  <p className="text-xs text-text-secondary">{submission.result}</p>
                </div>
                <button type="button" onClick={() => setSelectedSubmissionId(submission.id)} className="min-h-11 rounded-md border border-border-control px-3 text-sm font-medium text-text-primary hover:bg-card-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
                  Đánh giá
                </button>
              </div>
            </Card>)}
          </div>
          : <Card className="p-8 text-center text-sm text-text-secondary">
            {submissionsQuery.data?.is_active ? 'Chưa có bài nộp. Bài của học sinh sẽ xuất hiện ở đây.'
              : contest.status === 'upcoming' ? 'Cuộc thi chưa bắt đầu.' : 'Không có bài nộp trong cuộc thi này.'}
          </Card>}
    </section>

    <SubmissionDetailModal submissionId={selectedSubmissionId} isOpen={selectedSubmissionId !== null} onClose={() => setSelectedSubmissionId(null)} />
  </section>;
}
