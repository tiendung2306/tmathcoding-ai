import React, { useState } from 'react';
import { FailedSubmissionItem } from '../types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Stethoscope, Clock, CheckCircle2, FileCode, ChevronRight } from 'lucide-react';
import { SubmissionDetailModal } from './SubmissionDetailModal';

interface FailedSubmissionsListProps {
  submissions: FailedSubmissionItem[];
  loading: boolean;
  onDiagnose?: (submissionId: number) => void;
  diagnosingId?: number | null;
}

export const FailedSubmissionsList: React.FC<FailedSubmissionsListProps> = ({
  submissions,
  loading,
}) => {
  const [modalSubmissionId, setModalSubmissionId] = useState<number | null>(null);
  const [modalTab, setModalTab] = useState<'problem' | 'code' | 'testcases' | 'diagnosis'>('problem');

  const getBadgeVariant = (result: string) => {
    switch (result) {
      case 'WA':
        return 'wa';
      case 'TLE':
        return 'tle';
      case 'RTE':
        return 'rte';
      default:
        return 'outline';
    }
  };

  const getResultLabel = (result: string) => {
    switch (result) {
      case 'WA':
        return 'Kết quả sai';
      case 'TLE':
        return 'Quá thời gian';
      case 'RTE':
        return 'Lỗi thực thi';
      case 'CE':
        return 'Lỗi biên dịch';
      case 'MLE':
        return 'Quá bộ nhớ';
      default:
        return result;
    }
  };

  const handleOpenDetail = (submissionId: number, tab: 'problem' | 'code' | 'testcases' | 'diagnosis' = 'problem') => {
    setModalSubmissionId(submissionId);
    setModalTab(tab);
  };

  return (
    <>
      <Card className="border-border bg-card">
        <CardHeader className="pb-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded bg-red-50 border border-red-200 text-red-600">
                <Stethoscope className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-sm font-semibold text-text-primary">
                  Bài nộp chưa đạt gần đây
                </CardTitle>
                <CardDescription className="text-xs text-text-secondary mt-0.5">
                  Nhấn vào bài nộp để xem đề bài, mã nguồn, chi tiết các test case và chẩn đoán Socratic với Code Doctor
                </CardDescription>
              </div>
            </div>
            {submissions.length > 0 && (
              <Badge variant="outline" className="text-xs font-mono">
                {submissions.length} bài
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent className="pt-2">
          {loading ? (
            <div className="space-y-2 py-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 bg-card-subtle rounded animate-pulse" />
              ))}
            </div>
          ) : submissions.length === 0 ? (
            <div className="py-8 text-center flex flex-col items-center justify-center text-text-secondary">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mb-2 opacity-80" />
              <p className="text-xs font-medium text-text-primary">
                Không có bài nộp lỗi nào gần đây
              </p>
              <p className="text-[11px] text-text-secondary mt-0.5">
                Học sinh chưa có bài nộp nào bị đánh giá lỗi có lưu mã nguồn trong hệ thống.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border/60">
              {submissions.map((sub) => {
                return (
                  <div
                    key={sub.submission_id}
                    onClick={() => handleOpenDetail(sub.submission_id, 'problem')}
                    className="py-3 px-2.5 rounded-md transition-colors cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-card-subtle/70 group"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-medium text-text-primary group-hover:text-brand-primary transition-colors">
                          {sub.problem_name}
                        </span>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {sub.problem_code}
                        </Badge>
                        <Badge variant={getBadgeVariant(sub.result)} className="text-[10px]">
                          {sub.result} • {getResultLabel(sub.result)}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-3 text-[11px] text-text-secondary font-mono">
                        <span>Mã nộp: #{sub.submission_id}</span>
                        {sub.date && (
                          <span className="flex items-center gap-1 text-[11px]">
                            <Clock className="w-3 h-3 text-text-secondary/70" />
                            {sub.date}
                          </span>
                        )}
                        <span>{sub.points} pts</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(sub.submission_id, 'code');
                        }}
                        className="h-7 px-2.5 text-xs font-medium gap-1 text-text-secondary hover:text-text-primary"
                      >
                        <FileCode className="w-3.5 h-3.5" />
                        <span>Xem code & test</span>
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(sub.submission_id, 'diagnosis');
                        }}
                        className="h-7 px-2.5 text-xs font-medium gap-1.5 border-red-200 text-red-700 bg-red-50 hover:bg-red-100"
                      >
                        <Stethoscope className="w-3.5 h-3.5 text-red-600" />
                        <span>Chẩn đoán</span>
                      </Button>
                      <ChevronRight className="w-4 h-4 text-text-disabled group-hover:text-text-secondary transition-colors hidden sm:block" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detailed Modal: Problem, Source Code, Test Cases, and Socratic Code Doctor */}
      <SubmissionDetailModal
        submissionId={modalSubmissionId}
        isOpen={modalSubmissionId !== null}
        onClose={() => setModalSubmissionId(null)}
        initialTab={modalTab}
      />
    </>
  );
};
