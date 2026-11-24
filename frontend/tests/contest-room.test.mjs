import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from './load-ts.mjs';

const { contestPollInterval, filterSubmissions } =
  await import(await tsModuleUrl(new URL('../src/lib/contestRoom.ts', import.meta.url)));

const contest = { starts_at: '2026-11-24T08:00:00Z', ends_at: '2026-11-24T10:00:00Z' };
const at = iso => Date.parse(iso);

test('an upcoming contest polls until it starts instead of never refreshing', () => {
  assert.equal(contestPollInterval(contest, false, at('2026-11-24T07:59:50Z')), 10_000);
  assert.equal(contestPollInterval(contest, false, at('2026-11-24T06:00:00Z')), 60_000);
});

test('a running contest polls every five seconds even before the server flag catches up', () => {
  assert.equal(contestPollInterval(contest, true, at('2026-11-24T09:00:00Z')), 5_000);
  assert.equal(contestPollInterval(contest, false, at('2026-11-24T09:00:00Z')), 5_000);
});

test('an ended contest stops polling after a short grace period', () => {
  assert.equal(contestPollInterval(contest, false, at('2026-11-24T10:01:00Z')), 5_000);
  assert.equal(contestPollInterval(contest, false, at('2026-11-24T10:30:00Z')), false);
});

const rows = [
  { id: 1, user_id: 1, user_name: 'Nguyễn An', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:10:00Z', result: 'WA' },
  { id: 2, user_id: 1, user_name: 'Nguyễn An', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:20:00Z', result: 'AC' },
  { id: 3, user_id: 1, user_name: 'Nguyễn An', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:25:00Z', result: 'AC' },
  { id: 4, user_id: 2, user_name: 'Đặng Bình', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:15:00Z', result: 'AC' },
  { id: 5, user_id: 2, user_name: 'Đặng Bình', problem_id: 11, problem_name: 'Đồ thị', date: '2026-11-24T08:40:00Z', result: 'AC' },
];

test('filters by verdict and by accent-insensitive student or problem name', () => {
  assert.deepEqual(filterSubmissions(rows, 'failed', '').map(row => row.id), [1]);
  assert.deepEqual(filterSubmissions(rows, 'all', 'dang binh').map(row => row.id), [4, 5]);
  assert.deepEqual(filterSubmissions(rows, 'ac', 'do thi').map(row => row.id), [5]);
});


const { buildStandings, formatCountdown, formatElapsed, formatScore, problemLabel } =
  await import(await tsModuleUrl(new URL('../src/lib/contestRoom.ts', import.meta.url)));

const START = '2026-11-24T08:00:00Z';
const contestProblems = [
  { problem_id: 10, code: 'B2', title: 'Tổng dãy', label: 'A', points: 100 },
  { problem_id: 11, code: 'B10', title: 'Đồ thị', label: 'B', points: 100 },
];
const scored = [
  { id: 1, user_id: 1, user_name: 'Nguyễn An', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:10:00Z', result: 'WA', score: 40 },
  { id: 2, user_id: 1, user_name: 'Nguyễn An', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:20:00Z', result: 'AC', score: 100 },
  { id: 3, user_id: 1, user_name: 'Nguyễn An', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:25:00Z', result: 'AC', score: 100 },
  { id: 4, user_id: 2, user_name: 'Đặng Bình', problem_id: 10, problem_name: 'Tổng dãy', date: '2026-11-24T08:15:00Z', result: 'AC', score: 100 },
  { id: 5, user_id: 2, user_name: 'Đặng Bình', problem_id: 11, problem_name: 'Đồ thị', date: '2026-11-24T08:40:00Z', result: 'WA', score: 0 },
  { id: 6, user_id: 4, user_name: 'Lê Cường', problem_id: 11, problem_name: 'Đồ thị', date: '2026-11-24T09:00:00Z', result: 'WA', score: 30 },
];

test('standings keep the best score per problem at the time it was first reached', () => {
  const roster = [{ user_id: 1, name: 'Nguyễn An', username: 'an01' }, { user_id: 2, name: 'Đặng Bình' }, { user_id: 3, name: 'Chưa Nộp' }];
  const { problems, rows } = buildStandings(scored, roster, contestProblems, START);
  assert.deepEqual(problems.map(problem => [problem.label, problem.points]), [['A', 100], ['B', 100]]);
  // Bình and An both have 100; Bình got there earlier. Cường has 30. Chưa Nộp is unranked.
  assert.deepEqual(rows.map(row => [row.user_id, row.rank, row.total, row.seconds]),
    [[2, 1, 100, 900], [1, 2, 100, 1200], [4, 3, 30, 3600], [3, null, 0, 0]]);
  const an = rows.find(row => row.user_id === 1);
  assert.equal(an.username, 'an01');
  assert.deepEqual(an.cells[10], { score: 100, full: true, seconds: 1200, submissionId: 2, attempts: 3, firstSolve: false });
  const binh = rows.find(row => row.user_id === 2);
  assert.equal(binh.cells[10].firstSolve, true);
  assert.deepEqual([binh.cells[11].score, binh.cells[11].full], [0, false]);
});

test('equal points and time share a rank', () => {
  const tie = [
    { id: 1, user_id: 1, user_name: 'An', problem_id: 10, problem_name: 'A', date: '2026-11-24T08:10:00Z', result: 'AC', score: 100 },
    { id: 2, user_id: 2, user_name: 'Bình', problem_id: 10, problem_name: 'A', date: '2026-11-24T08:10:00Z', result: 'AC', score: 100 },
    { id: 3, user_id: 3, user_name: 'Cường', problem_id: 10, problem_name: 'A', date: '2026-11-24T08:30:00Z', result: 'WA', score: 0 },
  ];
  const { rows } = buildStandings(tie, [], contestProblems, START);
  assert.deepEqual(rows.map(row => row.rank), [1, 1, 3]);
  assert.deepEqual(rows.filter(row => row.cells[10].firstSolve).map(row => row.user_id), [1]);
});

test('without contest problems, AC counts as solved and columns are lettered by code', () => {
  const { problems, rows } = buildStandings(scored.map(({ score, ...row }) => ({ ...row, problem_code: row.problem_id === 10 ? 'B2' : 'B10' })), [], [], START);
  assert.deepEqual(problems.map(problem => [problem.label, problem.code, problem.points]), [['A', 'B2', null], ['B', 'B10', null]]);
  assert.equal(rows.find(row => row.user_id === 1).cells[10].full, true);
});

test('scores and elapsed times read like the judge standings', () => {
  assert.deepEqual([1000, 33.333, 0, 12.5].map(formatScore), ['1000', '33.33', '0', '12.5']);
  assert.equal(formatElapsed(172), '00:02:52');
  assert.equal(formatElapsed(136 * 3600 + 25 * 60 + 23), '136:25:23');
});

test('countdown formats hours and days', () => {
  assert.equal(formatCountdown('2026-11-24T10:00:00Z', Date.parse('2026-11-24T08:58:59Z')), '01:01:01');
  assert.equal(formatCountdown('2026-11-26T10:00:00Z', Date.parse('2026-11-24T10:00:00Z')), '2 ngày 00:00:00');
  assert.equal(formatCountdown('2026-11-24T10:00:00Z', Date.parse('2026-11-24T11:00:00Z')), '00:00:00');
});

test('session problems define the columns and their order, even before anyone submits', () => {
  const { problems } = buildStandings([], [], [contestProblems[1], contestProblems[0]], START);
  assert.deepEqual(problems.map(problem => problem.code), ['B10', 'B2']);
});

test('problem letters continue past Z', () => {
  assert.deepEqual([0, 1, 25, 26, 27, 51, 52].map(problemLabel), ['A', 'B', 'Z', 'AA', 'AB', 'AZ', 'BA']);
});
