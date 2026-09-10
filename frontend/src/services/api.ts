import axios from 'axios';
import {
  TimeRange,
  SkillTreeResponseData,
  CodeDoctorResponseData,
  ClassHeatmapResponseData,
  TagAnalyticsResponseData,
  AICommentaryResponseData,
  StudentDetailResponseData,
  ClassStudentItemData,
  StudentRecentSubmissionData,
  AutoTagStatusResponseData,
  AutoTagBatchRunResponseData
} from '../types';

const API_BASE_URL = '/api/v1';

export const fetchSkillTree = async (userId: number, timeRange: TimeRange = 'all'): Promise<SkillTreeResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/student/skill-tree`, {
    params: { user_id: userId, time_range: timeRange }
  });
  return res.data;
};

export const fetchTagAnalytics = async (userId: number, timeRange: TimeRange = 'all'): Promise<TagAnalyticsResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/student/analytics/tags`, {
    params: { user_id: userId, time_range: timeRange }
  });
  return res.data;
};

export const fetchAICommentary = async (
  userId: number,
  timeRange: TimeRange = 'all',
  forceRefresh: boolean = false
): Promise<AICommentaryResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/student/analytics/ai-commentary`, {
    params: { user_id: userId, time_range: timeRange, force_refresh: forceRefresh }
  });
  return res.data;
};

export const requestCodeDoctor = async (submissionId: number): Promise<CodeDoctorResponseData> => {
  const res = await axios.post(`${API_BASE_URL}/student/code-doctor/diagnose`, {
    submission_id: submissionId
  });
  return res.data;
};

export const fetchTeacherClasses = async () => {
  const res = await axios.get(`${API_BASE_URL}/teacher/my-classes`);
  return res.data;
};

export const fetchClassHeatmap = async (orgId: number, timeRange: TimeRange = 'all'): Promise<ClassHeatmapResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/teacher/class/${orgId}/heatmap`, {
    params: { time_range: timeRange }
  });
  return res.data;
};

export const searchStudents = async (query: string) => {
  const res = await axios.get(`${API_BASE_URL}/teacher/students/search?q=${encodeURIComponent(query)}`);
  return res.data;
};

export const fetchStudentDetail = async (studentId: number, timeRange: TimeRange = 'all'): Promise<StudentDetailResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/teacher/students/${studentId}/detail`, {
    params: { time_range: timeRange }
  });
  return res.data;
};

export const fetchClassStudents = async (orgId: number): Promise<ClassStudentItemData[]> => {
  const res = await axios.get(`${API_BASE_URL}/teacher/classes/${orgId}/students`);
  return res.data;
};

export const fetchRecentSubmissions = async (userId: number, onlyFailed: boolean = false, limit: number = 10): Promise<StudentRecentSubmissionData[]> => {
  const res = await axios.get(`${API_BASE_URL}/student/submissions/recent`, {
    params: { user_id: userId, only_failed: onlyFailed, limit }
  });
  return res.data;
};

export const fetchAutoTagStatus = async (): Promise<AutoTagStatusResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/admin/auto-tag/status`);
  return res.data;
};

export const runAutoTagBatch = async (batchSize: number = 10): Promise<AutoTagBatchRunResponseData> => {
  const res = await axios.post(`${API_BASE_URL}/admin/auto-tag/run-batch`, {
    batch_size: batchSize
  });
  return res.data;
};

