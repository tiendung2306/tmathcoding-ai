import { apiClient } from '../lib/apiClient';

export interface ScoreItem { problem_id: number; code: string; title: string; grade: string | null; points: number; difficulty: number | null; attempted: number; solved: number; method: string }
export interface StudentScore { ready: boolean; run_id: string; as_of: string; points: number; solved_count: number; unscored_count: number; page: number; total_pages: number; items: Pick<ScoreItem, 'problem_id' | 'code' | 'title' | 'grade' | 'points'>[] }
const base = '/api/v1/admin/scoring';
export async function studentScore(id: number, page: number): Promise<StudentScore | null> { return (await apiClient.get(`${base}/students/${id}`, { params: { page }, timeout: 15000 })).data; }
export function scoreDate(value: string | null) { return value ? new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleString('vi-VN') : ''; }
