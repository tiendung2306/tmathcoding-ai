import { ClassListQuery, ClassSortField } from '../types';

const sorts: ClassSortField[] = ['creation_date', 'name', 'member_count', 'id', 'last_session_at'];
export function positiveId(value: string | null | undefined): number {
  if (!value || !/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Response('Địa chỉ không hợp lệ.', { status: 404 });
  return Number(value);
}
export function classQuery(params: URLSearchParams): ClassListQuery {
  const integer = (key: string, fallback: number, max: number) => {
    const value = Number(params.get(key));
    return Number.isInteger(value) && value > 0 ? Math.min(value, max) : fallback;
  };
  const sort = params.get('sort') as ClassSortField;
  const size = integer('size', 24, 100);
  return { page: integer('page', 1, 100000), page_size: [12, 24, 48, 100].includes(size) ? size : 24, q: (params.get('q') || '').trim().slice(0, 128), sort_by: sorts.includes(sort) ? sort : 'creation_date', sort_order: params.get('order') === 'asc' ? 'asc' : 'desc', starred_only: params.get('starred') === '1' };
}
export function classSearch(query: ClassListQuery): string {
  const params = new URLSearchParams();
  if (query.page !== 1) params.set('page', String(query.page));
  if (query.page_size !== 24) params.set('size', String(query.page_size));
  if (query.q) params.set('q', query.q);
  if (query.sort_by !== 'creation_date') params.set('sort', query.sort_by);
  if (query.sort_order !== 'desc') params.set('order', query.sort_order);
  if (query.starred_only) params.set('starred', '1');
  return params.toString();
}
export function classListUrl(area: 'student' | 'teacher', list = ''): string {
  const search = classSearch(classQuery(new URLSearchParams(list)));
  return `/${area}/classes${search ? `?${search}` : ''}`;
}
export function studentUrl(id: number, classId?: number, list = '', roster = '', range = 'all'): string {
  const params = new URLSearchParams();
  if (classId) params.set('class', String(classId));
  if (list) params.set('list', list);
  if (roster) params.set('roster', roster);
  if (range !== 'all') params.set('range', range);
  return `/student/students/${id}${params.size ? `?${params}` : ''}`;
}
export function rosterUrl(classId: number, list = '', roster = ''): string {
  const params = new URLSearchParams(roster);
  if (list) params.set('list', list);
  return `/student/classes/${classId}/students${params.size ? `?${params}` : ''}`;
}
