import { lazy, Suspense, useCallback, useDeferredValue, useMemo, useState } from 'react';
import { useLoaderData, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Card } from '../components/ui/card';
import { BackLink } from '../components/BackNavigation';
import { ErrorPanel } from '../components/ErrorPanel';
import { SubmissionRow } from '../components/SubmissionRow';
import { Countdown } from '../components/Countdown';
import { fetchContestLiveSubmissions, fetchContestStudents } from '../services/api';
import { buildStandings, contestPollInterval, filterSubmissions, formatElapsed, formatScore, normalizeText, type ResultFilter, type StandingCell } from '../lib/contestRoom';
import type { ContestLiveSubmissionData, TeacherContestData } from '../types';

// The detail modal pulls in Markdown, KaTeX and code highlighting; load it on first use.
const SubmissionDetailModal = lazy(() => import('../components/SubmissionDetailModal')
  .then(module => ({ default: module.SubmissionDetailModal })));

const timeOnly = new Intl.DateTimeFormat('vi-VN', { timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' });
const PAGE_SIZE = 50;
const RESULT_FILTERS: { value: ResultFilter; label: string }[] = [
  { value: 'all', label: 'Tất cả' },
  { value: 'ac', label: 'Đạt (AC)' },
  { value: 'failed', label: 'Chưa đạt' },
];
type Tab = 'progress' | 'submissions';

function statusOf(contest: TeacherContestData, serverActive: boolean | undefined, now: number) {
  if (serverActive) return 'active';
  if (now < Date.parse(contest.starts_at)) return 'upcoming';
  if (now <= Date.parse(contest.ends_at)) return 'active';
  return 'ended';
}

function StandingCellButton({ cell, label, onOpen }: { cell: StandingCell; label: string; onOpen: (id: number) => void }) {
  const tone = cell.full ? 'text-emerald-700' : cell.score > 0 ? 'text-amber-700' : 'text-red-600';
  return <button type="button" onClick={() => onOpen(cell.submissionId)}
    aria-label={`${label}: ${formatScore(cell.score)} điểm lúc ${formatElapsed(cell.seconds)}, ${cell.attempts} lượt nộp${cell.firstSolve ? ', giải đầu tiên' : ''}`}
    className="block min-h-12 w-full px-1.5 py-1.5 tabular-nums hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary">
    <span className={`block font-semibold leading-5 ${tone}`}>{formatScore(cell.score)}</span>
    <span className="block text-[11px] text-text-tertiary">{formatElapsed(cell.seconds)}</span>
  </button>;
}

function ChoiceChips<T extends string | number>({ label, options, value, onChange }: {
  label: string; options: { value: T; label: string }[]; value: T; onChange: (value: T) => void;
}) {
  return <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
    {options.map(option => <button key={String(option.value)} type="button" role="radio" aria-checked={value === option.value} onClick={() => onChange(option.value)}
      className={`min-h-11 rounded-md border px-3 text-sm font-medium sm:min-h-9 ${value === option.value ? 'border-brand-primary/40 bg-brand-primary/10 text-brand-primary' : 'border-border bg-card text-text-secondary hover:text-text-primary'}`}>
      {option.label}
    </button>)}
  </div>;
}

export function ContestRoomPage() {
  const contest = useLoaderData() as TeacherContestData;
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get('tab') === 'submissions' ? 'submissions' : 'progress';
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null);
  const [resultFilter, setResultFilter] = useState<ResultFilter>('all');
  const [search, setSearch] = useState(params.get('q') || '');
  const deferredSearch = useDeferredValue(search);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const updateParams = (changes: Record<string, string | null>) => setParams(previous => {
    const next = new URLSearchParams(previous);
    for (const [key, value] of Object.entries(changes)) if (value) next.set(key, value); else next.delete(key);
    return next;
  }, { replace: true, preventScrollReset: true });

  const submissionsQuery = useQuery({
    queryKey: ['contest-live-submissions', contest.contest_id],
    queryFn: ({ signal }) => fetchContestLiveSubmissions(contest.contest_id, null, signal),
    refetchInterval: query => contestPollInterval(contest, query.state.data?.is_active),
    refetchIntervalInBackground: false,
  });
  const rosterQuery = useQuery({
    queryKey: ['contest-students', contest.contest_id],
    queryFn: ({ signal }) => fetchContestStudents(contest.contest_id, null, signal),
    staleTime: 60_000,
  });
  const refreshWhenStarted = useCallback(() => { void queryClient.invalidateQueries({ queryKey: ['contest-live-submissions', contest.contest_id] }); }, [queryClient, contest.contest_id]);

  const submissions = useMemo(() => (submissionsQuery.data?.events || [])
    .flatMap(event => event.record ? [event.record] : [])
    .sort((left, right) => right.date.localeCompare(left.date)), [submissionsQuery.data]);
  const roster = rosterQuery.data || [];
  const progress = useMemo(() => buildStandings(submissions, roster, submissionsQuery.data?.problems, contest.starts_at),
    [submissions, roster, submissionsQuery.data?.problems, contest.starts_at]);
  const problemLabels = useMemo(() => new Map(progress.problems.map(problem => [problem.problem_id, problem.label])), [progress.problems]);
  const filtered = useMemo(() => filterSubmissions(submissions, resultFilter, deferredSearch),
    [submissions, resultFilter, deferredSearch]);
  const visibleRows = useMemo(() => {
    const term = normalizeText(deferredSearch);
    return term ? progress.rows.filter(row => normalizeText(`${row.user_name} ${row.username || ''}`).includes(term)) : progress.rows;
  }, [progress.rows, deferredSearch]);
  const shown = filtered.slice(0, visibleCount);
  const status = statusOf(contest, submissionsQuery.data?.is_active, Date.now());
  const statusLabel = status === 'active' ? 'Đang diễn ra' : status === 'upcoming' ? 'Sắp diễn ra' : 'Đã kết thúc';

  const showStudentSubmissions = (name: string) => {
    setSearch(name); setResultFilter('all'); setVisibleCount(PAGE_SIZE);
    updateParams({ tab: 'submissions', q: name });
  };
  const changeSearch = (value: string) => { setSearch(value); setVisibleCount(PAGE_SIZE); updateParams({ q: value.trim() || null }); };

  return <section className="mx-auto max-w-7xl space-y-5 p-3.5 sm:p-5 lg:p-6">
    <header className="grid grid-cols-[1fr_minmax(0,auto)_1fr] items-center gap-3">
      <div className="justify-self-start"><BackLink compact /></div>
      <h1 className="text-center text-lg font-bold tracking-tight text-text-primary [overflow-wrap:anywhere] sm:text-2xl">{contest.title}</h1>
      <div className="flex items-center justify-self-end gap-2 text-sm">
        {status === 'active' && <span className="hidden tabular-nums text-red-700 sm:inline">Còn <Countdown target={contest.ends_at} /></span>}
        {status === 'upcoming' && <span className="hidden tabular-nums text-amber-800 sm:inline">Bắt đầu sau <Countdown target={contest.starts_at} onElapsed={refreshWhenStarted} /></span>}
        <Badge variant={status === 'active' ? 'ac' : 'outline'} className="whitespace-nowrap font-sans text-xs">{statusLabel}</Badge>
      </div>
    </header>

    {submissionsQuery.error && <ErrorPanel title="Không tải được bài nộp" message="Hãy thử tải lại dữ liệu cuộc thi." onRetry={() => { void submissionsQuery.refetch(); }} />}

    <div className="flex flex-col gap-3 border-b border-border sm:flex-row sm:items-end sm:justify-between">
      <div role="tablist" aria-label="Nội dung cuộc thi" className="flex gap-1">
        {([['progress', 'Bảng xếp hạng'], ['submissions', 'Bài nộp']] as [Tab, string][]).map(([value, label]) =>
          <button key={value} type="button" role="tab" aria-selected={tab === value} onClick={() => updateParams({ tab: value === 'progress' ? null : value })}
            className={`-mb-px min-h-11 border-b-2 px-3 text-sm font-medium ${tab === value ? 'border-brand-primary text-brand-primary' : 'border-transparent text-text-secondary hover:text-text-primary'}`}>
            {label}
          </button>)}
      </div>
      <label className="relative mb-2 block sm:w-64">
        <span className="sr-only">{tab === 'progress' ? 'Tìm học sinh' : 'Tìm học sinh hoặc bài'}</span>
        <Search aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <input type="search" value={search} onChange={event => changeSearch(event.target.value)} placeholder={tab === 'progress' ? 'Tìm học sinh…' : 'Tìm học sinh hoặc bài…'}
          className="h-11 w-full rounded-md border border-border bg-card pl-8 pr-3 text-sm placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:h-9" />
      </label>
    </div>

    {submissionsQuery.isPending ? <p role="status" className="py-4 text-sm text-text-secondary">Đang tải dữ liệu cuộc thi...</p>
      : submissionsQuery.error ? null
        : tab === 'progress' ? <section aria-label="Bảng xếp hạng" className="space-y-3">
          {rosterQuery.error && <p role="alert" className="text-sm text-red-700">Không tải được danh sách học sinh; chỉ hiện học sinh đã nộp bài.</p>}
          {visibleRows.length ? <div className="overflow-x-auto rounded-lg border border-slate-800 bg-card">
            <table className="w-full min-w-max border-collapse text-sm">
              <thead className="bg-slate-800 text-white">
                <tr>
                  <th scope="col" className="w-14 px-2 py-2.5 text-center font-semibold">Hạng</th>
                  <th scope="col" className="sticky left-0 z-10 min-w-48 bg-slate-800 px-3 py-2.5 text-left font-semibold">Học sinh</th>
                  <th scope="col" className="w-24 border-l border-slate-600 px-2 py-2.5 text-center font-semibold">Điểm</th>
                  {progress.problems.map(problem => <th key={problem.problem_id} scope="col" title={`${problem.label}. ${problem.name}`} className="w-20 min-w-20 border-l border-slate-600 px-2 py-1.5 text-center">
                    <span className="block text-base font-semibold leading-6">{problem.label}</span>
                    {problem.points != null && <span className="mx-auto block w-10 border-t border-slate-500 pt-0.5 text-xs font-medium tabular-nums text-slate-200">{formatScore(problem.points)}</span>}
                  </th>)}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map(row => <tr key={row.user_id} className="border-t border-border bg-card even:bg-card-subtle">
                  <td className="px-2 py-2 text-center text-base tabular-nums text-text-primary">{row.rank ?? '–'}</td>
                  <th scope="row" className="sticky left-0 z-10 max-w-72 bg-inherit px-3 py-2 text-left font-normal">
                    <button type="button" onClick={() => showStudentSubmissions(row.user_name)} disabled={!row.submissions}
                      className="group block max-w-full text-left disabled:cursor-default">
                      {row.username && row.username !== row.user_name && <span className="block truncate text-xs text-text-tertiary">{row.username}</span>}
                      <span className="block truncate font-semibold text-text-primary group-enabled:group-hover:text-brand-primary group-enabled:group-hover:underline group-disabled:font-medium group-disabled:text-text-tertiary">{row.user_name}</span>
                    </button>
                  </th>
                  <td className="border-l border-border px-2 py-2 text-center tabular-nums">
                    <span className="block text-base font-bold leading-5 text-text-primary">{formatScore(row.total)}</span>
                    {row.submissions > 0 && <span className="block text-xs text-text-tertiary">{formatElapsed(row.seconds)}</span>}
                  </td>
                  {progress.problems.map(problem => {
                    const cell = row.cells[problem.problem_id];
                    return <td key={problem.problem_id} className={`border-l border-border p-0 text-center ${cell?.firstSolve ? 'bg-lime-200/80' : ''}`}>
                      {cell && <StandingCellButton cell={cell} label={`${row.user_name}, bài ${problem.label}`} onOpen={setSelectedSubmissionId} />}
                    </td>;
                  })}
                </tr>)}
              </tbody>
            </table>
          </div> : <Card className="p-8 text-center text-sm text-text-secondary">
            {search ? 'Không có học sinh khớp từ khóa.' : status === 'upcoming' ? 'Cuộc thi chưa bắt đầu. Trang sẽ tự cập nhật khi cuộc thi diễn ra.' : 'Chưa có học sinh trong cuộc thi này.'}
          </Card>}
        </section>
          : <section aria-label="Bài nộp" className="space-y-3">
            <ChoiceChips label="Lọc theo kết quả" options={RESULT_FILTERS} value={resultFilter} onChange={value => { setResultFilter(value); setVisibleCount(PAGE_SIZE); }} />
            {shown.length ? <>
              <p className="text-xs text-text-tertiary">Hiển thị {shown.length.toLocaleString('vi-VN')} / {filtered.length.toLocaleString('vi-VN')} bài nộp</p>
              <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card shadow-xs">
                {shown.map((submission: ContestLiveSubmissionData) => <SubmissionRow key={submission.id}
                  points={submission.score ?? submission.points} result={submission.result}
                  name={submission.problem_name}
                  title={<>{problemLabels.has(submission.problem_id) && <span className="mr-1.5 text-text-tertiary">{problemLabels.get(submission.problem_id)}.</span>}{submission.problem_name}</>}
                  meta={<><span className="font-medium text-text-primary">{submission.user_name}</span><span className="mx-1.5" aria-hidden="true">·</span><time dateTime={submission.date}>{timeOnly.format(new Date(submission.date))}</time></>}
                  time={submission.time} memory={submission.memory} onOpen={() => setSelectedSubmissionId(submission.id)} />)}
              </div>
              {filtered.length > shown.length && <button type="button" onClick={() => setVisibleCount(count => count + PAGE_SIZE)} className="min-h-11 w-full rounded-md border border-border bg-card text-sm font-medium text-text-primary hover:bg-card-subtle">
                Hiển thị thêm {Math.min(PAGE_SIZE, filtered.length - shown.length)} bài nộp
              </button>}
            </>
              : <Card className="p-8 text-center text-sm text-text-secondary">
                {submissions.length ? 'Không có bài nộp khớp bộ lọc.'
                  : status === 'active' ? 'Chưa có bài nộp. Bài của học sinh sẽ xuất hiện ở đây.'
                    : status === 'upcoming' ? 'Cuộc thi chưa bắt đầu. Trang sẽ tự cập nhật khi cuộc thi diễn ra.' : 'Không có bài nộp trong cuộc thi này.'}
              </Card>}
          </section>}

    {selectedSubmissionId !== null && <Suspense fallback={null}>
      <SubmissionDetailModal submissionId={selectedSubmissionId} isOpen onClose={() => setSelectedSubmissionId(null)} />
    </Suspense>}
  </section>;
}
