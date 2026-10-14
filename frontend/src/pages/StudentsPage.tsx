import { Link, useLoaderData, useSearchParams } from 'react-router-dom';
import { useEffect, useState } from 'react';

interface StudentItem {
  user_id: number;
  name: string;
  username: string;
  points: number;
  problem_count: number;
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

  return <section className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-baseline gap-3">
        <h1 className="text-lg font-semibold text-text-primary">Học sinh</h1>
        <span className="text-xs tabular-nums text-text-secondary">{data.total} học sinh</span>
      </div>
      <div>
        <label htmlFor="student-list-search" className="sr-only">Tìm học sinh</label>
        <input id="student-list-search" type="search" value={search} maxLength={128}
          onChange={event => setSearch(event.target.value)} placeholder="Tìm tên, tài khoản hoặc mã"
          className="h-11 sm:h-9 w-full sm:w-72 rounded-md border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary" />
      </div>
    </div>
    <div className="overflow-x-auto rounded-md border border-border bg-card">
      <table className="w-full min-w-[540px] text-left text-sm">
        <thead className="bg-card-subtle text-text-secondary"><tr>
          <th scope="col" className="px-3 py-3 font-medium">Học sinh</th>
          <th scope="col" className="px-3 py-3 font-medium">Tài khoản</th>
          <th scope="col" className="px-3 py-3 text-right font-medium">Điểm</th>
          <th scope="col" className="px-3 py-3 text-right font-medium">Bài đã giải</th>
        </tr></thead>
        <tbody className="divide-y divide-border">
          {data.items.map(student => <tr key={student.user_id} className="hover:bg-card-hover">
            <td className="px-3"><Link to={`/student/students/${student.user_id}`} className="flex min-h-11 items-center font-medium text-text-primary hover:text-brand-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">{student.name} <span className="ml-2 text-xs font-normal text-text-secondary">#{student.user_id}</span></Link></td>
            <td className="px-3 text-text-secondary">{student.username}</td>
            <td className="px-3 text-right tabular-nums text-text-secondary">{student.points}</td>
            <td className="px-3 text-right tabular-nums text-text-secondary">{student.problem_count}</td>
          </tr>)}
          {data.items.length === 0 && <tr><td colSpan={4} className="px-3 py-12 text-center text-text-secondary">{query ? 'Không tìm thấy học sinh phù hợp' : 'Chưa có học sinh'}</td></tr>}
        </tbody>
      </table>
    </div>
    {data.total_pages > 1 && <nav aria-label="Phân trang học sinh" className="flex items-center justify-end gap-3 text-sm text-text-secondary">
      <button type="button" onClick={() => goToPage(data.page - 1)} disabled={data.page <= 1} className="min-h-11 px-3 disabled:opacity-40">Trước</button>
      <span className="tabular-nums">{data.page} / {data.total_pages}</span>
      <button type="button" onClick={() => goToPage(data.page + 1)} disabled={data.page >= data.total_pages} className="min-h-11 px-3 disabled:opacity-40">Sau</button>
    </nav>}
  </section>;
}
