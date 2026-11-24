import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from './load-ts.mjs';

const doctor = await import(await tsModuleUrl(new URL('../src/lib/codeDoctor.ts', import.meta.url)));

test('report lines outside the submission are not offered as links', () => {
  assert.deepEqual(doctor.normalizeLines([8, 3, 8, 0, 120, 2.5], 20), [3, 8]);
  assert.deepEqual(doctor.normalizeLines(undefined, 20), []);
});

test('code pane scrolls one line above the target', () => {
  assert.equal(doctor.codeLineOffset(1), 0);
  assert.equal(doctor.codeLineOffset(10), 8 * doctor.CODE_LINE_HEIGHT_PX);
});

test('approach detail names structure match and cluster size', () => {
  assert.equal(
    doctor.approachDetail({ name: 'Mảng cộng dồn', status: 'approved', member_count: 3, same_control_flow: true }),
    'cùng cấu trúc vòng lặp, 3 bài AC, đã duyệt',
  );
  assert.equal(doctor.approachDetail({ name: 'X', status: 'auto', member_count: 1, same_control_flow: null }), '');
  assert.equal(doctor.approachDetail(null), '');
});

test('every direction has Vietnamese copy without em dash', () => {
  for (const label of Object.values(doctor.DIRECTION_LABEL)) assert.ok(!label.includes('—'));
});
