import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from './load-ts.mjs';

const { formatMemoryKb } = await import(await tsModuleUrl(new URL('../src/lib/utils.ts', import.meta.url)));

test('judge memory (KB) is shown in KB or MB, never KB labelled as MB', () => {
  assert.equal(formatMemoryKb(262144), '256 MB');
  assert.equal(formatMemoryKb(28000), '27.3 MB');
  assert.equal(formatMemoryKb(512), '512 KB');
  assert.equal(formatMemoryKb(null), '—');
});
