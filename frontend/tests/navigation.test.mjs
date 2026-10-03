import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/navigation.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { positiveId, classQuery, classSearch, classListUrl, studentUrl, rosterUrl } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`);

test('invalid and unsafe route IDs produce a not-found response', () => {
  for (const id of [undefined, null, '', '0', '-1', '1.5', 'abc', '1e3', '9007199254740992']) {
    assert.throws(() => positiveId(id), error => error instanceof Response && error.status === 404);
  }
  assert.equal(positiveId('456'), 456);
});

test('malformed list URLs normalize to usable bounded API parameters', () => {
  const query = classQuery(new URLSearchParams('page=-1&size=999&sort=unknown&order=unknown&starred=true&q=' + 'x'.repeat(150)));
  assert.equal(query.page, 1); assert.equal(query.page_size, 100);
  assert.equal(query.sort_by, 'creation_date'); assert.equal(query.sort_order, 'desc');
  assert.equal(query.starred_only, false); assert.equal(query.q.length, 128);
});

test('list context survives nested navigation with Vietnamese and reserved characters', () => {
  const original = classQuery(new URLSearchParams({ page: '3', q: 'Toán & Tin + A', sort: 'name', order: 'asc', starred: '1' }));
  const list = classSearch(original);
  const url = new URL(studentUrl(456, 123, list, 'q=An&alert=STUCK', '7d'), 'http://localhost');
  assert.equal(url.searchParams.get('class'), '123'); assert.equal(url.searchParams.get('range'), '7d');
  assert.deepEqual(classQuery(new URLSearchParams(url.searchParams.get('list'))), original);
  const roster = new URL(rosterUrl(123, url.searchParams.get('list'), url.searchParams.get('roster')), 'http://localhost');
  assert.equal(roster.searchParams.get('q'), 'An'); assert.equal(roster.searchParams.get('alert'), 'STUCK');
  assert.equal(classListUrl('student', roster.searchParams.get('list')), `/student/classes?${list}`);
});

test('global student links do not carry stale class context', () => {
  assert.equal(studentUrl(456), '/student/students/456');
  assert.equal(classListUrl('teacher', 'redirect=https://example.com&page=2'), '/teacher/classes?page=2');
});
