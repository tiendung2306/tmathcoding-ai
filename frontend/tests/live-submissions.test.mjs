import test from 'node:test';
import assert from 'node:assert/strict';
import { applyLiveSubmissionEvents, shouldResetLiveFeed } from '../src/lib/liveSubmissions.mjs';

const record = (id, result, date = '2026-10-12T00:00:00Z') => ({ id, result, date });

test('live changes insert late rows, update verdicts, remove deletes, and deduplicate replays', () => {
  const initial = [record(8, 'AC'), record(3, 'WA')];
  const events = [
    { kind: 'created', submission_id: 12, record: record(12, 'WA') },
    { kind: 'updated', submission_id: 8, record: record(8, 'WA') },
    { kind: 'deleted', submission_id: 3, record: null },
    { kind: 'created', submission_id: 12, record: record(12, 'WA') },
  ];

  const updated = applyLiveSubmissionEvents(initial, events);
  assert.deepEqual(updated.map(item => item.id), [12, 8]);
  assert.equal(updated[1].result, 'WA');
});

test('snapshot replaces stale rows and ties sort by submission id', () => {
  const result = applyLiveSubmissionEvents([record(99, 'AC')], [
    { kind: 'created', submission_id: 4, record: record(4, 'AC') },
    { kind: 'created', submission_id: 7, record: record(7, 'AC') },
  ], true);
  assert.deepEqual(result.map(item => item.id), [7, 4]);
});

test('retrying the same session preserves its live feed; switching sessions resets it', () => {
  const sessionId = 24;
  assert.equal(shouldResetLiveFeed(sessionId, sessionId), false);
  assert.equal(shouldResetLiveFeed(sessionId, sessionId + 1), true);
  assert.equal(shouldResetLiveFeed(null, sessionId), true);
});
