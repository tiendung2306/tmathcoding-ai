import { useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Hourglass, Search } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { ErrorPanel } from '../components/ErrorPanel';
import { Countdown } from '../components/Countdown';
import { PaginationBar } from '../components/PaginationBar';
import { fetchContestOrganizations, fetchTeacherContests } from '../services/api';
import type { TeacherContestData } from '../types';

const dateTime = new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh',
});

function ContestCard({
  contest,
  organizationNames,
}: {
  contest: TeacherContestData;
  organizationNames: Map<number, string>;
}) {
  const location = useLocation();
  const cardTone = contest.status === 'active'
    ? 'border-l-emerald-600'
    : contest.status === 'upcoming' ? 'border-l-amber-500' : 'border-l-slate-300';
  const organizations = contest.class_ids
    .map(id => organizationNames.get(id) || `Lớp ${id}`)
    .join(', ');

  return <Link to={`/teacher/contests/${contest.contest_id}`} state={{ from: location.pathname + location.search }} aria-label={`Mở phòng cuộc thi ${contest.title}`} className={`contest-card flex min-h-[180px] min-w-0 cursor-pointer flex-col gap-3.5 rounded-lg border border-border border-l-[5px] ${cardTone} bg-card px-4 py-4 text-left shadow-xs transition-[box-shadow,transform,background-color] duration-150 hover:-translate-y-0.5 hover:bg-slate-50/60 hover:shadow-md focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:px-5 sm:py-5`}>
    <div className="min-w-0">
      <h3 className="truncate text-[21px] font-semibold leading-7 tracking-[-0.025em] text-text-primary">{contest.title}</h3>
      <p className="mt-0.5 truncate text-sm leading-5 text-text-secondary">{contest.code}</p>
      {organizations && <p className="mt-0.5 truncate text-sm leading-5 text-text-secondary">{organizations}</p>}
    </div>
    <div className="flex flex-1 flex-col">
      {contest.status === 'active'
        ? <p className="flex items-center gap-2 text-[15px] font-semibold leading-6 text-red-700">
          <Hourglass aria-hidden className="h-[18px] w-[18px] shrink-0" />
          <span>Kết thúc sau <Countdown target={contest.ends_at} /></span>
        </p>
        : contest.status === 'upcoming'
          ? <p className="flex items-center gap-2 text-[15px] font-semibold leading-6 text-amber-700">
            <Hourglass aria-hidden className="h-[18px] w-[18px] shrink-0" />
            <span>Bắt đầu sau <Countdown target={contest.starts_at} /></span>
          </p>
          : null}
      <dl className="mt-auto grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 border-t border-border pt-2.5 text-[13px] leading-5 text-text-secondary">
        <dt className="font-semibold text-text-primary">Bắt đầu</dt>
        <dd><time className="tabular-nums" dateTime={contest.starts_at}>{dateTime.format(new Date(contest.starts_at))}</time></dd>
        <dt className="font-semibold text-text-primary">Kết thúc</dt>
        <dd><time className="tabular-nums" dateTime={contest.ends_at}>{dateTime.format(new Date(contest.ends_at))}</time></dd>
      </dl>
    </div>
  </Link>;
}

function ContestSection({
  title,
  contests,
  organizationNames,
  loading,
}: {
  title: string;
  contests: TeacherContestData[];
  organizationNames: Map<number, string>;
  loading: boolean;
}) {
  return <section className="space-y-4" aria-label={title}>
    <div className="flex items-center gap-4 bg-card-subtle/70 px-3 py-2">
      <h2 className="shrink-0 text-sm font-semibold uppercase tracking-wide text-text-secondary">{title}</h2>
      <div className="h-px flex-1 bg-border" />
    </div>
    {loading ? <p role="status" className="py-3 text-sm text-text-secondary">Đang tải cuộc thi...</p>
      : contests.length ? <div className="grid gap-4 md:grid-cols-2">
        {contests.map(contest => <ContestCard key={contest.contest_id} contest={contest} organizationNames={organizationNames} />)}
      </div>
      : <p className="py-2 text-sm italic text-text-tertiary">Chưa có cuộc thi trong mục này.</p>}
  </section>;
}

export function ContestsPage() {
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [endedPage, setEndedPage] = useState(1);
  const cursorsByPage = useRef(new Map<number, string | null>([[1, null]]));
  const cursor = cursorsByPage.current.get(endedPage) ?? null;

  const organizations = useQuery({
    queryKey: ['contest-organizations'],
    queryFn: ({ signal }) => fetchContestOrganizations(signal),
  });
  const filters = { q: query || undefined };
  const active = useQuery({
    queryKey: ['teacher-contests', 'active', filters],
    queryFn: ({ signal }) => fetchTeacherContests({ ...filters, state: 'active', limit: 100 }, signal),
  });
  const upcoming = useQuery({
    queryKey: ['teacher-contests', 'upcoming', filters],
    queryFn: ({ signal }) => fetchTeacherContests({ ...filters, state: 'upcoming', limit: 100 }, signal),
  });
  const ended = useQuery({
    queryKey: ['teacher-contests', 'ended', filters, cursor],
    queryFn: ({ signal }) => fetchTeacherContests({ ...filters, state: 'ended', cursor, limit: 24 }, signal),
  });


  if (ended.data?.next_cursor && ended.data.has_more && !cursorsByPage.current.has(endedPage + 1)) {
    cursorsByPage.current.set(endedPage + 1, ended.data.next_cursor);
  }

  const organizationNames = useMemo(() => new Map(
    (organizations.data || []).map(item => [item.id, item.name]),
  ), [organizations.data]);
  const canGoNext = Boolean(ended.data?.has_more && ended.data.next_cursor);
  const visiblePages = [...new Set([
    1,
    ...[...cursorsByPage.current.keys()].filter(number => number >= Math.max(1, endedPage - 2) && number <= endedPage + 2),
    ...(canGoNext ? [endedPage + 1] : []),
  ])].sort((left, right) => left - right);
  const pageCountHint = Math.max(endedPage, canGoNext ? endedPage + 1 : endedPage);
  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    cursorsByPage.current = new Map([[1, null]]);
    setEndedPage(1);
    setQuery(searchInput.trim().slice(0, 128));
  };
  const goToEndedPage = (targetPage: number) => {
    if (cursorsByPage.current.has(targetPage)) setEndedPage(targetPage);
  };
  const goToNextEndedPage = () => {
    if (ended.data?.next_cursor && ended.data.has_more) {
      cursorsByPage.current.set(endedPage + 1, ended.data.next_cursor);
      setEndedPage(endedPage + 1);
    }
  };

  const error = active.error || upcoming.error || ended.error || organizations.error;

  return <section className="mx-auto max-w-7xl space-y-4 p-3.5 sm:p-5 lg:p-6">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h1 className="text-2xl font-semibold text-text-primary">Cuộc thi</h1>
      <form onSubmit={applyFilters} className="flex min-w-0 flex-col gap-2 sm:flex-row">
        <label htmlFor="contest-search" className="sr-only">Tìm theo tên hoặc mã cuộc thi</label>
        <input id="contest-search" type="search" maxLength={128} value={searchInput} onChange={event => setSearchInput(event.target.value)} placeholder="Nhập tên hoặc mã cuộc thi..." className="h-11 w-full rounded-md border border-border px-3 text-sm text-text-primary placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:h-9 sm:w-72" />
        <button type="submit" className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-brand-primary px-3 text-sm font-medium text-white hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 sm:h-9">
          <Search aria-hidden className="h-4 w-4" />Tìm kiếm
        </button>
      </form>
    </header>

    {error && <ErrorPanel title="Không tải được cuộc thi" message="Hãy thử tải lại danh sách." onRetry={() => { void Promise.all([active.refetch(), upcoming.refetch(), ended.refetch(), organizations.refetch()]); }} />}

    <div className="space-y-10">
      <ContestSection title="Cuộc thi đang diễn ra" contests={active.data?.items || []} organizationNames={organizationNames} loading={active.isPending} />
      {(upcoming.data?.items.length ?? 0) > 0 && <ContestSection title="Cuộc thi sắp diễn ra" contests={upcoming.data!.items} organizationNames={organizationNames} loading={false} />}
      <section className="space-y-4" aria-label="Cuộc thi đã qua">
        <div className="flex items-center gap-4 bg-card-subtle/70 px-3 py-2">
          <h2 className="shrink-0 text-sm font-semibold uppercase tracking-wide text-text-secondary">Cuộc thi đã qua</h2>
          <div className="h-px flex-1 bg-border" />
        </div>
        {ended.isPending ? <p role="status" className="py-3 text-sm text-text-secondary">Đang tải cuộc thi...</p>
          : ended.data?.items.length ? <div className="grid gap-4 md:grid-cols-2">
            {ended.data.items.map(contest => <ContestCard key={contest.contest_id} contest={contest} organizationNames={organizationNames} />)}
          </div>
          : <p className="py-2 text-sm italic text-text-tertiary">Chưa có cuộc thi nào đã kết thúc.</p>}
        {ended.data?.items.length && (endedPage > 1 || canGoNext) ? <PaginationBar
          label="Phân trang cuộc thi đã qua"
          page={endedPage}
          totalPages={pageCountHint}
          visiblePages={visiblePages}
          canGoPrevious={endedPage > 1 && cursorsByPage.current.has(endedPage - 1)}
          canGoNext={canGoNext}
          onPage={goToEndedPage}
          onPrevious={() => goToEndedPage(endedPage - 1)}
          onNext={goToNextEndedPage}
        /> : null}
      </section>
    </div>
  </section>;
}
