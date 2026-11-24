import { apiClient } from '../lib/apiClient';
import type { SkillPage, SkillProblem, SkillProblemDetail } from '../types';
import {
  TimeRange,
  SkillTreeResponseData,
  TagAnalyticsResponseData,
  AICommentaryResponseData,
  StudentSubmissionHistoryPageData,
  AutoTagStatusResponseData,
  AutoTagBatchRunResponseData,
  SubmissionDetailResponseData,
  JobCreateResponseData,
  DoctorFeedbackRating,
  JobStatusResponseData,
  TeacherContestPageData,
  TeacherContestData,
  ContestLiveSubmissionsData,
  ContestOrganizationData,
  ContestStudentData,
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

export const submitCodeDoctorFeedback = async (
  submissionId: number, rating: DoctorFeedbackRating, note?: string,
): Promise<void> => {
  await apiClient.post(`${API_BASE_URL}/student/code-doctor/submissions/${submissionId}/feedback`, { rating, note });
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
  state: 'active' | 'upcoming' | 'ended';
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

export async function fetchContestLiveSubmissions(contestId: number, classId?: number | null, signal?: AbortSignal): Promise<ContestLiveSubmissionsData> {
  return (await apiClient.get<ContestLiveSubmissionsData>(`${API_BASE_URL}/virtual-class/contests/${contestId}/live-submissions`, {
    params: classId ? { class_id: classId } : {}, signal, timeout: 30_000,
  })).data;
}

export async function fetchContestOrganizations(signal?: AbortSignal): Promise<ContestOrganizationData[]> {
  return (await apiClient.get<ContestOrganizationData[]>(`${API_BASE_URL}/teacher/contest-organizations`, {
    signal, timeout: 30_000,
  })).data;
}

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


// Class sessions ("phiên học") are contests mapped to a class in the Source API.
export async function fetchContestStudents(contestId: number, classId?: number | null, signal?: AbortSignal): Promise<ContestStudentData[]> {
  return (await apiClient.get<ContestStudentData[]>(`${API_BASE_URL}/teacher/my-contests/${contestId}/students`, {
    params: classId ? { class_id: classId } : {}, signal, timeout: 30_000,
  })).data;
}
