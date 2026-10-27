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
