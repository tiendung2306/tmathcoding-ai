import axios from 'axios';
import { SkillConfigState, SkillDocument, SkillDefinition } from '../types';

const base = '/api/v1/admin/skill-config';
export const loadSkillConfig = async (): Promise<SkillConfigState> => (await axios.get(base, {timeout: 30_000})).data;
export const saveSkillConfiguration = async (revision: number, document: SkillDocument): Promise<SkillConfigState> => (await axios.put(base, {revision, document}, {timeout: 30_000})).data;
export interface Suggestion { tag_id: number; node_id: string; reason: string }
export interface SkillProposal extends Suggestion { source_node_id: string; status: 'pending' | 'assigned' | 'rejected'; nodes: SkillDefinition[] }
export const rejectSkillProposals = async (document: SkillDocument, tag_ids: number[]): Promise<{proposals: SkillProposal[]}> => (await axios.patch(`${base}/proposals`, {document, action: 'reject', tag_ids}, {timeout: 30_000})).data;
export const approveSkillProposals = async (revision: number, document: SkillDocument, tag_ids: number[]): Promise<SkillConfigState> => (await axios.patch(`${base}/proposals`, {revision, document, action: 'approve', tag_ids}, {timeout: 30_000})).data;
export const suggestSkillTags = async (document: SkillDocument, signal?: AbortSignal, runId?: string): Promise<{suggestions: Suggestion[]; proposals: SkillProposal[]; remaining: number; batch_size: number}> => (await axios.post(`${base}/suggest`, document, {timeout: 200_000, signal, params: {run_id: runId}})).data;
export const cancelSkillAI = async (runId: string) => axios.delete(`${base}/suggest/${encodeURIComponent(runId)}`, {timeout: 10_000});
export function skillError(error: unknown) {
  const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
  return typeof detail === 'string' ? detail : error instanceof Error && error.message === 'invalid student' ? 'Nhập ID học sinh là số nguyên dương.' : 'Không thể hoàn tất thao tác. Hãy thử lại.';
}
