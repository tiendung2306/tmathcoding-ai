export interface ContestWindow {
  starts_at: string;
  ends_at: string;
}

export interface ContestSubmission {
  id: number;
  user_id: number;
  user_name: string;
  problem_id: number;
  problem_name: string;
  date: string;
  result: string;
}

export type ResultFilter = 'all' | 'ac' | 'failed';

const LIVE_INTERVAL_MS = 5_000;
const MAX_WAIT_INTERVAL_MS = 60_000;
/** Keep polling briefly after the end so late judging results still arrive. */
const AFTER_END_GRACE_MS = 2 * 60_000;

/**
 * How often the contest room should refresh. Uses the contest's own time window
 * rather than the status captured when the page loaded, so an upcoming contest
 * starts refreshing by itself and an ended one stops.
 */
export function contestPollInterval(contest: ContestWindow, serverActive: boolean | undefined, now = Date.now()): number | false {
  const start = Date.parse(contest.starts_at);
  const end = Date.parse(contest.ends_at);
  if (serverActive) return LIVE_INTERVAL_MS;
  if (Number.isFinite(start) && now < start) return Math.min(MAX_WAIT_INTERVAL_MS, Math.max(LIVE_INTERVAL_MS, start - now));
  if (Number.isFinite(end) && now <= end + AFTER_END_GRACE_MS) return LIVE_INTERVAL_MS;
  return false;
}

export function normalizeText(value: string): string {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().trim();
}

export function filterSubmissions<T extends ContestSubmission>(items: T[], result: ResultFilter, query: string): T[] {
  const term = normalizeText(query);
  return items.filter(item => {
    if (result === 'ac' && item.result !== 'AC') return false;
    if (result === 'failed' && item.result === 'AC') return false;
    return !term || normalizeText(`${item.user_name} ${item.problem_name}`).includes(term);
  });
}

export interface RosterStudent { user_id: number; name: string; username?: string | null }

export interface ProblemColumn {
  problem_id: number;
  /** Column header: the problem's letter in the contest (A, B, ..., Z, AA, ...). */
  label: string;
  code: string;
  name: string;
  /** Maximum points in this contest; unknown when the source has no contest problem list. */
  points: number | null;
}

export interface SessionProblem { problem_id: number; code: string; title: string; label: string; points?: number | null }

export interface StandingCell {
  /** Best score on this problem. */
  score: number;
  full: boolean;
  /** Seconds from the contest start to the first submission that reached the best score. */
  seconds: number;
  /** That submission, opened when the cell is clicked. */
  submissionId: number;
  attempts: number;
  /** First student to get full points on this problem. */
  firstSolve: boolean;
}

export interface StandingRow {
  user_id: number;
  user_name: string;
  username: string | null;
  /** Competition rank (ties share a rank); null for students without submissions. */
  rank: number | null;
  total: number;
  /** Sum of the times of the scored problems, like the judge's cumulative time. */
  seconds: number;
  submissions: number;
  cells: Record<number, StandingCell>;
}

export type StandingSubmission = ContestSubmission & { problem_code?: string | null; points?: number | null; score?: number | null };

/** A, B, ..., Z, AA, AB, ... like the contest problem letters. */
export function problemLabel(index: number): string {
  let label = '';
  for (let value = index + 1; value > 0; value = Math.floor((value - 1) / 26)) {
    label = String.fromCharCode(65 + ((value - 1) % 26)) + label;
  }
  return label;
}

function naturalCompare(left: string, right: string) {
  return left.localeCompare(right, 'vi', { numeric: true, sensitivity: 'base' });
}

const EPSILON = 1e-9;

/**
 * Contest standings in the judge's default format: per problem the best score
 * counts, at the time it was first reached; students rank by total points, then
 * by cumulative time. Every roster student gets a row; students who have not
 * submitted stay unranked at the bottom.
 */
export function buildStandings(items: StandingSubmission[], roster: RosterStudent[],
  sessionProblems: SessionProblem[] = [], startsAt?: string) {
  const problems = new Map<number, ProblemColumn>(sessionProblems.map(problem => [problem.problem_id,
    { problem_id: problem.problem_id, label: problem.label, code: problem.code, name: problem.title, points: problem.points ?? null }]));
  const rows = new Map<number, StandingRow>();
  const newRow = (user_id: number, user_name: string, username: string | null = null): StandingRow =>
    ({ user_id, user_name, username, rank: null, total: 0, seconds: 0, submissions: 0, cells: {} });
  for (const student of roster) rows.set(student.user_id, newRow(student.user_id, student.name, student.username || null));
  const start = startsAt ? Date.parse(startsAt) : NaN;
  const chronological = [...items].sort((left, right) => left.date.localeCompare(right.date) || left.id - right.id);
  const origin = Number.isFinite(start) ? start : chronological.length ? Date.parse(chronological[0].date) : 0;
  for (const item of chronological) {
    if (!problems.has(item.problem_id)) {
      const code = item.problem_code || `#${item.problem_id}`;
      problems.set(item.problem_id, { problem_id: item.problem_id, label: code, code, name: item.problem_name, points: null });
    }
    const column = problems.get(item.problem_id)!;
    let row = rows.get(item.user_id);
    if (!row) { row = newRow(item.user_id, item.user_name); rows.set(item.user_id, row); }
    row.submissions += 1;
    const score = item.score ?? item.points ?? (item.result === 'AC' ? 1 : 0);
    const full = column.points != null ? score >= column.points - EPSILON : item.result === 'AC';
    const seconds = Math.max(0, Math.floor((Date.parse(item.date) - origin) / 1000));
    const cell = row.cells[item.problem_id];
    if (!cell) {
      row.cells[item.problem_id] = { score, full, seconds, submissionId: item.id, attempts: 1, firstSolve: false };
    } else {
      cell.attempts += 1;
      if (score > cell.score + EPSILON) Object.assign(cell, { score, full, seconds, submissionId: item.id });
    }
  }
  // First full score per problem gets highlighted.
  for (const column of problems.values()) {
    let first: StandingCell | null = null;
    for (const row of rows.values()) {
      const cell = row.cells[column.problem_id];
      if (cell?.full && (!first || cell.seconds < first.seconds || (cell.seconds === first.seconds && cell.submissionId < first.submissionId))) first = cell;
    }
    if (first) first.firstSolve = true;
  }
  for (const row of rows.values()) {
    for (const cell of Object.values(row.cells)) {
      row.total += cell.score;
      if (cell.score > EPSILON) row.seconds += cell.seconds;
    }
    row.total = Math.round(row.total * 1000) / 1000;
  }
  const ranked = [...rows.values()].filter(row => row.submissions > 0)
    .sort((left, right) => right.total - left.total || left.seconds - right.seconds || left.user_name.localeCompare(right.user_name, 'vi'));
  ranked.forEach((row, index) => {
    const previous = ranked[index - 1];
    row.rank = previous && Math.abs(previous.total - row.total) < EPSILON && previous.seconds === row.seconds ? previous.rank : index + 1;
  });
  const unranked = [...rows.values()].filter(row => row.submissions === 0)
    .sort((left, right) => left.user_name.localeCompare(right.user_name, 'vi'));
  // The contest's own order wins; otherwise sort derived columns by code and letter them.
  const columns = sessionProblems.length ? [...problems.values()]
    : [...problems.values()]
      .sort((left, right) => naturalCompare(left.code, right.code) || left.problem_id - right.problem_id)
      .map((column, index) => ({ ...column, label: problemLabel(index) }));
  return { problems: columns, rows: [...ranked, ...unranked] };
}

/** 1000, 33.33: scores without trailing zeros. */
export function formatScore(value: number): string {
  return String(Math.round(value * 100) / 100);
}

/** Elapsed time like the judge's standings: hours keep growing (136:25:23). */
export function formatElapsed(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return [Math.floor(seconds / 3600), Math.floor((seconds % 3600) / 60), seconds % 60]
    .map(value => String(value).padStart(2, '0')).join(':');
}

export function formatCountdown(target: string, now: number): string {
  const seconds = Math.max(0, Math.floor((new Date(target).getTime() - now) / 1000));
  const days = Math.floor(seconds / 86_400);
  const clock = [Math.floor((seconds % 86_400) / 3_600), Math.floor((seconds % 3_600) / 60), seconds % 60]
    .map(value => String(value).padStart(2, '0')).join(':');
  return days > 0 ? `${days} ngày ${clock}` : clock;
}
