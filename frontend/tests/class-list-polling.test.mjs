import test from 'node:test';
import assert from 'node:assert/strict';
import { isSameClassListQuery } from '../src/lib/classListPolling.mjs';

const query = {
  page: 1,
  page_size: 24,
  q: '',
  sort_by: 'creation_date',
  sort_order: 'desc',
  starred_only: false,
};

test('poll response applies only to the complete query that started it', () => {
  assert.equal(isSameClassListQuery(query, { ...query }), true);
  for (const update of [
    { page: 2 },
    { q: 'algebra' },
    { sort_by: 'name' },
    { sort_order: 'asc' },
    { starred_only: true },
    { page_size: 50 },
  ]) {
    assert.equal(isSameClassListQuery(query, { ...query, ...update }), false);
  }
});
