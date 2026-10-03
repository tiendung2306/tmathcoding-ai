import axios from 'axios';
import { queryClient } from '../lib/queryClient';
import { ClassStudentItemData } from '../types';
export interface ClassContext { id: number; name: string }
export interface SessionDetail { id: number; org_id: number; name: string; class_name: string; start_time: string; end_time: string | null }
export async function loadClass(id: number, signal: AbortSignal): Promise<ClassContext> {
  signal.throwIfAborted();
  return queryClient.fetchQuery({
    queryKey: ['class', id],
    queryFn: async () => (await axios.get<ClassContext>(`/api/v1/teacher/classes/${id}`, { timeout: 30_000 })).data,
  });
}
export async function loadRoster(id: number, signal: AbortSignal): Promise<ClassStudentItemData[]> {
  signal.throwIfAborted();
  return queryClient.fetchQuery({
    queryKey: ['class', id, 'students'],
    queryFn: async () => (await axios.get<ClassStudentItemData[]>(`/api/v1/teacher/classes/${id}/students`, { timeout: 30_000 })).data,
  });
}
export async function loadProfile(id: number, signal: AbortSignal): Promise<{ id: number; name: string }> {
  signal.throwIfAborted();
  return queryClient.fetchQuery({
    queryKey: ['student', id, 'profile'],
    queryFn: async () => (await axios.get<{ id: number; name: string }>(`/api/v1/teacher/students/${id}`, { timeout: 30_000 })).data,
  });
}
export async function loadSession(id: number, signal: AbortSignal): Promise<SessionDetail> {
  return (await axios.get(`/api/v1/virtual-class/sessions/${id}`, { signal })).data;
}
export async function routeRequest<T>(request: () => Promise<T>): Promise<T> {
  try { return await request(); }
  catch (error) {
    if (error instanceof Response) throw error;
    if (axios.isCancel(error)) throw error;
    const status = axios.isAxiosError(error) ? error.response?.status || 503 : 503;
    throw new Response('Không tải được dữ liệu.', { status });
  }
}
