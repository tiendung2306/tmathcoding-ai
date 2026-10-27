import { apiClient } from '../lib/apiClient';
import type { SkillPage, SkillProblem, SkillProblemDetail } from '../types';
import {
  TimeRange,
  SkillTreeResponseData,
  ClassHeatmapResponseData,
  TagAnalyticsResponseData,
  AICommentaryResponseData,
  StudentDetailResponseData,
  ClassStudentItemData,
  StudentSubmissionHistoryPageData,
  AutoTagStatusResponseData,
  AutoTagBatchRunResponseData,
  SubmissionDetailResponseData,
  JobCreateResponseData,
  JobStatusResponseData,
  TeacherContestPageData,
  TeacherContestData,
  ContestLiveSubmissionsData,
  ContestOrganizationData,
} from '../types';

const API_BASE_URL = '/api/v1';

export async function fetchSkillProblems(tagId: number, userId: number, timeRange: TimeRange, status: string, q: string, page: number, signal?: AbortSignal): Promise<SkillPage<SkillProblem>> {
  return (await apiClient.get(`${API_BASE_URL}/student/skill-tags/${tagId}/problems`, {
    params: { user_id: userId, time_range: timeRange, status, q, page }, signal, timeout: 30_000,
  })).data;
}

export async function fetchSkillProblemDetail(problemId: number, userId: number, timeRange: TimeRange, page: number, signal?: AbortSignal): Promise<SkillProblemDetail> {
  return (await apiClient.get(`${API_BASE_URL}/student/skill-problems/${problemId}`, {
    params: { user_id: userId, time_range: timeRange, page }, signal, timeout: 30_000,
  })).data;
}

export const fetchSkillTree = async (userId: number, timeRange: TimeRange = 'all', signal?: AbortSignal): Promise<SkillTreeResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/student/skill-tree`, {
    params: { user_id: userId, time_range: timeRange }, signal, timeout: 30_000,
  });
  return res.data;
};

export const fetchTagAnalytics = async (userId: number, timeRange: TimeRange = 'all'): Promise<TagAnalyticsResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/student/analytics/tags`, {
    params: { user_id: userId, time_range: timeRange }, timeout: 30_000,
  });
  return res.data;
};

export const fetchAICommentary = async (
  userId: number,
  timeRange: TimeRange = 'all',
  forceRefresh: boolean = false
): Promise<AICommentaryResponseData | null> => {
  const res = await apiClient.get(`${API_BASE_URL}/student/analytics/ai-commentary`, {
    params: { user_id: userId, time_range: timeRange, force_refresh: forceRefresh }, timeout: 250_000,
  });
  return res.data;
};

export const requestCodeDoctor = async (submissionId: number, forceRefresh: boolean = false): Promise<JobCreateResponseData> => {
  const res = await apiClient.post(`${API_BASE_URL}/student/code-doctor/diagnose`, {
    submission_id: submissionId,
    force_refresh: forceRefresh
  });
  return res.data;
};

export const fetchJobStatus = async (jobId: string): Promise<JobStatusResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/jobs/${jobId}`);
  return res.data;
};

export const fetchSubmissionDetail = async (submissionId: number): Promise<SubmissionDetailResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/student/submissions/${submissionId}/detail`);
  return res.data;
};

export async function fetchTeacherContests(params: {
  state: 'active' | 'ended';
  q?: string;
  cursor?: string | null;
  limit?: number;
}, signal?: AbortSignal): Promise<TeacherContestPageData> {
  return (await apiClient.get<TeacherContestPageData>(`${API_BASE_URL}/teacher/my-contests`, {
    params, signal, timeout: 30_000,
  })).data;
}

export async function fetchTeacherContest(contestId: number, signal?: AbortSignal): Promise<TeacherContestData> {
  return (await apiClient.get<TeacherContestData>(`${API_BASE_URL}/teacher/my-contests/${contestId}`, {
    signal, timeout: 30_000,
  })).data;
}

export async function fetchContestLiveSubmissions(contestId: number, signal?: AbortSignal): Promise<ContestLiveSubmissionsData> {
  return (await apiClient.get<ContestLiveSubmissionsData>(`${API_BASE_URL}/virtual-class/contests/${contestId}/live-submissions`, {
    signal, timeout: 30_000,
  })).data;
}

export async function fetchContestOrganizations(signal?: AbortSignal): Promise<ContestOrganizationData[]> {
  return (await apiClient.get<ContestOrganizationData[]>(`${API_BASE_URL}/teacher/contest-organizations`, {
    signal, timeout: 30_000,
  })).data;
}

export const fetchClassHeatmap = async (orgId: number, timeRange: TimeRange = 'all'): Promise<ClassHeatmapResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/teacher/class/${orgId}/heatmap`, {
    params: { time_range: timeRange }
  });
  return res.data;
};

export const searchStudents = async (query: string) => {
  const res = await apiClient.get(`${API_BASE_URL}/teacher/students/search?q=${encodeURIComponent(query)}`);
  return res.data;
};

export const fetchStudentDetail = async (studentId: number, timeRange: TimeRange = 'all'): Promise<StudentDetailResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/teacher/students/${studentId}/detail`, {
    params: { time_range: timeRange }
  });
  return res.data;
};

export const fetchClassStudents = async (orgId: number): Promise<ClassStudentItemData[]> => {
  const res = await apiClient.get(`${API_BASE_URL}/teacher/classes/${orgId}/students`);
  return res.data;
};

export const fetchStudentSubmissionHistory = async (
  userId: number,
  cursor: string | null,
): Promise<StudentSubmissionHistoryPageData> => {
  const res = await apiClient.get<StudentSubmissionHistoryPageData>(`${API_BASE_URL}/student/submissions/history`, {
    params: { user_id: userId, cursor: cursor || undefined, page_size: 24 },
    timeout: 30_000,
  });
  return res.data;
};

export const fetchAutoTagStatus = async (): Promise<AutoTagStatusResponseData> => {
  const res = await apiClient.get(`${API_BASE_URL}/admin/auto-tag/status`);
  return res.data;
};

export const runAutoTagBatch = async (batchSize: number = 10): Promise<AutoTagBatchRunResponseData> => {
  const res = await apiClient.post(`${API_BASE_URL}/admin/auto-tag/run-batch`, {
    batch_size: batchSize
  });
  return res.data;
};


// Virtual Class API
export const getVirtualClassSessions = async (orgId: number) => {
  const res = await apiClient.get(`${API_BASE_URL}/virtual-class/${orgId}/sessions`);
  return res.data;
};

export const stopVirtualClass = async (sessionId: number) => {
  const res = await apiClient.post(`${API_BASE_URL}/virtual-class/sessions/${sessionId}/stop`);
  return res.data;
};

export const fetchLiveSubmissions = async (sessionId: number, cursor: string | null = null, signal?: AbortSignal) => {
  const res = await apiClient.get(`${API_BASE_URL}/virtual-class/sessions/${sessionId}/live-submissions`, {
    params: cursor ? { cursor } : {}, signal,
  });
  return res.data;
};
