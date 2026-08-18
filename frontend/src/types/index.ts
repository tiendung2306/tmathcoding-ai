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
  summary: string;
  guiding_question: string;
  actionable_hint: string;
}

export interface CodeDoctorResponseData {
  submission_id: number;
  user_id: number;
  problem_name: string;
  diagnosis: CodeDoctorDiagnosisData;
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
