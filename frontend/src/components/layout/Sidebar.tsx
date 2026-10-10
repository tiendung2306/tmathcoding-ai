import React from 'react';
import { BarChart3, FileText, GraduationCap, Home, Presentation, Settings, ShieldCheck, type LucideIcon } from 'lucide-react';
import { Link, NavLink, useLocation } from 'react-router-dom';

type NavigationItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
};

const primaryItems: NavigationItem[] = [
  { to: '/', label: 'Trang chủ', icon: Home, end: true },
  { to: '/student/classes', label: 'Học sinh', icon: GraduationCap },
  { to: '/teacher/classes', label: 'Lớp học', icon: Presentation },
  { to: '/admin', label: 'Quản trị viên', icon: ShieldCheck },
];

const settingsItem: NavigationItem = { to: '/settings', label: 'Cài đặt', icon: Settings };

function NavigationLink({ item }: { item: NavigationItem }) {
  const Icon = item.icon;
  return <NavLink
    to={item.to}
    end={item.end}
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
      {item.to === '/student/classes' && <StudentDetailTabs />}
    </React.Fragment>)}
  </>;
}

export function Sidebar() {
  return <>
    <aside className="dashboard-sidebar" aria-label="Điều hướng chính">
      <nav className="dashboard-sidebar-nav">
        <PrimaryNavigation />
      </nav>
      <nav className="dashboard-sidebar-settings" aria-label="Thiết lập">
        <NavigationLink item={settingsItem} />
      </nav>
    </aside>
    <details className="dashboard-mobile-menu">
      <summary>Menu</summary>
      <nav aria-label="Điều hướng chính trên điện thoại">
        <PrimaryNavigation />
        <NavigationLink item={settingsItem} />
      </nav>
    </details>
  </>;
}
