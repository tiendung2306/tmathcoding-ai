export function positiveId(value: string | null | undefined): number {
  if (!value || !/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Response('Địa chỉ không hợp lệ.', { status: 404 });
  return Number(value);
}
export function studentUrl(id: number, classId?: number, list = '', roster = '', range = '7d'): string {
  const params = new URLSearchParams();
  if (classId) params.set('class', String(classId));
  if (list) params.set('list', list);
  if (roster) params.set('roster', roster);
  if (range !== '7d') params.set('range', range);
  return `/student/students/${id}${params.size ? `?${params}` : ''}`;
}
export function rosterUrl(classId: number, list = '', roster = ''): string {
  const params = new URLSearchParams(roster);
  if (list) params.set('list', list);
  return `/student/classes/${classId}/students${params.size ? `?${params}` : ''}`;
}

export function detailBackTarget(path: string, search: string, from?: unknown, sessionClassId?: number): string | null {
  const params = new URLSearchParams(search);
  let fallback: string | null = null;
  if (/^\/student\/students\/\d+$/.test(path)) {
    const classId = Number(params.get('class'));
    fallback = Number.isSafeInteger(classId) && classId > 0
      ? rosterUrl(classId, params.get('list') || '', params.get('roster') || '')
      : '/student/students';
  } else if (/^\/student\/classes\/\d+\/students$/.test(path)) {
    fallback = '/student/students';
  } else if (/^\/teacher\/contests\/\d+$/.test(path)) {
    fallback = '/teacher/contests';
  } else if (/^\/teacher\/sessions\/\d+$/.test(path)) {
    fallback = sessionClassId && Number.isSafeInteger(sessionClassId) && sessionClassId > 0
      ? `/teacher/classes/${sessionClassId}/sessions${params.get('list') ? `?${new URLSearchParams({ list: params.get('list')! })}` : ''}`
      : '/teacher/contests';
  } else if (/^\/teacher\/classes\/\d+\/sessions$/.test(path)) {
    fallback = '/teacher/contests';
  } else if (path === '/admin/skills') {
    fallback = '/admin';
  }
  if (!fallback) return null;
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && from !== path + search
    ? from : fallback;
}
