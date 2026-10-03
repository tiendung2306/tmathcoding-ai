import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Search } from 'lucide-react';
import { Input } from '../ui/input';
interface HeaderProps { searchQuery: string; setSearchQuery: (value: string) => void; onSearchSubmit: () => void; inputRef: React.RefObject<HTMLInputElement> }
export function Header({ searchQuery, setSearchQuery, onSearchSubmit, inputRef }: HeaderProps) {
  const { pathname } = useLocation();
  const area = pathname.startsWith('/teacher') ? 'Lớp học ảo' : pathname.startsWith('/admin') ? 'Quản trị viên' : 'Học sinh';
  return <header className="sticky top-0 z-20 border-b border-border bg-card"><div className="max-w-7xl mx-auto px-3.5 sm:px-5 lg:px-6 py-2 flex flex-wrap items-center gap-x-4 gap-y-2">
    <Link to="/" aria-label="tmath, chọn khu vực làm việc" className="flex items-center gap-2 min-h-11 shrink-0 font-semibold text-sm"><img src="/tmath-logo.png" alt="" className="w-7 h-7 object-contain" />tmath OJ</Link>
    <span className="text-sm text-text-secondary">{area}</span><Link to="/" className="ml-auto text-sm min-h-11 inline-flex items-center hover:underline">Đổi khu vực</Link>
    <form role="search" className="w-full sm:w-72 sm:ml-4" onSubmit={event => { event.preventDefault(); onSearchSubmit(); }}><div className="relative">
      <Input ref={inputRef} value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Tìm học sinh..." aria-label="Tên hoặc tên đăng nhập học sinh" className="h-11 pr-12" />
      <button type="submit" aria-label="Tìm học sinh" className="absolute top-0 right-0 h-11 w-11 inline-flex items-center justify-center rounded-md hover:bg-card-subtle"><Search className="w-4 h-4" /></button>
    </div></form>
  </div></header>;
}
