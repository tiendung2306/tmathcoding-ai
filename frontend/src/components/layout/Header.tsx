import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { UserRound } from 'lucide-react';
import { logout, type AuthAccount } from '../../services/auth';

export function Header({ account }: { account: AuthAccount }) {
  const [logoutError, setLogoutError] = useState(false);
  const signOut = async () => {
    try { await logout(); window.location.assign('/'); }
    catch { setLogoutError(true); }
  };
  return <header className="dashboard-header">
    <Link to="/student/students" aria-label="tmath, về danh sách học sinh" className="dashboard-brand">
      <img src="/tmath-logo.png" alt="" className="h-8 w-8 object-contain" />
      <span>tmath</span>
    </Link>
    <div className="dashboard-account max-w-[calc(100vw-8rem)] flex-wrap justify-end">
      <span className="dashboard-account-avatar" aria-hidden="true"><UserRound className="h-5 w-5" /></span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-sm font-medium text-text-primary">{account.username}</span>
        <span className="block truncate text-xs text-text-secondary">Quản trị viên</span>
      </span>
      <button type="button" onClick={signOut} className="ml-2 min-h-11 px-3 text-sm text-text-secondary underline hover:text-text-primary">Đăng xuất</button>
      {logoutError && <span role="alert" className="w-full text-right text-xs text-red-800">Chưa đăng xuất được. Hãy thử lại.</span>}
    </div>
  </header>;
}
