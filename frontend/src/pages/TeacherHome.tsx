import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Search, Trophy } from 'lucide-react';
import { ErrorPanel } from '../components/ErrorPanel';
import { fetchTeacherContests } from '../services/api';

const dateTime = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' });

function SectionHeader({ title, to, linkLabel }: { title: string; to: string; linkLabel: string }) {
  return <div className="flex items-center justify-between gap-3">
    <h2 className="text-base font-semibold text-text-primary">{title}</h2>
    <Link to={to} className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-brand-primary hover:underline sm:min-h-0">
      {linkLabel}<ArrowRight aria-hidden className="h-4 w-4" />
    </Link>
  </div>;
}

export function TeacherHome() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const active = useQuery({
    queryKey: ['teacher-contests', 'active', { q: undefined }],
    queryFn: ({ signal }) => fetchTeacherContests({ state: 'active', limit: 100 }, signal),
  });
  const upcoming = useQuery({
    queryKey: ['teacher-contests', 'upcoming', { q: undefined }],
    queryFn: ({ signal }) => fetchTeacherContests({ state: 'upcoming', limit: 5 }, signal),
  });
  const searchStudents = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const term = query.trim().slice(0, 128);
    navigate(term ? `/student/students?${new URLSearchParams({ q: term })}` : '/student/students');
  };
  const contests = [...(active.data?.items || []), ...(upcoming.data?.items || [])];

  return <section className="mx-auto max-w-7xl space-y-6 p-3.5 sm:p-5 lg:p-6">
    <header className="space-y-3">
      <h1 className="text-2xl font-semibold text-text-primary">Trang chủ</h1>
      <form onSubmit={searchStudents} role="search" className="flex max-w-xl gap-2">
        <label htmlFor="home-student-search" className="sr-only">Tìm học sinh</label>
        <input id="home-student-search" type="search" value={query} maxLength={128} onChange={event => setQuery(event.target.value)} placeholder="Tìm học sinh theo tên hoặc tài khoản…"
          className="h-11 min-w-0 flex-1 rounded-md border border-border bg-card px-3 text-sm placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary" />
        <button type="submit" className="inline-flex h-11 items-center gap-2 rounded-md bg-brand-primary px-4 text-sm font-medium text-white hover:bg-brand-primary-hover">
          <Search aria-hidden className="h-4 w-4" />Tìm
        </button>
      </form>
    </header>

    <section aria-label="Cuộc thi" className="max-w-3xl space-y-3">
      <SectionHeader title="Cuộc thi đang và sắp diễn ra" to="/teacher/contests" linkLabel="Tất cả cuộc thi" />
      {(active.error || upcoming.error) && <ErrorPanel title="Không tải được cuộc thi" message="Hãy thử lại." onRetry={() => { void Promise.all([active.refetch(), upcoming.refetch()]); }} />}
      {active.isPending || upcoming.isPending ? <p role="status" className="text-sm text-text-secondary">Đang tải…</p>
        : contests.length ? <ul className="space-y-2">
          {contests.map(contest => <li key={contest.contest_id}>
            <Link to={`/teacher/contests/${contest.contest_id}`} state={{ from: '/teacher/home' }} className={`flex items-center gap-3 rounded-lg border border-border border-l-4 bg-card px-4 py-3 hover:bg-card-subtle ${contest.status === 'active' ? 'border-l-emerald-600' : 'border-l-amber-500'}`}>
              <Trophy aria-hidden className="h-5 w-5 shrink-0 text-text-tertiary" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-text-primary">{contest.title}</span>
                <span className="block text-xs text-text-secondary">
                  {contest.status === 'active' ? `Đang diễn ra · kết thúc ${dateTime.format(new Date(contest.ends_at))}` : `Bắt đầu ${dateTime.format(new Date(contest.starts_at))}`}
                </span>
              </span>
            </Link>
          </li>)}
        </ul>
          : !(active.error || upcoming.error) && <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-text-secondary">Không có cuộc thi đang hoặc sắp diễn ra.</p>}
    </section>
  </section>;
}
