import { Link, useLoaderData, useLocation, useRouteLoaderData, useSearchParams } from 'react-router-dom';
import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Search, Star } from 'lucide-react';
import { getVisiblePageNumbers, PaginationBar } from '../components/PaginationBar';
import type { AuthAccount } from '../services/auth';

interface StudentItem {
  user_id: number;
  name: string;
  username: string;
  points: number;
  problem_count: number;
  avatar_url: string | null;
  rank: number | null;
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
  const account = useRouteLoaderData('app') as AuthAccount;
  const location = useLocation();
  const returnTo = location.pathname + location.search;
  const [params, setParams] = useSearchParams();
  const query = params.get('q') || '';
  const requestedSort = params.get('sort');
  const sort = requestedSort === 'name' || requestedSort === 'name_desc' || requestedSort === 'points_asc' ? requestedSort : 'points_desc';
  const sortingByName = sort === 'name' || sort === 'name_desc';
  const [search, setSearch] = useState(query);
  const storageKey = `tmath:student-stars:${account.id}`;
  const [starredIds, setStarredIds] = useState<number[]>(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(storageKey) || '[]');
      return Array.isArray(saved) ? saved.filter((id): id is number => Number.isSafeInteger(id) && id > 0) : [];
    } catch { return []; }
  });
  const starredSet = useMemo(() => new Set(starredIds), [starredIds]);
  const visibleStudents = useMemo(() => [...data.items].sort((a, b) => Number(starredSet.has(b.user_id)) - Number(starredSet.has(a.user_id))), [data.items, starredSet]);

  const toggleStar = (userId: number) => {
    setStarredIds(previous => {
      const next = previous.includes(userId) ? previous.filter(id => id !== userId) : [...previous, userId];
      try { window.localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Sorting still works for this visit. */ }
      return next;
    });
  };

  const changeSort = (field: 'name' | 'points') => {
    const value = field === 'name'
      ? sort === 'name' ? 'name_desc' : 'name'
      : sort === 'points_desc' ? 'points_asc' : 'points_desc';
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (value === 'points_desc') next.delete('sort'); else next.set('sort', value);
      next.delete('page');
      return next;
    }, { preventScrollReset: true });
  };

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
    <div className="flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-end sm:justify-between">
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
        <caption className="sr-only">Danh sách học sinh; học sinh đánh dấu sao được đưa lên đầu trang đang xem</caption>
        <thead className="border-b border-border bg-card-subtle text-text-secondary"><tr>
          <th scope="col" className="w-12 px-1 text-center font-medium"><span className="sr-only">Đánh dấu sao</span></th>
          <th scope="col" className="w-14 px-1 text-center font-medium sm:w-20">{sortingByName ? 'STT' : 'Hạng'}</th>
          <th scope="col" className="w-12 font-medium"><span className="sr-only">Ảnh đại diện</span></th>
          <th scope="col" aria-sort={sortingByName ? sort === 'name' ? 'ascending' : 'descending' : 'none'} className="p-0 font-medium">
            <button type="button" onClick={() => changeSort('name')} className={`flex min-h-11 w-full items-center gap-1 px-2 text-left transition-colors hover:bg-card-hover hover:text-brand-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary sm:pl-5 sm:pr-3 ${sortingByName ? 'font-semibold text-text-primary' : ''}`} aria-label={`Sắp xếp theo tên học sinh ${sort === 'name' ? 'giảm' : 'tăng'} dần`}>Tên truy cập <span aria-hidden>{sortingByName ? sort === 'name' ? '↑' : '↓' : ''}</span></button>
          </th>
          <th scope="col" aria-sort={!sortingByName ? sort === 'points_desc' ? 'descending' : 'ascending' : 'none'} className="w-20 p-0 text-right font-medium sm:w-28">
            <button type="button" onClick={() => changeSort('points')} className={`flex min-h-11 w-full items-center justify-end gap-1 px-2 text-right transition-colors hover:bg-card-hover hover:text-brand-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary sm:px-4 ${!sortingByName ? 'font-semibold text-text-primary' : ''}`} aria-label={`Sắp xếp theo điểm ${sort === 'points_desc' ? 'tăng' : 'giảm'} dần`}>Điểm <span aria-hidden>{!sortingByName ? sort === 'points_desc' ? '↓' : '↑' : ''}</span></button>
          </th>
        </tr></thead>
        <tbody className="divide-y divide-border">
          {visibleStudents.map(student => <tr key={student.user_id} className={`hover:bg-card-hover ${starredSet.has(student.user_id) ? 'bg-card-subtle/40' : ''}`}>
            <td className="px-1 text-center"><button type="button" onClick={() => toggleStar(student.user_id)} aria-pressed={starredSet.has(student.user_id)} aria-label={`${starredSet.has(student.user_id) ? 'Bỏ sao' : 'Đánh dấu sao'} ${student.name}`} title={starredSet.has(student.user_id) ? 'Bỏ đánh dấu sao' : 'Đưa lên đầu trang'} className="inline-flex size-11 items-center justify-center rounded-sm text-text-secondary hover:text-amber-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"><Star aria-hidden className={`size-4 ${starredSet.has(student.user_id) ? 'fill-amber-500 text-amber-600' : ''}`} /></button></td>
            <td className="px-1 text-center tabular-nums text-text-secondary">{sortingByName ? (data.page - 1) * data.page_size + data.items.findIndex(item => item.user_id === student.user_id) + 1 : student.rank ?? '—'}</td>
            <td className="py-1.5"><Link to={`/student/students/${student.user_id}`} state={{ from: returnTo }} aria-label={`Mở hồ sơ ${student.name}`} className="mx-auto flex size-11 items-center justify-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"><StudentAvatar url={student.avatar_url} name={student.name} /></Link></td>
            <th scope="row" className="px-2 py-1.5 font-normal sm:pl-5 sm:pr-3">
              <Link to={`/student/students/${student.user_id}`} state={{ from: returnTo }} className="flex min-h-11 min-w-0 items-center rounded-sm text-left text-text-primary hover:text-brand-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
                <span className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5 sm:flex-nowrap">
                  <span className="min-w-0 truncate font-medium">{student.name}</span>
                  <span className="min-w-0 truncate text-xs text-text-secondary">{student.name === String(student.user_id) ? '' : '@'}{student.username}</span>
                </span>
              </Link>
            </th>
            <td className="px-2 text-right font-semibold tabular-nums text-text-primary sm:px-4">{Math.round(student.points).toLocaleString('vi-VN')}</td>
          </tr>)}
          {data.items.length === 0 && <tr><td colSpan={5} className="px-3 py-12 text-center text-text-secondary">{query ? 'Không tìm thấy học sinh phù hợp' : 'Chưa có học sinh'}</td></tr>}
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
