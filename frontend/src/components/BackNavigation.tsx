import { ArrowLeft } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { detailBackTarget } from '../lib/navigation';

/** Pages that place the back link inside their own header row. */
const PAGES_WITH_OWN_BACK_LINK = [/^\/teacher\/contests\/\d+$/];

function useBackTarget() {
  const location = useLocation();
  const from = (location.state as { from?: unknown } | null)?.from;
  return detailBackTarget(location.pathname, location.search, from);
}

export function BackLink({ compact = false }: { compact?: boolean }) {
  const target = useBackTarget();
  if (!target) return null;
  return <Link to={target} aria-label="Quay lại" className="-ml-1 inline-flex min-h-11 min-w-11 items-center gap-2 rounded-md px-1 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
    <ArrowLeft aria-hidden className="size-4" /><span className={compact ? 'hidden sm:inline' : undefined}>Quay lại</span>
  </Link>;
}

export function BackNavigation() {
  const { pathname } = useLocation();
  if (PAGES_WITH_OWN_BACK_LINK.some(pattern => pattern.test(pathname))) return null;
  return <div className="mx-auto max-w-7xl px-3.5 pt-3 empty:hidden sm:px-5 lg:px-6">
    <BackLink />
  </div>;
}
