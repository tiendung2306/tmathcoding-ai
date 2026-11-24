import type { ReactNode } from 'react';
import { formatMemoryKb } from '../lib/utils';

/** One submission in a list: verdict tile, problem, when, then run time and memory. Opens the detail on click. */
export function SubmissionRow({ points, result, language, name, title, meta, time, memory, onOpen }: {
  points: number | null;
  result: string | null;
  language?: string | null;
  /** Problem name, also used to label the button. */
  name: string;
  /** Shown instead of the name, e.g. with the contest letter. */
  title?: ReactNode;
  /** Line under the title (when it was submitted, by whom). */
  meta: ReactNode;
  time: number | null;
  memory: number | null;
  onOpen: () => void;
}) {
  const tone = resultTone(result);
  return <button type="button" onClick={onOpen} aria-label={`Xem bài nộp ${name}, ${formatPoints(points)} điểm`} className="group flex w-full cursor-pointer items-center gap-3 p-3 text-left transition-colors hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary sm:gap-4 sm:px-5 sm:py-4">
    <span role="img" aria-label={`${formatPoints(points)} điểm, ${result || 'chưa rõ kết quả'}`} className={`flex h-[4.75rem] w-[4.75rem] shrink-0 flex-col items-center justify-center rounded-xl text-center ${tone}`}>
      <strong className="max-w-full truncate px-1 text-base tabular-nums">{formatPoints(points)}</strong>
      <span className="mt-1 max-w-full truncate px-1 text-[10px] font-semibold uppercase tracking-wide">{result || '—'}{language ? ` · ${language}` : ''}</span>
    </span>
    <span className="min-w-0 flex-1">
      <span className="block max-w-full truncate text-sm font-semibold text-text-primary group-hover:text-brand-primary group-focus-visible:text-brand-primary sm:text-base">{title ?? name}</span>
      <span className="mt-1 block text-xs text-text-secondary">{meta}</span>
    </span>
    <span className="hidden shrink-0 text-right text-xs tabular-nums text-text-secondary sm:block">
      <strong className="block font-mono text-text-primary">{time === null ? '—' : `${time.toFixed(3)} giây`}</strong>
      <span className="mt-1 block">{formatMemoryKb(memory)}</span>
    </span>
  </button>;
}

function resultTone(result: string | null | undefined) {
  switch ((result || '').toUpperCase()) {
    case 'AC': return 'bg-emerald-500 text-white';
    case 'WA': case 'RTE': case 'CE': case 'OLE': return 'bg-red-500 text-white';
    case 'TLE': case 'MLE': case 'QU': return 'bg-amber-400 text-slate-900';
    default: return 'bg-card-subtle text-text-secondary';
  }
}

export function formatPoints(value: number | null) {
  if (value === null) return '—';
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(value);
}
