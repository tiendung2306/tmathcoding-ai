import React, { useState } from 'react';
import type { DoctorFeedbackRating, DoctorFindingData, DoctorReportData } from '../types';
import { submitCodeDoctorFeedback } from '../services/api';
import {
  CONFIDENCE_LABEL,
  DIRECTION_LABEL,
  EVIDENCE_LABEL,
  SEVERITY_LABEL,
  approachDetail,
  normalizeLines,
} from '../lib/codeDoctor';
import { Button } from './ui/button';

interface CodeDoctorReportProps {
  submissionId: number;
  report: DoctorReportData;
  lineCount: number;
  onFocusLines: (lines: number[]) => void;
  onReanalyze: () => void;
}

const FEEDBACK_OPTIONS: { rating: DoctorFeedbackRating; label: string }[] = [
  { rating: 'correct', label: 'Đúng' },
  { rating: 'partial', label: 'Đúng một phần' },
  { rating: 'wrong', label: 'Sai' },
];

const DIRECTION_TONE: Record<DoctorReportData['direction'], string> = {
  on_track: 'text-emerald-700',
  partially: 'text-amber-700',
  off_track: 'text-red-700',
  unknown: 'text-text-secondary',
};

function LineLinks({ lines, lineCount, onFocusLines }: { lines: number[]; lineCount: number; onFocusLines: (lines: number[]) => void }) {
  const valid = normalizeLines(lines, lineCount);
  if (valid.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1">
      {valid.map((line) => (
        <button
          key={line}
          type="button"
          onClick={() => onFocusLines(valid)}
          aria-label={`Xem dòng ${line} trong mã nguồn`}
          className="inline-flex min-h-11 items-center rounded-sm px-1 font-mono text-xs font-medium text-brand-primary underline underline-offset-2 hover:text-blue-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:min-h-0 sm:py-0.5"
        >
          dòng {line}
        </button>
      ))}
    </span>
  );
}

function FindingList({ title, items, lineCount, onFocusLines }: {
  title: string; items: DoctorFindingData[]; lineCount: number; onFocusLines: (lines: number[]) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="border-t border-border pt-4">
      <h4 className="text-sm font-semibold text-text-primary">{title}</h4>
      <ul className="mt-2 space-y-2">
        {items.map((item, index) => (
          <li key={index} className="text-sm leading-6 text-text-primary">
            {item.point}
            {item.severity && <span className="ml-1 text-xs text-text-secondary">(mức {SEVERITY_LABEL[item.severity]})</span>}
            {' '}
            <LineLinks lines={item.lines} lineCount={lineCount} onFocusLines={onFocusLines} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export const CodeDoctorReport: React.FC<CodeDoctorReportProps> = ({
  submissionId, report, lineCount, onFocusLines, onReanalyze,
}) => {
  const [feedback, setFeedback] = useState<DoctorFeedbackRating | null>(null);
  const [sending, setSending] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const accepted = report.verdict === 'AC';

  const sendFeedback = async (rating: DoctorFeedbackRating) => {
    setSending(true);
    setFeedbackError(null);
    try {
      await submitCodeDoctorFeedback(submissionId, rating);
      setFeedback(rating);
    } catch (err: any) {
      setFeedbackError(err?.response?.data?.detail || 'Chưa lưu được đánh giá. Vui lòng thử lại.');
    } finally {
      setSending(false);
    }
  };

  const nearest = report.nearest_approach;
  const best = report.best_approach;
  const sameApproach = nearest && best && nearest.approach_id === best.approach_id;

  return (
    <div className="rounded-md border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border pb-3">
        <h3 className="text-base font-semibold text-text-primary">Nhận xét Code Doctor</h3>
        <p className="text-xs text-text-secondary">
          Độ tin cậy {CONFIDENCE_LABEL[report.confidence]}
          {report.model ? `, model ${report.model}` : ''}
        </p>
      </div>

      {report.origin === 'fallback' && (
        <div role="note" className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p>
            AI chưa đọc mã{report.fallback_reason ? `: ${report.fallback_reason}` : '.'} Nội dung dưới đây chỉ dựa trên phân tích tĩnh và so khớp với bài AC.
          </p>
          <Button variant="outline" size="sm" onClick={onReanalyze} className="min-h-11 px-3 text-sm">
            Phân tích lại
          </Button>
        </div>
      )}

      <p className="pt-4 text-sm leading-7 text-text-primary">{report.overview}</p>

      <dl className="mt-4 grid gap-x-6 gap-y-3 border-t border-border pt-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-text-secondary">Hướng làm</dt>
          <dd className={`mt-0.5 font-medium ${DIRECTION_TONE[report.direction]}`}>{DIRECTION_LABEL[report.direction]}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-secondary">Độ phức tạp</dt>
          <dd className="mt-0.5 text-text-primary">
            <span className="font-mono">{report.estimated_complexity || 'Chưa rõ'}</span>
            {report.expected_complexity && report.expected_complexity !== 'Chưa xác định' && (
              <span className="block text-xs text-text-secondary">Ràng buộc gợi ý: {report.expected_complexity}</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-secondary">Hướng giải gần nhất</dt>
          <dd className="mt-0.5 text-text-primary">
            {nearest ? nearest.name : 'Chưa có bài AC để so sánh'}
            {nearest && approachDetail(nearest) && <span className="block text-xs text-text-secondary">{approachDetail(nearest)}</span>}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-secondary">Hướng giải tốt nhất đã biết</dt>
          <dd className="mt-0.5 text-text-primary">
            {best ? (sameApproach ? 'Trùng với hướng gần nhất' : best.name) : 'Chưa có'}
          </dd>
        </div>
      </dl>

      {!accepted && (
        <section className="mt-4 border-t border-border pt-4">
          <h4 className="text-sm font-semibold text-text-primary">Lỗi logic</h4>
          {report.logic_errors.length === 0 ? (
            <p className="mt-2 text-sm text-text-secondary">Chưa xác định được vị trí sai cụ thể.</p>
          ) : (
            <ol className="mt-2 space-y-3">
              {report.logic_errors.map((error, index) => (
                <li key={index} className="rounded-md border border-border bg-card-subtle/60 p-3 text-sm leading-6">
                  <div className="flex flex-wrap items-center gap-x-2">
                    <span className="font-medium text-text-primary">{error.what}</span>
                    <LineLinks lines={error.lines} lineCount={lineCount} onFocusLines={onFocusLines} />
                  </div>
                  {error.why && <p className="text-text-primary"><span className="text-text-secondary">Vì sao: </span>{error.why}</p>}
                  {error.fix && <p className="text-text-primary"><span className="text-text-secondary">Cách sửa: </span>{error.fix}</p>}
                  <p className="text-xs text-text-secondary">Căn cứ: {EVIDENCE_LABEL[error.evidence]}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      <div className="mt-4 space-y-4">
        <FindingList title="Điểm mạnh" items={report.strengths} lineCount={lineCount} onFocusLines={onFocusLines} />
        <FindingList title={accepted ? 'Điểm cần cải thiện' : 'Điểm yếu'} items={report.weaknesses} lineCount={lineCount} onFocusLines={onFocusLines} />
      </div>

      {report.student_hints.length > 0 && (
        <details className="mt-4 border-t border-border pt-4 text-sm">
          <summary className="min-h-11 cursor-pointer py-2 font-semibold text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:min-h-0">
            Gợi ý cho học sinh, theo mức tiết lộ tăng dần
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5 leading-6 text-text-primary">
            {report.student_hints.map((hint, index) => <li key={index}>{hint}</li>)}
          </ol>
        </details>
      )}

      {report.static_facts.length > 0 && (
        <details className="mt-4 border-t border-border pt-4 text-sm">
          <summary className="min-h-11 cursor-pointer py-2 font-semibold text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:min-h-0">
            Phân tích tĩnh
          </summary>
          <ul className="mt-2 space-y-1 leading-6">
            {report.static_facts.map((fact, index) => (
              <li key={index} className={fact.kind === 'risk' ? 'text-text-primary' : 'text-text-secondary'}>
                {fact.kind === 'risk' ? 'Rủi ro: ' : ''}{fact.text}{' '}
                <LineLinks lines={fact.lines} lineCount={lineCount} onFocusLines={onFocusLines} />
              </li>
            ))}
          </ul>
        </details>
      )}

      {report.limitations.length > 0 && (
        <details className="mt-4 border-t border-border pt-4 text-sm">
          <summary className="min-h-11 cursor-pointer py-2 font-semibold text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary sm:min-h-0">
            Giới hạn của nhận xét
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 leading-6 text-text-secondary">
            {report.limitations.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </details>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4 text-sm">
        {feedback ? (
          <p role="status" className="text-text-secondary">Đã ghi nhận đánh giá của bạn.</p>
        ) : (
          <>
            <span className="text-text-secondary">Nhận xét này:</span>
            {FEEDBACK_OPTIONS.map((option) => (
              <Button key={option.rating} variant="outline" size="sm" disabled={sending}
                onClick={() => sendFeedback(option.rating)} className="min-h-11 px-3 text-sm">
                {option.label}
              </Button>
            ))}
            {feedbackError && <p role="alert" className="w-full text-sm text-red-700">{feedbackError}</p>}
          </>
        )}
      </div>
    </div>
  );
};
