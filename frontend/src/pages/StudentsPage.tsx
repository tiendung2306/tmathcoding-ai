import { Link, useLoaderData, useSearchParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Search } from 'lucide-react';
import { getVisiblePageNumbers, PaginationBar } from '../components/PaginationBar';

interface StudentItem {
  user_id: number;
  name: string;
  username: string;
  points: number;
  problem_count: number;
  avatar_url: string | null;
  rank: number;
}

export interface StudentPageData {
  items: StudentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function StudentsPage() {
  const data = useLoaderData() as StudentPageData;
  const [params, setParams] = useSearchParams();
  const query = params.get('q') || '';
  const [search, setSearch] = useState(query);

  useEffect(() => { setSearch(query); }, [query]);
  useEffect(() => {
    if (search.trim() === query) return;
    const timer = window.setTimeout(() => {
      setParams(previous => {
        const next = new URLSearchParams(previous);
        if (search.trim()) next.set('q', search.trim()); else next.delete('q');
        next.delete('page');
        return next;
      }, { replace: true, preventScrollReset: true });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search, query, setParams]);

  const goToPage = (page: number) => {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (page === 1) next.delete('page'); else next.set('page', String(page));
      return next;
    });
  };

  const applySearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (search.trim()) next.set('q', search.trim()); else next.delete('q');
      next.delete('page');
      return next;
    }, { preventScrollReset: true });
  };

  return <section className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h1 className="text-2xl font-semibold text-text-primary">Học sinh</h1>
      <form onSubmit={applySearch} className="flex min-w-0 gap-2 sm:w-[22rem]">
        <label htmlFor="student-list-search" className="sr-only">Tìm học sinh</label>
        <input id="student-list-search" type="search" value={search} maxLength={128}
          onChange={event => setSearch(event.target.value)} placeholder="Tìm tên hoặc tài khoản"
          className="h-11 min-w-0 flex-1 rounded-md border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:h-9" />
        <button type="submit" className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md bg-brand-primary px-3 text-sm font-medium text-white hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 sm:h-9">
          <Search aria-hidden className="h-4 w-4" />Tìm kiếm
        </button>
      </form>
    </div>
    <div className="overflow-x-auto rounded-md border border-border bg-card">
      <table className="w-full table-fixed text-left text-sm">
        <caption className="sr-only">Xếp hạng học sinh theo điểm</caption>
        <thead className="bg-card-subtle text-text-secondary"><tr>
          <th scope="col" className="w-20 px-3 py-3 text-center font-medium">Hạng</th>
          <th scope="col" className="pl-5 pr-3 py-3 font-medium">Học sinh</th>
          <th scope="col" aria-sort="descending" className="w-24 px-3 py-3 text-right font-medium">Điểm</th>
        </tr></thead>
        <tbody className="divide-y divide-border">
          {data.items.map(student => <tr key={student.user_id} className="hover:bg-card-hover">
            <td className="px-3 text-center tabular-nums text-text-secondary">{student.rank}</td>
            <th scope="row" className="pl-5 pr-3 py-1.5 font-normal">
              <Link to={`/student/students/${student.user_id}`} className="flex min-h-11 min-w-0 items-center gap-3 rounded-sm text-left text-text-primary hover:text-brand-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
                <StudentAvatar url={student.avatar_url} name={student.name} />
                <span className="min-w-0">
                  <span className="block truncate font-medium">{student.name}</span>
                  <span className="block truncate text-xs text-text-secondary">@{student.username}</span>
                </span>
              </Link>
            </th>
            <td className="px-3 text-right tabular-nums text-text-secondary">{Math.round(student.points)}</td>
          </tr>)}
          {data.items.length === 0 && <tr><td colSpan={3} className="px-3 py-12 text-center text-text-secondary">{query ? 'Không tìm thấy học sinh phù hợp' : 'Chưa có học sinh'}</td></tr>}
        </tbody>
      </table>
    </div>
    {data.total_pages > 1 && <PaginationBar
      label="Phân trang học sinh"
      page={data.page}
      totalPages={data.total_pages}
      visiblePages={getVisiblePageNumbers(data.page, data.total_pages)}
      canGoPrevious={data.page > 1}
      canGoNext={data.page < data.total_pages}
      onPage={goToPage}
      onPrevious={() => goToPage(data.page - 1)}
      onNext={() => goToPage(data.page + 1)}
    />}
  </section>;
}

function StudentAvatar({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  const initial = [...name.trim()][0]?.toLocaleUpperCase('vi') || '?';

  return <span aria-hidden="true" className="grid size-9 shrink-0 place-items-center overflow-hidden rounded-full bg-card-subtle text-sm font-semibold text-text-secondary">
    {url && !failed
      ? <img src={url} alt="" loading="lazy" className="size-full object-cover" onError={() => setFailed(true)} />
      : initial}
  </span>;
}
