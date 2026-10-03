import React, { useEffect, useRef, useState } from 'react';
import { Link, Outlet, ScrollRestoration, useLocation, useMatches, useNavigation } from 'react-router-dom';
import { Header } from './components/layout/Header';
import { searchStudents } from './services/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './components/ui/dialog';
import { studentUrl } from './lib/navigation';

export interface PageHandle {
  title: string | ((data: any) => string);
  crumbs?: (data: any, search: URLSearchParams) => { label: string; to?: string }[];
}
export function App() {
  const location = useLocation();
  const matches = useMatches();
  const navigation = useNavigation();
  const mainRef = useRef<HTMLElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchGeneration = useRef(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<{ user_id: number; name: string; problem_count: number; points: number }[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const match = [...matches].reverse().find(item => item.handle);
  const handle = match?.handle as PageHandle | undefined;
  const title = typeof handle?.title === 'function' ? handle.title(match?.data) : handle?.title || 'tmath';
  const crumbs = match?.data != null ? handle?.crumbs?.(match.data, new URLSearchParams(location.search)) || [] : [];
  const previousPath = useRef(location.pathname);
  useEffect(() => {
    document.title = `${title} · tmath`;
    if (previousPath.current !== location.pathname) { mainRef.current?.focus({ preventScroll: true }); previousPath.current = location.pathname; }
    searchGeneration.current += 1; setSearchOpen(false);
  }, [location.pathname, title]);
  const submitSearch = async () => {
    if (!searchQuery.trim()) return;
    const generation = ++searchGeneration.current;
    setSubmittedQuery(searchQuery.trim());
    setResults([]); setSearchError(''); setSearching(true); setSearchOpen(true);
    try { const data = await searchStudents(searchQuery.trim()); if (generation === searchGeneration.current) setResults(data); }
    catch { if (generation === searchGeneration.current) setSearchError('Không tìm được học sinh lúc này. Hãy thử lại.'); }
    finally { if (generation === searchGeneration.current) setSearching(false); }
  };
  return <div className="min-h-screen bg-app text-text-primary flex flex-col">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 bg-card p-3">Đến nội dung chính</a>
    <Header searchQuery={searchQuery} setSearchQuery={setSearchQuery} onSearchSubmit={submitSearch} inputRef={searchInputRef} />
    <main id="main-content" ref={mainRef} tabIndex={-1} className="flex-1 min-w-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-primary focus-visible:outline-offset-[-2px]">
      {crumbs.length > 0 && <nav aria-label="Đường dẫn" className="max-w-7xl mx-auto px-3.5 sm:px-5 lg:px-6 pt-4"><ol className="flex flex-wrap items-center gap-x-2 text-sm text-text-secondary">
        {crumbs.map((crumb, index) => <li key={`${index}-${crumb.label}`} className="flex items-center gap-2 min-w-0">
          {index > 0 && <span aria-hidden="true" className="text-text-tertiary">/</span>}
          {crumb.to ? <Link to={crumb.to} className="py-2 hover:underline hover:text-brand-primary break-words">{crumb.label}</Link> : <span aria-current="page" className="py-2 font-medium text-text-primary break-words">{crumb.label}</span>}
        </li>)}
      </ol></nav>}
      {navigation.state !== 'idle' && <div role="status" className="fixed top-0 left-0 right-0 h-1 bg-brand-primary z-50"><span className="sr-only">Đang mở trang...</span></div>}
      <Outlet />
    </main>
    <Dialog open={searchOpen} onOpenChange={open => { setSearchOpen(open); if (!open) searchGeneration.current += 1; }}>
      <DialogContent onCloseAutoFocus={event => { event.preventDefault(); searchInputRef.current?.focus(); }} className="max-w-lg"><DialogHeader><DialogTitle>Kết quả tìm kiếm</DialogTitle><DialogDescription>Học sinh khớp với “{submittedQuery}”.</DialogDescription></DialogHeader>
        {searching ? <p role="status">Đang tìm học sinh...</p> : searchError ? <div role="alert"><p>{searchError}</p><button onClick={submitSearch} className="mt-3 underline min-h-11">Thử lại</button></div> : results.length === 0 ? <p role="status">Không tìm thấy học sinh. Hãy thử tên hoặc tên đăng nhập khác.</p> : <ul className="max-h-[60vh] overflow-y-auto space-y-2">{results.map(student => <li key={student.user_id}>
          <Link to={studentUrl(student.user_id)} onClick={() => setSearchOpen(false)} className="block rounded-md border border-border p-3 hover:bg-card-subtle"><span className="block font-medium">{student.name}</span><span className="text-xs text-text-secondary">#{student.user_id} · {student.problem_count} bài · {student.points} điểm</span></Link>
        </li>)}</ul>}
      </DialogContent>
    </Dialog>
    <ScrollRestoration />
  </div>;
}
export default App;
