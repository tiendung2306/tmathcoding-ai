import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationBarProps {
  label: string;
  page: number;
  totalPages: number;
  visiblePages: number[];
  canGoPrevious: boolean;
  canGoNext: boolean;
  onPage: (page: number) => void;
  onPrevious: () => void;
  onNext: () => void;
  disabled?: boolean;
}

export function getVisiblePageNumbers(page: number, totalPages: number): number[] {
  if (totalPages <= 8) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (page <= 4) {
    return [1, 2, 3, 4, 5, 6, totalPages - 1, totalPages];
  }
  if (page >= totalPages - 3) {
    return [1, totalPages - 5, totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  }
  return [1, page - 1, page, page + 1, totalPages - 1, totalPages];
}

export function PaginationBar({
  label,
  page,
  totalPages,
  visiblePages,
  canGoPrevious,
  canGoNext,
  onPage,
  onPrevious,
  onNext,
  disabled = false,
}: PaginationBarProps) {
  const pages = [...new Set(visiblePages)].sort((left, right) => left - right);

  return <nav aria-label={label} className="inline-flex max-w-full items-center gap-1 overflow-x-auto rounded-full border border-border bg-card p-1.5 shadow-xs">
    <button type="button" onClick={onPrevious} disabled={disabled || !canGoPrevious} aria-label="Trang trước" className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-200 text-slate-700 hover:bg-slate-300 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
      <ChevronLeft aria-hidden className="h-4 w-4" />
    </button>
    {pages.map((pageNumber, index) => {
      const previousPageNumber = pages[index - 1];
      return <span key={pageNumber} className="contents">
        {previousPageNumber !== undefined && pageNumber - previousPageNumber > 1 && <span aria-hidden="true" className="min-w-8 px-1 text-center text-sm text-text-secondary">…</span>}
        <button type="button" onClick={() => onPage(pageNumber)} disabled={disabled} aria-current={pageNumber === page ? 'page' : undefined} aria-label={`Trang ${pageNumber}`} className={`grid h-10 min-w-10 shrink-0 place-items-center rounded-xl px-3 text-sm font-semibold tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed ${pageNumber === page ? 'bg-brand-primary text-white shadow-sm' : 'text-text-primary hover:bg-brand-primary/5'}`}>
          {pageNumber}
        </button>
      </span>;
    })}
    {pages.length > 0 && pages[pages.length - 1] < totalPages && <span aria-hidden="true" className="min-w-8 px-1 text-center text-sm text-text-secondary">…</span>}
    <button type="button" onClick={onNext} disabled={disabled || !canGoNext} aria-label="Trang sau" className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-200 text-slate-700 hover:bg-slate-300 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">
      <ChevronRight aria-hidden className="h-4 w-4" />
    </button>
  </nav>;
}
