import { ArrowLeft } from 'lucide-react';
import { Link, useLocation, useMatches } from 'react-router-dom';
import { detailBackTarget } from '../lib/navigation';

export function BackNavigation() {
  const location = useLocation();
  const matches = useMatches();
  const from = (location.state as { from?: unknown } | null)?.from;
  const data = matches[matches.length - 1]?.data as { org_id?: number } | undefined;
  const target = detailBackTarget(location.pathname, location.search, from, data?.org_id);
  if (!target) return null;

  return <div className="mx-auto max-w-7xl px-3.5 pt-3 sm:px-5 lg:px-6">
    <Link to={target} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium text-text-secondary transition-colors hover:border-border-control hover:bg-card-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
      <ArrowLeft aria-hidden className="size-4" />Quay lại
    </Link>
  </div>;
}
