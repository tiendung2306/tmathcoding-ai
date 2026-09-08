import React, { useState, useEffect, useRef } from 'react';
import {
  SubmissionDetailResponseData,
  CodeDoctorDiagnosisData,
} from '../types';
import { fetchSubmissionDetail, requestCodeDoctor, fetchJobStatus } from '../services/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';
import {
  FileText,
  Code2,
  ListChecks,
  Stethoscope,
  Copy,
  Check,
  Clock,
  HardDrive,
  Award,
  AlertCircle,
  HelpCircle,
  Lightbulb,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';

interface SubmissionDetailModalProps {
  submissionId: number | null;
  isOpen: boolean;
  onClose: () => void;
  initialTab?: 'problem' | 'code' | 'testcases' | 'diagnosis';
}

export const SubmissionDetailModal: React.FC<SubmissionDetailModalProps> = ({
  submissionId,
  isOpen,
  onClose,
  initialTab = 'problem',
}) => {
  const [detail, setDetail] = useState<SubmissionDetailResponseData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'problem' | 'code' | 'testcases' | 'diagnosis'>('problem');
  const [copied, setCopied] = useState<boolean>(false);

  // AI Code Doctor diagnosis state
  const [diagnosis, setDiagnosis] = useState<CodeDoctorDiagnosisData | null>(null);
  const [diagnosing, setDiagnosing] = useState<boolean>(false);
  const [diagnosisProgress, setDiagnosisProgress] = useState<number>(0);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);
  const pollIntervalRef = useRef<any>(null);

  const clearPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearPolling();
    };
  }, []);

  const runDiagnosisFor = async (id: number, forceRefresh: boolean = false) => {
    clearPolling();
    setDiagnosing(true);
    setDiagnosisError(null);
    setDiagnosisProgress(15);
    setActiveTab('diagnosis');
    try {
      const initRes = await requestCodeDoctor(id, forceRefresh);

      // 1. Result already available from Redis Cache
      if (initRes.status === 'COMPLETED' && initRes.result?.diagnosis) {
        setDiagnosis(initRes.result.diagnosis);
        setDiagnosisProgress(100);
        setDiagnosing(false);
        return;
      }

      // 2. Asynchronous job started -> Poll every 2 seconds
      const jobId = initRes.job_id;
      let attempts = 0;
      const maxAttempts = 60; // 120s max

      pollIntervalRef.current = setInterval(async () => {
        attempts += 1;
        try {
          const jobRes = await fetchJobStatus(jobId);
          setDiagnosisProgress(jobRes.progress || Math.min(20 + attempts * 3, 90));

          if (jobRes.status === 'COMPLETED') {
            clearPolling();
            setDiagnosis(jobRes.result?.diagnosis || null);
            setDiagnosisProgress(100);
            setDiagnosing(false);
          } else if (jobRes.status === 'FAILED') {
            clearPolling();
            setDiagnosisError(jobRes.error || 'Tác vụ chẩn đoán không thành công. Vui lòng thử lại.');
            setDiagnosing(false);
          } else if (attempts >= maxAttempts) {
            clearPolling();
            setDiagnosisError('Thời gian chẩn đoán vượt quá giới hạn cho phép. Vui lòng bấm thử lại.');
            setDiagnosing(false);
          }
        } catch (pollErr: any) {
          console.error('Polling error:', pollErr);
          if (attempts >= maxAttempts) {
            clearPolling();
            setDiagnosisError('Không thể kết nối đến máy chủ để lấy kết quả chẩn đoán.');
            setDiagnosing(false);
          }
        }
      }, 2000);
    } catch (err: any) {
      console.error(err);
      clearPolling();
      setDiagnosisError(err?.response?.data?.detail || 'Chẩn đoán tạm thời gián đoạn. Vui lòng thử lại.');
      setDiagnosing(false);
    }
  };

  useEffect(() => {
    if (isOpen && submissionId) {
      loadSubmissionDetail(submissionId);
      setActiveTab(initialTab);
      setDiagnosis(null);
      setDiagnosisError(null);
      setDiagnosisProgress(0);
      if (initialTab === 'diagnosis') {
        runDiagnosisFor(submissionId);
      }
    } else {
      clearPolling();
      setDetail(null);
      setError(null);
      setDiagnosis(null);
      setDiagnosisError(null);
      setDiagnosisProgress(0);
    }
  }, [isOpen, submissionId, initialTab]);

  const loadSubmissionDetail = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSubmissionDetail(id);
      setDetail(res);
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Không thể tải chi tiết bài nộp. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCode = async () => {
    if (!detail?.source_code) return;
    try {
      await navigator.clipboard.writeText(detail.source_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunDiagnosis = (forceRefresh: boolean = false) => {
    if (submissionId) {
      runDiagnosisFor(submissionId, forceRefresh);
    }
  };

  const formatMemory = (kb: number | null | undefined) => {
    if (kb === null || kb === undefined) return 'N/A';
    if (kb >= 1024) {
      return `${(kb / 1024).toFixed(1)} MB`;
    }
    return `${kb} KB`;
  };

  const getVerdictVariant = (result: string) => {
    switch (result) {
      case 'AC':
        return 'ac';
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

  const getVerdictBadge = (status: string) => {
    switch (status) {
      case 'AC':
        return (
          <span className="inline-flex items-center gap-1 font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded text-[11px] font-medium">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            AC
          </span>
        );
      case 'WA':
        return (
          <span className="inline-flex items-center gap-1 font-mono text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded text-[11px] font-medium">
            <XCircle className="w-3 h-3 text-red-600" />
            WA
          </span>
        );
      case 'TLE':
        return (
          <span className="inline-flex items-center gap-1 font-mono text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded text-[11px] font-medium">
            <Clock className="w-3 h-3 text-amber-600" />
            TLE
          </span>
        );
      case 'RTE':
        return (
          <span className="inline-flex items-center gap-1 font-mono text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded text-[11px] font-medium">
            <AlertTriangle className="w-3 h-3 text-purple-600" />
            RTE
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 font-mono text-text-secondary bg-card-subtle border border-border px-1.5 py-0.5 rounded text-[11px]">
            {status}
          </span>
        );
    }
  };

  const testcases = detail?.testcases ?? [];
  const passedCases = testcases.filter((tc) => tc.status === 'AC').length;
  const totalCases = testcases.length;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] flex flex-col p-4 sm:p-6 overflow-hidden">
        {loading || !detail ? (
          <div className="space-y-4 py-8">
            <div className="flex items-center justify-between">
              <Skeleton className="h-6 w-1/3" />
              <Skeleton className="h-6 w-20" />
            </div>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-64 w-full" />
            <p className="text-xs text-text-secondary text-center">
              Đang tải thông tin chi tiết bài nộp...
            </p>
          </div>
        ) : error ? (
          <div className="py-10 text-center space-y-3">
            <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
            <p className="text-sm font-medium text-text-primary">{error}</p>
            <div className="flex justify-center gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => submissionId && loadSubmissionDetail(submissionId)}
              >
                Thử lại
              </Button>
              <Button variant="secondary" size="sm" onClick={onClose}>
                Đóng
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Modal Header */}
            <DialogHeader className="space-y-2 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pr-6">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <DialogTitle className="text-base font-semibold text-text-primary">
                      {detail.problem_name}
                    </DialogTitle>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {detail.problem_code}
                    </Badge>
                    <Badge variant={getVerdictVariant(detail.result)} className="text-[10px]">
                      {detail.result}
                    </Badge>
                  </div>
                  <DialogDescription className="text-xs text-text-secondary flex items-center gap-3 flex-wrap font-mono">
                    <span>Mã nộp: #{detail.submission_id}</span>
                    <span>Ngôn ngữ: {detail.language_name}</span>
                    {detail.date && <span>Nộp lúc: {detail.date}</span>}
                  </DialogDescription>
                </div>

                {/* Top Action: Run Code Doctor */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleRunDiagnosis(false)}
                  disabled={diagnosing}
                  className="h-8 px-3 text-xs font-medium border-red-200 text-red-700 bg-red-50 hover:bg-red-100 shrink-0 gap-1.5"
                >
                  <Stethoscope className="w-3.5 h-3.5 text-red-600" />
                  <span>{diagnosing ? 'Đang chẩn đoán...' : 'Chẩn đoán với Code Doctor'}</span>
                </Button>
              </div>

              {/* Telemetry Chips Bar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="bg-card-subtle/70 border border-border/80 rounded p-2 flex items-center gap-2">
                  <Award className="w-3.5 h-3.5 text-brand-primary shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-text-secondary">Điểm số</p>
                    <p className="text-xs font-bold text-text-primary font-mono">
                      {detail.points} / {detail.problem_points}
                    </p>
                  </div>
                </div>

                <div className="bg-card-subtle/70 border border-border/80 rounded p-2 flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-text-secondary">Thời gian chạy</p>
                    <p className="text-xs font-bold text-text-primary font-mono truncate">
                      {detail.time !== null && detail.time !== undefined ? `${detail.time}s` : 'N/A'} (max {detail.time_limit}s)
                    </p>
                  </div>
                </div>

                <div className="bg-card-subtle/70 border border-border/80 rounded p-2 flex items-center gap-2">
                  <HardDrive className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-text-secondary">Bộ nhớ dùng</p>
                    <p className="text-xs font-bold text-text-primary font-mono truncate">
                      {formatMemory(detail.memory)} (max {formatMemory(detail.memory_limit * 1024)})
                    </p>
                  </div>
                </div>

                <div className="bg-card-subtle/70 border border-border/80 rounded p-2 flex items-center gap-2">
                  <ListChecks className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-text-secondary">Trường hợp kiểm thử</p>
                    <p className="text-xs font-bold text-text-primary font-mono">
                      {totalCases > 0 ? `${passedCases}/${totalCases} đạt` : '0 test'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Navigation Tabs */}
              <div className="flex border-b border-border/80 pt-2 gap-1 overflow-x-auto">
                <button
                  type="button"
                  onClick={() => setActiveTab('problem')}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap focus-visible:outline-none ${
                    activeTab === 'problem'
                      ? 'border-brand-primary text-brand-primary'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Đề bài & Ràng buộc</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('code')}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap focus-visible:outline-none ${
                    activeTab === 'code'
                      ? 'border-brand-primary text-brand-primary'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <Code2 className="w-3.5 h-3.5" />
                  <span>Mã nguồn bài nộp</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('testcases')}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap focus-visible:outline-none ${
                    activeTab === 'testcases'
                      ? 'border-brand-primary text-brand-primary'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <ListChecks className="w-3.5 h-3.5" />
                  <span>Kết quả kiểm thử ({totalCases})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('diagnosis')}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap focus-visible:outline-none ${
                    activeTab === 'diagnosis'
                      ? 'border-red-600 text-red-700 font-semibold'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <Stethoscope className="w-3.5 h-3.5 text-red-600" />
                  <span>Chẩn đoán AI</span>
                  {diagnosis && (
                    <span className="w-1.5 h-1.5 rounded-full bg-red-600 inline-block ml-0.5" />
                  )}
                </button>
              </div>
            </DialogHeader>

            {/* Tab Contents (Scrollable Body) */}
            <div className="flex-1 overflow-y-auto py-2 pr-1 space-y-4 min-h-[300px]">
              {/* TAB 1: Problem Statement & Limits */}
              {activeTab === 'problem' && (
                <div className="space-y-3">
                  <div className="bg-card-subtle/50 border border-border/80 rounded-md p-3.5 text-xs text-text-secondary space-y-2">
                    <div className="flex items-center justify-between flex-wrap gap-2 text-text-primary font-medium border-b border-border/60 pb-2">
                      <span>Ràng buộc kỹ thuật bài toán</span>
                      <span className="font-mono text-[11px] text-text-secondary">
                        Mã bài: {detail.problem_code}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
                      <div>
                        <span className="text-text-secondary">Thời gian tối đa:</span>{' '}
                        <span className="font-mono font-medium text-text-primary">{detail.time_limit} giây</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">Bộ nhớ tối đa:</span>{' '}
                        <span className="font-mono font-medium text-text-primary">{detail.memory_limit} MB</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">Thang điểm tối đa:</span>{' '}
                        <span className="font-mono font-medium text-text-primary">{detail.problem_points} điểm</span>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-md border border-border bg-card p-4 space-y-2">
                    <h4 className="text-xs font-semibold text-text-primary flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-brand-primary" />
                      Mô tả đề bài
                    </h4>
                    {detail.problem_description ? (
                      <div className="text-xs text-text-primary whitespace-pre-wrap leading-relaxed font-sans max-h-[380px] overflow-y-auto pr-1">
                        {detail.problem_description}
                      </div>
                    ) : (
                      <p className="text-xs text-text-secondary italic py-4 text-center">
                        Bài toán này chưa có nội dung mô tả chi tiết trong hệ thống.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 2: Source Code */}
              {activeTab === 'code' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between bg-card-subtle/70 border border-border/80 px-3 py-2 rounded-t-md">
                    <div className="flex items-center gap-2">
                      <Code2 className="w-3.5 h-3.5 text-text-secondary" />
                      <span className="text-xs font-mono font-medium text-text-primary">
                        {detail.language_name}
                      </span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopyCode}
                      className="h-6 px-2 text-[11px] gap-1 font-mono"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-600" />
                          <span>Đã sao chép</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3 text-text-secondary" />
                          <span>Sao chép mã</span>
                        </>
                      )}
                    </Button>
                  </div>

                  <div className="bg-slate-950 text-slate-100 rounded-b-md border border-border font-mono text-xs overflow-x-auto max-h-[440px] p-3 leading-5">
                    <table className="w-full border-collapse">
                      <tbody>
                        {detail.source_code.split('\n').map((line, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/60">
                            <td className="w-10 pr-3 text-right text-slate-500 select-none text-[11px] align-top">
                              {idx + 1}
                            </td>
                            <td className="whitespace-pre font-mono text-slate-200">
                              {line || ' '}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* TAB 3: Test Cases Breakdown */}
              {activeTab === 'testcases' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-text-secondary px-1">
                    <span>
                      Tổng số: <strong className="text-text-primary">{totalCases}</strong> test cases
                    </span>
                    <span>
                      Đạt: <strong className="text-emerald-600">{passedCases}</strong> / {totalCases}
                    </span>
                  </div>

                  {totalCases === 0 ? (
                    <div className="rounded-md border border-border bg-card-subtle/40 p-8 text-center text-xs text-text-secondary">
                      Chưa có dữ liệu kết quả từng test case cho bài nộp này.
                    </div>
                  ) : (
                    <div className="rounded-md border border-border overflow-hidden">
                      <div className="overflow-x-auto max-h-[400px]">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead className="bg-card-subtle border-b border-border text-[11px] text-text-secondary font-medium sticky top-0">
                            <tr>
                              <th className="py-2.5 px-3">Test #</th>
                              <th className="py-2.5 px-3">Trạng thái</th>
                              <th className="py-2.5 px-3">Điểm số</th>
                              <th className="py-2.5 px-3">Thời gian</th>
                              <th className="py-2.5 px-3">Bộ nhớ</th>
                              <th className="py-2.5 px-3">Ghi chú phản hồi</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/60">
                            {testcases.map((tc) => (
                              <tr
                                key={tc.case}
                                className={`hover:bg-card-subtle/50 transition-colors ${
                                  tc.status !== 'AC' ? 'bg-red-50/20' : ''
                                }`}
                              >
                                <td className="py-2 px-3 font-mono font-medium text-text-primary">
                                  #{tc.case}
                                </td>
                                <td className="py-2 px-3">
                                  {getVerdictBadge(tc.status)}
                                </td>
                                <td className="py-2 px-3 font-mono text-text-secondary">
                                  {tc.points !== null && tc.total !== null
                                    ? `${tc.points}/${tc.total}`
                                    : tc.points ?? '0'}
                                </td>
                                <td className="py-2 px-3 font-mono text-text-secondary">
                                  {tc.time !== null && tc.time !== undefined
                                    ? `${tc.time.toFixed(3)}s`
                                    : 'N/A'}
                                </td>
                                <td className="py-2 px-3 font-mono text-text-secondary">
                                  {formatMemory(tc.memory)}
                                </td>
                                <td className="py-2 px-3 text-text-secondary font-mono text-[11px] max-w-xs truncate">
                                  {tc.feedback || tc.output || (tc.status === 'AC' ? 'Chính xác' : 'Không có chi tiết')}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 4: Socratic AI Code Doctor Diagnosis */}
              {activeTab === 'diagnosis' && (
                <div className="space-y-3.5">
                  {diagnosing ? (
                    <div className="rounded-md border border-border bg-card p-6 space-y-3 text-center">
                      <div className="p-3 w-12 h-12 rounded-full bg-red-50 border border-red-200 text-red-600 mx-auto flex items-center justify-center animate-pulse">
                        <Stethoscope className="w-6 h-6" />
                      </div>
                      <h4 className="text-xs font-semibold text-text-primary">
                        AI Code Doctor đang phân tích mã nguồn và các test case lỗi
                      </h4>
                      <p className="text-[11px] text-text-secondary max-w-md mx-auto leading-relaxed">
                        Hệ thống đang đối chiếu đề bài, các ràng buộc thời gian, bộ nhớ và các trường hợp kiểm thử bị lỗi để xây dựng câu hỏi gợi mở tư duy.
                      </p>
                      <div className="pt-2 max-w-xs mx-auto space-y-1.5">
                        <div className="h-1.5 w-full bg-border rounded-full overflow-hidden">
                          <div
                            className="h-full bg-red-600 transition-all duration-500 rounded-full"
                            style={{ width: `${diagnosisProgress}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-mono text-text-secondary">
                          Đang xử lý ngầm ({diagnosisProgress}%)
                        </span>
                      </div>
                    </div>
                  ) : diagnosisError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 p-4 space-y-2 text-center">
                      <AlertCircle className="w-6 h-6 text-red-600 mx-auto" />
                      <p className="text-xs font-medium text-red-700">{diagnosisError}</p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRunDiagnosis(false)}
                        className="text-xs gap-1.5 border-red-200 text-red-700 hover:bg-red-100"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Thử chẩn đoán lại</span>
                      </Button>
                    </div>
                  ) : diagnosis ? (
                    <div className="rounded-lg border border-border bg-card p-4 sm:p-5 space-y-3.5">
                      {/* Summary Banner */}
                      <div className="flex items-center justify-between border-b border-border/60 pb-3">
                        <div className="flex items-center gap-2">
                          <div className="p-1.5 rounded bg-red-50 border border-red-200 text-red-600">
                            <Stethoscope className="w-4 h-4" />
                          </div>
                          <div>
                            <h4 className="text-xs font-semibold text-text-primary">
                              Nhận xét chuyên môn từ AI Code Doctor
                            </h4>
                            <p className="text-[11px] text-text-secondary">
                              Phân tích trực tiếp mã nguồn và test case bài {detail.problem_name}
                            </p>
                          </div>
                        </div>
                        <Badge variant="wa" className="text-[10px] font-mono">
                          {diagnosis.error_category}
                        </Badge>
                      </div>

                      {/* Single Cohesive Paragraph */}
                      <div className="rounded-md bg-card-subtle/70 border border-border/70 p-4">
                        <p className="text-xs sm:text-[13px] text-text-primary leading-relaxed whitespace-pre-wrap font-sans">
                          {diagnosis.advice || diagnosis.summary}
                        </p>
                      </div>

                      <div className="pt-1 flex justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRunDiagnosis(true)}
                          disabled={diagnosing}
                          className="text-xs gap-1.5 h-7 px-2.5"
                        >
                          <RotateCcw className="w-3 h-3 text-text-secondary" />
                          <span>Chẩn đoán lại (Làm mới)</span>
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-md border border-border bg-card p-6 space-y-3 text-center">
                      <div className="p-3 w-12 h-12 rounded-full bg-red-50 border border-red-200 text-red-600 mx-auto flex items-center justify-center">
                        <Stethoscope className="w-6 h-6" />
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-semibold text-text-primary">
                          Chưa có nhận xét cho bài nộp này
                        </h4>
                        <p className="text-[11px] text-text-secondary max-w-md mx-auto leading-relaxed">
                          AI Code Doctor sẽ đối chiếu đề bài, giới hạn ràng buộc và các test case bị lỗi để phân tích trực diện vấn đề trong thuật toán của bạn.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRunDiagnosis(false)}
                        className="text-xs gap-1.5 h-8 px-3 border-red-200 text-red-700 bg-red-50 hover:bg-red-100"
                      >
                        <Stethoscope className="w-3.5 h-3.5 text-red-600" />
                        <span>Chẩn đoán bài nộp này</span>
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <DialogFooter className="pt-2 border-t border-border/80 flex items-center justify-between sm:justify-between">
              <div className="text-[11px] text-text-secondary font-mono hidden sm:block">
                Bài toán: {detail.problem_code} • Nộp: #{detail.submission_id}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={onClose}
                className="text-xs"
              >
                Đóng
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
