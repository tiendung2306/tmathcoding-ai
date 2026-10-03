import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import { QueryObserver } from '@tanstack/react-query';
import axios from 'axios';

const source = await readFile(new URL('../src/lib/queryClient.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
  .replace('@tanstack/react-query', import.meta.resolve('@tanstack/react-query'));
const clientModule = `data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`;
const { queryClient } = await import(clientModule);

test('StrictMode-style unsubscribe/remount shares a pending read', async () => {
  let calls = 0;
  let finish;
  const options = { queryKey: ['strict-mode'], queryFn: () => { calls++; return new Promise(resolve => { finish = resolve; }); } };
  const first = new QueryObserver(queryClient, options);
  const unsubscribe = first.subscribe(() => {});
  unsubscribe();
  const second = new QueryObserver(queryClient, options);
  const unsubscribeSecond = second.subscribe(() => {});
  const pending = queryClient.fetchQuery(options);
  assert.equal(calls, 1);
  finish('done');
  assert.equal(await pending, 'done');
  assert.equal(await queryClient.fetchQuery(options), 'done');
  assert.equal(calls, 1);
  unsubscribeSecond();
  queryClient.clear();
});

test('late results cannot replace data for a different student or range', async () => {
  let finish;
  const old = queryClient.fetchQuery({ queryKey: ['student', 1, 'skill', 'all'], queryFn: () => new Promise(resolve => { finish = resolve; }) });
  await queryClient.fetchQuery({ queryKey: ['student', 2, 'skill', '7d'], queryFn: async () => 'current' });
  finish('old');
  await old;
  assert.equal(queryClient.getQueryData(['student', 2, 'skill', '7d']), 'current');
  queryClient.clear();
});

test('invalidating shared class data refreshes it; failed reads are retryable explicitly', async () => {
  let calls = 0;
  const options = { queryKey: ['class', 390], queryFn: async () => ++calls };
  assert.equal(await queryClient.fetchQuery(options), 1);
  assert.equal(await queryClient.fetchQuery(options), 1);
  await queryClient.invalidateQueries({ queryKey: ['class', 390] });
  assert.equal(await queryClient.fetchQuery(options), 2);
  let failures = 0;
  const failing = { queryKey: ['failure'], queryFn: async () => { failures++; throw new Error('offline'); } };
  await assert.rejects(queryClient.fetchQuery(failing), /offline/);
  assert.equal(failures, 1);
  await assert.rejects(queryClient.fetchQuery(failing), /offline/);
  assert.equal(failures, 2);
  queryClient.clear();
});

test('roster and student navigation reuse the actual shared context requests', async () => {
  const navigationSource = await readFile(new URL('../src/services/navigation.ts', import.meta.url), 'utf8');
  const navigationJS = ts.transpileModule(navigationSource, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
    .replace("'axios'", JSON.stringify(import.meta.resolve('axios')))
    .replace("'../lib/queryClient'", JSON.stringify(clientModule));
  const { loadClass, loadRoster } = await import(`data:text/javascript;base64,${Buffer.from(navigationJS).toString('base64')}`);
  const originalGet = axios.get;
  const requests = [];
  axios.get = async url => { requests.push(url); return { data: url.endsWith('/students') ? [{ user_id: 1, name: 'An' }] : { id: 390, name: 'Lớp' } }; };
  try {
    const signal = new AbortController().signal;
    await Promise.all([loadClass(390, signal), loadRoster(390, signal)]);
    await Promise.all([loadClass(390, signal), loadRoster(390, signal)]);
    assert.deepEqual(requests, ['/api/v1/teacher/classes/390', '/api/v1/teacher/classes/390/students']);
    const cancelled = new AbortController(); cancelled.abort();
    await assert.rejects(loadClass(390, cancelled.signal), error => error.name === 'AbortError');
    assert.equal(requests.length, 2);
  } finally { axios.get = originalGet; queryClient.clear(); }
});
