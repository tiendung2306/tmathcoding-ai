import { Link } from 'react-router-dom';
import { UserRound } from 'lucide-react';
import type { AuthAccount } from '../../services/auth';

export function Header({ account }: { account: AuthAccount }) {
  return <header className="dashboard-header">
    <Link to="/teacher/home" aria-label="tmath, về trang chủ" className="dashboard-brand">
      <img src="/tmath-logo.png" alt="" className="h-8 w-8 object-contain" />
      <span>tmath</span>
    </Link>
    <div className="dashboard-account max-w-[calc(100vw-8rem)] flex-wrap justify-end">
      <span className="dashboard-account-avatar" aria-hidden="true"><UserRound className="h-5 w-5" /></span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-sm font-medium text-text-primary">{account.username}</span>
        <span className="block truncate text-xs text-text-secondary">Quản trị viên</span>
      </span>
    </div>
  </header>;
}
