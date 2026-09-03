import axios from 'axios';
import {
  SkillTreeResponseData,
  CodeDoctorResponseData,
  ClassHeatmapResponseData,
  TagAnalyticsResponseData,
  AICommentaryResponseData,
  StudentDetailResponseData
} from '../types';

const API_BASE_URL = '/api/v1';

export const fetchSkillTree = async (userId: number): Promise<SkillTreeResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/student/skill-tree`, {
    params: { user_id: userId }
  });
  return res.data;
};

export const fetchTagAnalytics = async (userId: number): Promise<TagAnalyticsResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/student/analytics/tags`, {
    params: { user_id: userId }
  });
  return res.data;
};

export const fetchAICommentary = async (userId: number, forceRefresh: boolean = false): Promise<AICommentaryResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/student/analytics/ai-commentary`, {
    params: { user_id: userId, force_refresh: forceRefresh }
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

export const fetchClassHeatmap = async (orgId: number): Promise<ClassHeatmapResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/teacher/class/${orgId}/heatmap`);
  return res.data;
};

export const searchStudents = async (query: string) => {
  const res = await axios.get(`${API_BASE_URL}/teacher/students/search?q=${encodeURIComponent(query)}`);
  return res.data;
};

export const fetchStudentDetail = async (studentId: number): Promise<StudentDetailResponseData> => {
  const res = await axios.get(`${API_BASE_URL}/teacher/students/${studentId}/detail`);
  return res.data;
};
