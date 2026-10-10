import React, { useEffect, useRef } from 'react';
import { Outlet, ScrollRestoration, useLocation, useMatches, useNavigation } from 'react-router-dom';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';

export interface PageHandle {
  title: string | ((data: any) => string);
}
export function App() {
  const location = useLocation();
  const matches = useMatches();
  const navigation = useNavigation();
  const mainRef = useRef<HTMLElement>(null);
  const match = [...matches].reverse().find(item => item.handle);
  const handle = match?.handle as PageHandle | undefined;
  const title = typeof handle?.title === 'function' ? handle.title(match?.data) : handle?.title || 'tmath';
  const previousPath = useRef(location.pathname);
  useEffect(() => {
    document.title = `${title} · tmath`;
    if (previousPath.current !== location.pathname) { mainRef.current?.focus({ preventScroll: true }); previousPath.current = location.pathname; }
  }, [location.pathname, title]);
  return <div className="min-h-screen bg-app text-text-primary">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 bg-card p-3">Đến nội dung chính</a>
    <Header />
    <div className="dashboard-layout">
      <Sidebar />
      <main id="main-content" ref={mainRef} tabIndex={-1} className="min-w-0 flex-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-primary focus-visible:outline-offset-[-2px]">
      {navigation.state !== 'idle' && <div role="status" className="fixed top-0 left-0 right-0 h-1 bg-brand-primary z-50"><span className="sr-only">Đang mở trang...</span></div>}
      <Outlet />
      </main>
    </div>
    <ScrollRestoration />
  </div>;
}
export default App;
