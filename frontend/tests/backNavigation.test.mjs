import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/navigation.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { detailBackTarget } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`);

test('detail back link returns to the originating student list with its filters', () => {
  assert.equal(detailBackTarget('/student/students/47', '?tab=submissions', '/student/students?sort=name_desc&page=3'),
    '/student/students?sort=name_desc&page=3');
});

test('direct detail links use a useful parent page', () => {
  assert.equal(detailBackTarget('/student/students/47', '?class=12&list=q%3Dabc&roster=alert%3DSTUCK'),
    '/student/classes/12/students?alert=STUCK&list=q%3Dabc');
  assert.equal(detailBackTarget('/teacher/contests/8', ''), '/teacher/contests');
  assert.equal(detailBackTarget('/teacher/sessions/9', '?list=page%3D2', undefined, 12),
    '/teacher/classes/12/sessions?list=page%3D2');
  assert.equal(detailBackTarget('/teacher/home', ''), null);
});

test('back link ignores unsafe or self-referential origins', () => {
  assert.equal(detailBackTarget('/teacher/contests/8', '', '//other.example'), '/teacher/contests');
  assert.equal(detailBackTarget('/teacher/contests/8', '', '/teacher/contests/8'), '/teacher/contests');
});
