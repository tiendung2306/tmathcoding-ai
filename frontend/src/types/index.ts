export type TimeRange = '1d' | '7d' | '30d' | '1y' | 'all';

export interface PillarReasonItem {
  label: string;
  val: number;
  type: 'base' | 'bonus' | 'penalty';
  desc?: string;
}

export interface PillarBreakdownItem {
  score: number;
  base_score: number;
  precision_mod: number;
  efficiency_mod: number;
  code_quality_mod: number;
  ac_count: number;
  total_subs: number;
  avg_time_ratio: number;
  breakdown_items: PillarReasonItem[];
}

export interface BloomRadarData {
  time_range?: TimeRange;
  quy_hoach_dong?: number;
  cau_truc_du_lieu?: number;
  xu_ly_xau?: number;
  ham_co_ban?: number;
  toan_hoc?: number;
  hinh_hoc?: number;
  do_thi?: number;
  tham_lam?: number;
  // Backward compatibility
  A_Nho?: number;
  B_Hieu?: number;
  C_VanDung?: number;
  D_PhanTich?: number;
  E_DanhGia?: number;
  F_DacBiet?: number;
  breakdown?: Record<string, PillarBreakdownItem>;
}

export interface AlgorithmRadarData {
  time_range: TimeRange;
  quy_hoach_dong: number;
  cau_truc_du_lieu: number;
  xu_ly_xau: number;
  ham_co_ban: number;
  toan_hoc: number;
  hinh_hoc: number;
  do_thi: number;
  tham_lam: number;
  breakdown?: Record<string, PillarBreakdownItem>;
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
  time_range?: TimeRange;
  bloom_radar: BloomRadarData;
  algorithm_radar?: AlgorithmRadarData | null;
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
  time_range?: TimeRange;
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
  time_range?: TimeRange;
  total_submissions_period?: number;
}

export interface TagAnalyticsResponseData {
  user_id: number;
  student_name: string;
  time_range?: TimeRange;
  summary: TagAnalyticsSummaryData;
  tags: TagMetricItemData[];
}

export interface Recent7DaysSummaryData {
  submissions_count: number;
  active_tags: string[];
}

export interface RecentPeriodSummaryData {
  time_range: TimeRange;
  submissions_count: number;
  active_tags: string[];
}

export interface AICommentaryResponseData {
  commentary: string;
  time_range?: TimeRange;
  recent_7days_summary: Recent7DaysSummaryData;
  period_summary?: RecentPeriodSummaryData;
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
  time_range?: TimeRange;
  total_submissions_period?: number;
}

export interface ClassStudentItemData {
  user_id: number;
  name: string;
  username: string;
  points: number;
  problem_count: number;
  display_rank: string;
  alerts: string[];
  last_submission_at: string | null;
}

export interface StudentRecentSubmissionData {
  id: number;
  date: string;
  result: string;
  points: number;
  problem_id: number;
  problem_code: string;
  problem_name: string;
}

export interface StudentDetailResponseData {
  user_id: number;
  name: string;
  username: string;
  time_range?: TimeRange;
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

// ==============================================================================
// F3.1: Admin Auto-Tagging Pipeline & Dashboard
// ==============================================================================

export interface AutoTagRecentProblemItemData {
  id: number;
  problem_id: number;
  problem_code: string;
  problem_name: string;
  primary_tag_id: number;
  primary_tag_name: string;
  secondary_tag_ids: number[];
  bloom_group_id: number | null;
  bloom_group_name: string | null;
  reasoning: string;
  model: string;
  created_at: string;
}

export interface AutoTagCurrentBatchData {
  total: number;
  processed: number;
  successful: number;
  failed: number;
  started_at: string;
}

export interface AutoTagStatusResponseData {
  total_problems: number;
  tagged_problems: number;
  untagged_problems: number;
  progress_percentage: number;
  is_running: boolean;
  current_batch: AutoTagCurrentBatchData | null;
  recent_tags: AutoTagRecentProblemItemData[];
}

export interface AutoTagBatchRunResponseData {
  status: string;
  message: string;
  batch_size: number;
}

