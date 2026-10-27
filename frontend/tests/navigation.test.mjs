import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/navigation.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { positiveId, studentUrl, rosterUrl } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`);

test('invalid and unsafe route IDs produce a not-found response', () => {
  for (const id of [undefined, null, '', '0', '-1', '1.5', 'abc', '1e3', '9007199254740992']) {
    assert.throws(() => positiveId(id), error => error instanceof Response && error.status === 404);
  }
  assert.equal(positiveId('456'), 456);
});

test('roster context survives nested navigation with Vietnamese and reserved characters', () => {
  const list = 'page=3&q=Toán+%26+Tin+%2B+A';
  const url = new URL(studentUrl(456, 123, list, 'q=An&alert=STUCK', '7d'), 'http://localhost');
  assert.equal(url.searchParams.get('class'), '123'); assert.equal(url.searchParams.get('range'), null);
  assert.equal(url.searchParams.get('list'), list);
  const roster = new URL(rosterUrl(123, url.searchParams.get('list'), url.searchParams.get('roster')), 'http://localhost');
  assert.equal(roster.searchParams.get('q'), 'An'); assert.equal(roster.searchParams.get('alert'), 'STUCK');
});

test('global student links do not carry stale class context', () => {
  assert.equal(studentUrl(456), '/student/students/456');
});
