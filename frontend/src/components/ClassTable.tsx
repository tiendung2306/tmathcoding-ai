import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowUp, ChevronDown, Search, Star } from 'lucide-react';
import { ClassListQuery, ClassPageData, ClassSortField, ClassSummaryData } from '../types';
import { fetchTeacherClasses, setClassStar } from '../services/api';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';
import { ErrorPanel } from './ErrorPanel';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

interface ClassTableProps {
  query: ClassListQuery;
  onQueryChange: (query: ClassListQuery, options?: { replace?: boolean }) => void;
  classHref: (orgId: number) => string;
  initialData?: ClassPageData;
}

type ClassColumn = { label: string; right?: boolean; width: number } & (
  { field: ClassSortField; sortable?: true }
  | { field: 'school_year' | 'managers'; sortable: false }
);

const COLUMNS: ClassColumn[] = [
  { field: 'id', label: 'Mã lớp', width: 76 },
  { field: 'name', label: 'Tên lớp', width: 230 },
  { field: 'school_year', label: 'Năm học', sortable: false, width: 108 },
  { field: 'managers', label: 'Người quản lý', sortable: false, width: 210 },
  { field: 'member_count', label: 'Sĩ số', right: true, width: 72 },
  { field: 'creation_date', label: 'Ngày tạo', width: 126 },
  { field: 'last_session_at', label: 'Phiên học gần nhất', width: 190 },
];

const COLUMN_COUNT = COLUMNS.length + 1;

function ClassNameCell({ cls, classHref }: {
  cls: ClassSummaryData;
  classHref: ClassTableProps['classHref'];
}) {
  const nameRef = useRef<HTMLAnchorElement>(null);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    const button = nameRef.current;
    if (!button) return;
    const measure = () => setTruncated(button.scrollWidth > button.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(button);
    return () => observer.disconnect();
  }, [cls.name]);

  return (
    <Tooltip open={truncated ? undefined : false}>
      <TooltipTrigger asChild>
        <Link
          ref={nameRef} to={classHref(cls.id)}
          className="block w-full truncate py-3 text-left font-medium text-text-primary hover:text-brand-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded-sm"
        >{cls.name}</Link>
      </TooltipTrigger>
      <TooltipContent side="top" align="start" className="max-w-[min(24rem,calc(100vw-2rem))] whitespace-normal break-words text-xs leading-relaxed">
        {cls.name}
      </TooltipContent>
    </Tooltip>
  );
}

const dateFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh',
});
const timeFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  timeZone: 'Asia/Ho_Chi_Minh',
});

function formatDate(value: string | null, includeTime = false): string {
  if (!value) return '';
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
  return (includeTime ? timeFormatter : dateFormatter).format(date);
}

export const ClassTable: React.FC<ClassTableProps> = ({ query, onQueryChange, classHref, initialData }) => {
  const [searchInput, setSearchInput] = useState(query.q);
  const [data, setData] = useState<ClassPageData | null>(initialData || null);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const consumedRetry = useRef(0);
  const [savingStar, setSavingStar] = useState<number | null>(null);
  const [starError, setStarError] = useState<string | null>(null);
  const latestQuery = useRef(query);
  const mounted = useRef(true);
  latestQuery.current = query;

  useEffect(() => { setSearchInput(query.q); }, [query.q]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const q = searchInput.trim();
    if (q === query.q) return;
    const timer = setTimeout(() => onQueryChange({ ...query, q, page: 1 }), 300);
    return () => clearTimeout(timer);
  }, [searchInput, query, onQueryChange]);

  useEffect(() => {
    if (initialData && retry === consumedRetry.current) {
      setData(initialData); setLoading(false);
      if (initialData.page !== query.page) onQueryChange({ ...query, page: initialData.page }, { replace: true });
      return;
    }
    consumedRetry.current = retry;
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    fetchTeacherClasses(query, controller.signal)
      .then((response) => {
        if (!active) return;
        setData(response);
        if (response.page !== query.page) onQueryChange({ ...query, page: response.page }, { replace: true });
      })
      .catch(() => {
        if (!active) return;
        setData(null);
        setError('Không tải được danh sách lớp học. Vui lòng thử lại.');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => {
      active = false;
      controller.abort();
    };
  }, [query, retry, onQueryChange, initialData]);

  const nextSortOrder = (field: ClassSortField) => query.sort_by === field
      ? (query.sort_order === 'asc' ? 'desc' : 'asc')
      : (field === 'creation_date' || field === 'last_session_at' ? 'desc' : 'asc');
  const sortColumn = (field: ClassSortField) => {
    onQueryChange({ ...query, sort_by: field, sort_order: nextSortOrder(field), page: 1 });
  };

  const toggleStar = async (cls: ClassSummaryData) => {
    if (savingStar !== null) return;
    setSavingStar(cls.id);
    setStarError(null);
    try {
      await setClassStar(cls.id, !cls.starred_at);
      if (mounted.current) {
        setRetry(value => value + 1);
        if (latestQuery.current.page !== 1) onQueryChange({ ...latestQuery.current, page: 1 });
      }
    } catch {
      if (mounted.current) setStarError('Không cập nhật được lớp đã lưu. Bấm ngôi sao để thử lại.');
    } finally {
      if (mounted.current) setSavingStar(null);
    }
  };

  const pagingDisabled = loading || searchInput.trim() !== query.q || savingStar !== null;
  const pageButtonClass = 'h-11 sm:h-9 px-3';
  const emptyMessage = query.q ? 'Không tìm thấy lớp phù hợp'
    : query.starred_only ? 'Chưa có lớp đã lưu' : 'Chưa có lớp học';

  return (
    <TooltipProvider delayDuration={300}>
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-3 shrink-0">
          <h1 className="text-lg font-semibold text-text-primary">Danh sách lớp học</h1>
          {data && !loading && <span className="text-xs text-text-secondary tabular-nums">{data.total} lớp</span>}
        </div>
        <div className="flex items-center gap-2 sm:ml-auto">
          <div className="relative flex-1 sm:w-64 sm:flex-none">
            <label htmlFor="class-search" className="sr-only">Tìm lớp</label>
            <Input
              id="class-search" type="search" placeholder="Tìm tên hoặc mã lớp"
              maxLength={128} value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              className="pl-8 h-11 sm:h-9 text-xs"
            />
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary pointer-events-none" aria-hidden="true" />
          </div>
          <div className="relative shrink-0">
          <label htmlFor="class-saved-filter" className="sr-only">Lọc lớp</label>
          <select
            id="class-saved-filter" value={query.starred_only ? 'saved' : 'all'}
            onChange={(event) => onQueryChange({ ...query, starred_only: event.target.value === 'saved', page: 1 })}
            className="h-11 sm:h-9 appearance-none rounded-md border border-border bg-card pl-3 pr-9 text-xs text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
          >
            <option value="all">Tất cả lớp</option>
            <option value="saved">Đã lưu</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-secondary pointer-events-none" aria-hidden="true" />
          </div>
        </div>
      </div>

      {starError && <p role="alert" className="text-xs text-red-700">{starError}</p>}
      {error ? (
        <div role="alert"><ErrorPanel message={error} onRetry={() => setRetry((value) => value + 1)} /></div>
      ) : (
        <div
          role="region" aria-label="Danh sách lớp học" aria-busy={loading}
          tabIndex={0}
          className="overflow-x-auto rounded-md border border-border bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
        >
          <table className="w-full min-w-[1060px] table-fixed text-xs text-left">
            <caption className="sr-only">Danh sách lớp học. Bấm tên cột để sắp xếp. Lớp đã lưu đứng đầu theo lần lưu mới nhất.</caption>
            <colgroup>
              <col style={{ width: 48 }} />
              {COLUMNS.map(({ field, width }) => <col key={field} style={{ width }} />)}
            </colgroup>
            <thead className="bg-card-subtle border-b border-border text-text-secondary">
              <tr>
                <th scope="col" className="w-12 text-center font-medium"><span className="sr-only">Lưu lớp</span></th>
                {COLUMNS.map(({ field, label, right, sortable }) => (
                  <th
                    key={field} scope="col"
                    aria-sort={query.sort_by === field ? (query.sort_order === 'asc' ? 'ascending' : 'descending') : undefined}
                    className={`px-3 font-medium whitespace-nowrap ${right ? 'text-right' : ''}`}
                  >
                    {sortable === false ? label : (
                    <button
                      type="button" onClick={() => sortColumn(field)}
                      className={`flex items-center gap-1.5 w-full h-11 font-medium hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded-sm ${right ? 'justify-end' : ''}`}
                      title={`Sắp xếp ${nextSortOrder(field) === 'desc' ? 'giảm' : 'tăng'} dần`}
                    >
                      {label}
                      {query.sort_by === field && (query.sort_order === 'asc'
                        ? <ArrowUp className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                        : <ArrowDown className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />)}
                    </button>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <>
                  <tr><td colSpan={COLUMN_COUNT} className="px-4 py-3 text-text-secondary" role="status">Đang tải danh sách lớp...</td></tr>
                  {Array.from({ length: Math.min(query.page_size, 8) }, (_, index) => (
                    <tr key={index} aria-hidden="true"><td colSpan={COLUMN_COUNT} className="px-4 py-3"><Skeleton className="h-4" /></td></tr>
                  ))}
                </>
              ) : data?.items.length === 0 ? (
                <tr><td colSpan={COLUMN_COUNT} className="px-4 py-12 text-center text-text-secondary" role="status">{emptyMessage}</td></tr>
              ) : data?.items.map((cls) => (
                <tr key={cls.id} className="hover:bg-card-hover transition-colors">
                  <td className="px-1 text-center">
                    <button
                      type="button" onClick={() => toggleStar(cls)}
                      disabled={savingStar !== null}
                      aria-pressed={Boolean(cls.starred_at)} aria-busy={savingStar === cls.id}
                      aria-label={`${cls.starred_at ? 'Bỏ lưu' : 'Lưu'} lớp ${cls.name}`}
                      title={cls.starred_at ? `Đã lưu ${formatDate(cls.starred_at, true)}` : 'Lưu lớp'}
                      className="inline-flex h-11 w-11 sm:h-9 sm:w-9 items-center justify-center rounded-md hover:bg-card-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:opacity-50"
                    >
                      <Star className={`w-4 h-4 ${cls.starred_at ? 'text-amber-700 fill-amber-700' : 'text-text-tertiary'}`} aria-hidden="true" />
                    </button>
                  </td>
                  <td className="px-3 text-text-secondary font-mono tabular-nums">{cls.id}</td>
                  <td className="px-3">
                    <ClassNameCell cls={cls} classHref={classHref} />
                  </td>
                  <td className="px-3 text-text-secondary tabular-nums">{cls.school_year || 'Chưa có dữ liệu'}</td>
                  <td className="px-3 text-text-secondary">
                    <span className="block truncate" title={cls.managers.map((manager) => manager.name).join(', ')}>
                      {cls.managers.map((manager) => manager.name).join(', ') || 'Chưa có dữ liệu'}
                    </span>
                  </td>
                  <td className="px-3 text-right tabular-nums text-text-secondary">{cls.member_count}</td>
                  <td className="px-3 whitespace-nowrap text-text-secondary tabular-nums" title={formatDate(cls.creation_date, true)}>
                    {formatDate(cls.creation_date) || 'Chưa có ngày tạo'}
                  </td>
                  <td className="px-3 whitespace-nowrap text-text-secondary tabular-nums">
                    {formatDate(cls.last_session_at, true) || 'Chưa có phiên'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && !error && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-text-secondary">
          <p role="status" aria-live="polite" className="tabular-nums">
            {loading ? 'Đang tải...' : data.total === 0 ? '0 lớp'
              : `${(data.page - 1) * data.page_size + 1} - ${Math.min(data.page * data.page_size, data.total)} / ${data.total} lớp`}
          </p>
          <div className="flex flex-wrap items-center gap-3 sm:ml-auto">
            <div className="flex items-center gap-2">
              <label htmlFor="class-page-size">Mỗi trang</label>
              <select
                id="class-page-size" value={query.page_size}
                onChange={(event) => onQueryChange({ ...query, page_size: Number(event.target.value), page: 1 })}
                className="h-11 sm:h-9 rounded-md border border-border bg-card px-2 text-xs text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              >{[12, 24, 48, 100].map((size) => <option key={size} value={size}>{size}</option>)}</select>
            </div>
            {data.total > 0 && (
              <nav aria-label="Phân trang lớp học" className="flex items-center gap-1.5">
                <Button variant="outline" className={pageButtonClass} disabled={pagingDisabled || data.page === 1} onClick={() => onQueryChange({ ...query, page: 1 })} aria-label="Trang đầu">Đầu</Button>
                <Button variant="outline" className={pageButtonClass} disabled={pagingDisabled || data.page === 1} onClick={() => onQueryChange({ ...query, page: data.page - 1 })}>Trước</Button>
                <span className="px-1 tabular-nums">{data.page} / {data.total_pages}</span>
                <Button variant="outline" className={pageButtonClass} disabled={pagingDisabled || data.page >= data.total_pages} onClick={() => onQueryChange({ ...query, page: data.page + 1 })}>Sau</Button>
                <Button variant="outline" className={pageButtonClass} disabled={pagingDisabled || data.page >= data.total_pages} onClick={() => onQueryChange({ ...query, page: data.total_pages })} aria-label="Trang cuối">Cuối</Button>
              </nav>
            )}
          </div>
        </div>
      )}
    </div>
    </TooltipProvider>
  );
};
