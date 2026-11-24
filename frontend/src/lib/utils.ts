import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** The judge stores memory in KB (submission usage and problem limits alike). */
export function formatMemoryKb(kb: number | null | undefined): string {
  if (kb === null || kb === undefined || !Number.isFinite(kb)) return '—';
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `${mb >= 100 || Number.isInteger(mb) ? Math.round(mb) : mb.toFixed(1)} MB`;
}
