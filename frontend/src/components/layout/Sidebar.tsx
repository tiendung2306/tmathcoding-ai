import React, { useState } from 'react';
import { BarChart3, FileText, GraduationCap, Home, LogOut, ShieldCheck, Trophy, type LucideIcon } from 'lucide-react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { logout } from '../../services/auth';

type NavigationItem = {
  to: string;
  label: string;
  icon: LucideIcon;
};

const primaryItems: NavigationItem[] = [
  { to: '/teacher/home', label: 'Trang chủ', icon: Home },
  { to: '/student/students', label: 'Học sinh', icon: GraduationCap },
  { to: '/teacher/contests', label: 'Cuộc thi', icon: Trophy },
  { to: '/admin', label: 'Quản trị viên', icon: ShieldCheck },
];

function NavigationLink({ item }: { item: NavigationItem }) {
  const Icon = item.icon;
  return <NavLink
    to={item.to}
    className={({ isActive }) => `dashboard-nav-link${isActive ? ' dashboard-nav-link-active' : ''}`}
  >
    <Icon aria-hidden className="h-5 w-5 shrink-0" />
    <span>{item.label}</span>
  </NavLink>;
}

function StudentDetailTabs() {
  const location = useLocation();
  if (!/^\/student\/students\/\d+$/.test(location.pathname)) return null;

  const hrefFor = (tab: 'overview' | 'submissions') => {
    const search = new URLSearchParams(location.search);
    if (tab === 'overview') search.delete('tab'); else search.set('tab', tab);
    const query = search.toString();
    return `${location.pathname}${query ? `?${query}` : ''}`;
  };
  const activeTab = new URLSearchParams(location.search).get('tab') === 'submissions' ? 'submissions' : 'overview';
  const items = [
    { tab: 'overview' as const, label: 'Tổng quan', icon: BarChart3 },
    { tab: 'submissions' as const, label: 'Bài nộp', icon: FileText },
  ];

  return <div className="dashboard-student-subnav">
    {items.map(item => {
      const Icon = item.icon;
      return <Link key={item.tab} to={hrefFor(item.tab)} className={`dashboard-nav-link${activeTab === item.tab ? ' dashboard-nav-link-active' : ''}`} aria-current={activeTab === item.tab ? 'page' : undefined}>
        <Icon aria-hidden className="h-5 w-5 shrink-0" />
        <span>{item.label}</span>
      </Link>;
    })}
  </div>;
}

function PrimaryNavigation() {
  return <>
    {primaryItems.map(item => <React.Fragment key={item.to}>
      <NavigationLink item={item} />
      {item.to === '/student/students' && <StudentDetailTabs />}
    </React.Fragment>)}
  </>;
}

function LogoutButton() {
  const [logoutError, setLogoutError] = useState(false);
  const signOut = async () => {
    try {
      await logout();
      window.location.assign('/login');
    } catch {
      setLogoutError(true);
    }
  };

  return <div className="grid gap-2">
    <button type="button" onClick={signOut} className="flex min-h-11 w-full items-center gap-2 rounded-md bg-red-700 px-3 text-sm font-medium text-white hover:bg-red-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-700 focus-visible:ring-offset-2">
      <LogOut aria-hidden className="h-4 w-4 shrink-0" />
      <span>Đăng xuất</span>
    </button>
    {logoutError && <span role="alert" className="text-xs text-red-800">Chưa đăng xuất được. Hãy thử lại.</span>}
  </div>;
}

export function Sidebar() {
  return <>
    <aside className="dashboard-sidebar" aria-label="Điều hướng chính">
      <nav className="dashboard-sidebar-nav">
        <PrimaryNavigation />
      </nav>
      <div className="mt-auto border-t border-border pt-3">
        <LogoutButton />
      </div>
    </aside>
    <details className="dashboard-mobile-menu">
      <summary>Menu</summary>
      <nav aria-label="Điều hướng chính trên điện thoại">
        <PrimaryNavigation />
        <div className="border-t border-border pt-3">
          <LogoutButton />
        </div>
      </nav>
    </details>
  </>;
}
