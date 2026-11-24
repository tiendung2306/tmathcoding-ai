import type {
  DoctorApproachInfoData,
  DoctorConfidence,
  DoctorDirection,
  DoctorLogicErrorData,
  DoctorSeverity,
} from '../types';

export const CODE_LINE_HEIGHT_PX = 24;

export const DIRECTION_LABEL: Record<DoctorDirection, string> = {
  on_track: 'Đúng hướng',
  partially: 'Đúng một phần',
  off_track: 'Chưa đúng hướng',
  unknown: 'Chưa đủ dữ liệu',
};

export const CONFIDENCE_LABEL: Record<DoctorConfidence, string> = {
  high: 'cao',
  medium: 'trung bình',
  low: 'thấp',
};

export const SEVERITY_LABEL: Record<DoctorSeverity, string> = {
  high: 'nặng',
  medium: 'vừa',
  low: 'nhẹ',
};

export const EVIDENCE_LABEL: Record<DoctorLogicErrorData['evidence'], string> = {
  static: 'phân tích tĩnh',
  reference_diff: 'so với lời giải AC',
  model: 'AI đọc mã',
};

/** One line of context for an approach: complexity, loop structure, cluster size. */
export function approachDetail(approach: DoctorApproachInfoData | null | undefined): string {
  if (!approach) return '';
  const parts: string[] = [];
  if (approach.same_control_flow === true) parts.push('cùng cấu trúc vòng lặp');
  if (approach.same_control_flow === false) parts.push('khác cấu trúc vòng lặp');
  if (approach.member_count > 1) parts.push(`${approach.member_count} bài AC`);
  if (approach.status === 'approved') parts.push('đã duyệt');
  return parts.join(', ');
}

/** Valid, sorted, de-duplicated line numbers inside the submission. */
export function normalizeLines(lines: number[] | null | undefined, lineCount: number): number[] {
  return [...new Set((lines ?? []).filter((line) => Number.isInteger(line) && line >= 1 && line <= lineCount))]
    .sort((a, b) => a - b);
}

/** Scroll offset that puts the line near the top of the code pane, keeping one line of context. */
export function codeLineOffset(line: number): number {
  return Math.max(0, (line - 2) * CODE_LINE_HEIGHT_PX);
}
