export interface BloomRadarData {
  A_Nho: number;
  B_Hieu: number;
  C_VanDung: number;
  D_PhanTich: number;
  E_DanhGia: number;
  F_DacBiet: number;
}

export interface SkillTreeNodeData {
  topic_id: number;
  key: string;
  name: string;
  category: string;
  mastery_score: number;
  status: 'GREEN' | 'YELLOW' | 'RED' | 'LOCKED';
}

export interface SkillTreeResponseData {
  user_id: number;
  student_name: string;
  bloom_radar: BloomRadarData;
  skill_tree_nodes: SkillTreeNodeData[];
}

export interface CodeDoctorDiagnosisData {
  error_category: string;
  advice?: string;
  summary?: string;
  guiding_question?: string;
  actionable_hint?: string;
}

export interface CodeDoctorResponseData {
  submission_id: number;
  user_id: number;
  problem_name: string;
  diagnosis: CodeDoctorDiagnosisData;
}

export type JobStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface JobCreateResponseData {
  job_id: string;
  status: JobStatus;
  message: string;
  result?: any;
}

export interface JobStatusResponseData {
  job_id: string;
  job_type: string;
  status: JobStatus;
  progress: number;
  result?: any;
  error?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  deadline_at?: string | null;
}

export interface FailedSubmissionItem {
  submission_id: number;
  problem_id: number;
  problem_code: string;
  problem_name: string;
  result: string;
  status?: string;
  date?: string;
  points: number;
  language_id?: number;
}

export interface TestCaseDetailItem {
  case: number;
  status: string;
  time?: number | null;
  memory?: number | null;
  points?: number | null;
  total?: number | null;
  feedback?: string | null;
  output?: string | null;
}

export interface SubmissionDetailResponseData {
  submission_id: number;
  user_id: number;
  problem_id: number;
  problem_code: string;
  problem_name: string;
  problem_description: string;
  time_limit: number;
  memory_limit: number;
  problem_points: number;
  result: string;
  status?: string | null;
  date?: string | null;
  time?: number | null;
  memory?: number | null;
  points: number;
  language_name: string;
  source_code: string;
  testcases: TestCaseDetailItem[];
}

export interface HeatmapStudentRowData {
  user_id: number;
  student_name: string;
  scores: number[];
  alerts: string[];
}

export interface ClassHeatmapResponseData {
  organization_id: number;
  organization_name: string;
  columns: string[];
  students: HeatmapStudentRowData[];
  class_averages: number[];
}

// Tag Completion Analytics & Learning Advisor

export type TagStatus = 'MASTERED' | 'PRACTICING' | 'NEEDS_IMPROVEMENT' | 'UNATTEMPTED';

export type TagWeight = 'small' | 'medium' | 'large';

export interface TagSubmissionStatData {
  total_submissions: number;
  ac_count: number;
  wa_count: number;
  tle_count: number;
  other_count: number;
  ac_rate: number;
  wa_rate: number;
  tle_rate: number;
  primary_error: string | null;
}

export interface TagMetricItemData {
  tag_id: number;
  key: string;
  name: string;
  total_problems: number;
  ac_problems: number;
  completion_rate: number;
  tag_weight: TagWeight;
  submissions_stat: TagSubmissionStatData;
  status: TagStatus;
}

export interface TagAnalyticsSummaryData {
  total_problems_in_system: number;
  total_solved_unique: number;
  total_submissions_7d: number;
}

export interface TagAnalyticsResponseData {
  user_id: number;
  student_name: string;
  summary: TagAnalyticsSummaryData;
  tags: TagMetricItemData[];
}

export interface Recent7DaysSummaryData {
  submissions_count: number;
  active_tags: string[];
}

export interface AICommentaryResponseData {
  commentary: string;
  recent_7days_summary: Recent7DaysSummaryData;
  recommended_tags: string[];
  generated_at: string;
}

// ==============================================================================
// F2.1 / F2.2: Teacher Dashboard: Class Heatmap & Student Detail
// ==============================================================================

export interface ClassSummaryData {
  id: number;
  name: string;
  member_count: number;
}

export interface StudentSearchItemData {
  user_id: number;
  name: string;
  username: string;
  points: number;
  problem_count: number;
}

export interface StudentBloomScoreData {
  group_id: number;
  label: string;
  score: number;
}

export interface StudentDetailSummaryData {
  total_problems_in_system: number;
  total_solved_unique: number;
  total_submissions_7d: number;
}

export interface StudentDetailResponseData {
  user_id: number;
  name: string;
  username: string;
  points: number;
  performance_points: number;
  problem_count: number;
  display_rank: string;
  organizations: string[];
  bloom_scores: StudentBloomScoreData[];
  alerts: string[];
  last_submission_at: string | null;
  summary: StudentDetailSummaryData;
}
