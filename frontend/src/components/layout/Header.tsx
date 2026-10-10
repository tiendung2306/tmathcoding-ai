import React from 'react';
import { Link } from 'react-router-dom';
import { UserRound } from 'lucide-react';

export function Header() {
  return <header className="dashboard-header">
    <Link to="/" aria-label="tmath, về trang chủ" className="dashboard-brand">
      <img src="/tmath-logo.png" alt="" className="h-8 w-8 object-contain" />
      <span>tmath</span>
    </Link>
    <div className="dashboard-account" aria-label="Trạng thái tài khoản: chưa đăng nhập">
      <span className="dashboard-account-avatar" aria-hidden="true"><UserRound className="h-5 w-5" /></span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-sm font-medium text-text-primary">Người dùng</span>
        <span className="block truncate text-xs text-text-secondary">Chưa đăng nhập</span>
      </span>
    </div>
  </header>;
}
