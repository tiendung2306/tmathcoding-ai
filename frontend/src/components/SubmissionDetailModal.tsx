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
} from './ui/dialog';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';
import { MarkdownMath } from './MarkdownMath';
import {
  Code2,
  Stethoscope,
  Loader2,
  Copy,
  Check,
  AlertCircle,
  RotateCcw,
  CheckCircle2,
  XCircle,
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
  const [activeTab, setActiveTab] = useState<'overview' | 'diagnosis'>('overview');
  const [copied, setCopied] = useState<boolean>(false);
  const [highlightedCode, setHighlightedCode] = useState<string | null>(null);
  const [selectedCaseIndex, setSelectedCaseIndex] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

  // AI Code Doctor diagnosis state
  const [diagnosis, setDiagnosis] = useState<CodeDoctorDiagnosisData | null>(null);
  const [diagnosing, setDiagnosing] = useState<boolean>(false);
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

  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = 0;
  }, [activeTab]);

  useEffect(() => {
    let current = true;
    setHighlightedCode(null);
    if (activeTab !== 'overview' || !detail?.source_code) return;
    void import('../lib/codeHighlight').then(({ highlightSource }) => {
      if (current) setHighlightedCode(highlightSource(detail.source_code, detail.language_name));
    }).catch(() => {
      if (current) setHighlightedCode(null);
    });
    return () => { current = false; };
  }, [activeTab, detail?.source_code, detail?.language_name]);

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    const current = tabs.indexOf(document.activeElement as HTMLButtonElement);
    if (current < 0) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    tabs[next].click();
  };

  const runDiagnosisFor = async (id: number, forceRefresh: boolean = false) => {
    clearPolling();
    setDiagnosing(true);
    setDiagnosisError(null);
    setActiveTab('diagnosis');
    try {
      const initRes = await requestCodeDoctor(id, forceRefresh);

      // 1. Result already available from Redis Cache
      if (initRes.status === 'COMPLETED' && initRes.result?.diagnosis) {
        setDiagnosis(initRes.result.diagnosis);
        setDiagnosing(false);
        return;
      }

      // 2. Asynchronous job started -> Poll every 2 seconds
      const jobId = initRes.job_id;
      let attempts = 0;
      const maxAttempts = 90; // 180s max for the local CPU model

      pollIntervalRef.current = setInterval(async () => {
        attempts += 1;
        try {
          const jobRes = await fetchJobStatus(jobId);

          if (jobRes.status === 'COMPLETED') {
            clearPolling();
            setDiagnosis(jobRes.result?.diagnosis || null);
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
      setActiveTab(initialTab === 'diagnosis' ? 'diagnosis' : 'overview');
      setSelectedCaseIndex(0);
      setDiagnosis(null);
      setDiagnosisError(null);
      if (initialTab === 'diagnosis') {
        runDiagnosisFor(submissionId);
      }
    } else {
      clearPolling();
      setDetail(null);
      setError(null);
      setDiagnosis(null);
      setDiagnosisError(null);
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

  const getVerdictBadge = (status: string) => {
    const passed = status === 'AC';
    return (
      <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-xs font-medium ${passed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
        {passed ? <CheckCircle2 aria-hidden="true" className="h-3 w-3" /> : <XCircle aria-hidden="true" className="h-3 w-3" />}
        {status}
      </span>
    );
  };

  const testcases = detail?.testcases ?? [];
  const passedCases = testcases.filter((tc) => tc.status === 'AC').length;
  const totalCases = testcases.length;
  const selectedCase = testcases[selectedCaseIndex] ?? testcases[0];
  const codeLineCount = detail?.source_code.split('\n').length ?? 0;
  const problemDescription = detail?.problem_description.replace(
    /^\s*(?:#{1,6}[ \t]+Đề bài|(?:\*\*|__)[ \t]*Đề bài[ \t]*(?:\*\*|__)|Đề bài)[ \t]*:?[ \t]*(?:\r?\n)+/i,
    '',
  ).trimStart() ?? '';

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex h-[calc(100dvh-1rem)] max-h-[calc(100dvh-1rem)] w-[calc(100%-1rem)] max-w-[1600px] flex-col gap-0 overflow-hidden p-0 sm:h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-2rem)] sm:w-[calc(100%-2rem)]">
        {error ? (
          <div className="m-auto space-y-3 px-6 py-10 text-center">
            <DialogTitle className="sr-only">Chi tiết bài nộp</DialogTitle>
            <DialogDescription className="sr-only">Không tải được chi tiết bài nộp.</DialogDescription>
            <AlertCircle className="mx-auto h-8 w-8 text-red-600" />
            <p className="text-sm font-medium text-text-primary">{error}</p>
            <div className="flex justify-center gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => submissionId && loadSubmissionDetail(submissionId)}>Thử lại</Button>
              <Button variant="secondary" size="sm" onClick={onClose}>Đóng</Button>
            </div>
          </div>
        ) : loading || !detail ? (
          <div className="m-auto w-full max-w-2xl space-y-4 px-6 py-8" role="status" aria-busy="true">
            <DialogTitle className="sr-only">Chi tiết bài nộp</DialogTitle>
            <DialogDescription className="sr-only">Đang tải chi tiết bài nộp.</DialogDescription>
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
        ) : (
          <>
            {/* Modal Header */}
            <DialogHeader className="shrink-0 gap-0 space-y-0 border-b-0 p-4 pb-0 sm:px-6 sm:pt-5">
              <div className="pr-11">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <DialogTitle className="min-w-0 text-lg font-semibold leading-snug text-text-primary sm:text-xl">
                      {detail.problem_name}
                    </DialogTitle>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant="outline" className="font-mono text-xs">
                        {detail.problem_code}
                      </Badge>
                      <strong className={`font-mono text-3xl font-bold leading-none ${detail.result === 'AC' ? 'text-emerald-700' : 'text-red-700'}`}>
                        <span className="sr-only">Kết quả: </span>{detail.result}
                      </strong>
                    </div>
                  </div>
                  {detail.date && <DialogDescription className="text-xs text-text-secondary sm:text-sm">Nộp lúc: {detail.date}</DialogDescription>}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-y border-border bg-card-subtle/50 px-3 py-3 sm:grid-cols-4 sm:px-4">
                <div className="min-w-0"><p className="text-xs text-text-secondary">Điểm</p><p className="mt-0.5 font-mono text-sm font-semibold text-text-primary">{detail.points} / {detail.problem_points}</p></div>
                <div className="min-w-0"><p className="text-xs text-text-secondary">Thời gian</p><p className="mt-0.5 font-mono text-sm font-semibold text-text-primary">{detail.time !== null && detail.time !== undefined ? `${detail.time}s` : 'N/A'}</p></div>
                <div className="min-w-0"><p className="text-xs text-text-secondary">Bộ nhớ</p><p className="mt-0.5 font-mono text-sm font-semibold text-text-primary">{formatMemory(detail.memory)}</p></div>
                <div className="min-w-0"><p className="text-xs text-text-secondary">Kiểm thử đạt</p><p className="mt-0.5 font-mono text-sm font-semibold text-text-primary">{totalCases > 0 ? `${passedCases} / ${totalCases}` : 'Chưa có'}</p></div>
              </div>

              <div className="-mx-4 mt-2 flex gap-1 border-b border-border px-4 sm:-mx-6 sm:px-6" role="tablist" aria-label="Chi tiết bài nộp" onKeyDown={handleTabKeyDown}>
                <button
                  type="button"
                  role="tab"
                  id="submission-tab-overview"
                  aria-controls="submission-tab-panel"
                  aria-selected={activeTab === 'overview'}
                  tabIndex={activeTab === 'overview' ? 0 : -1}
                  onClick={() => setActiveTab('overview')}
                  className={`flex min-h-11 shrink-0 items-center border-b-2 px-3 text-sm font-medium transition-colors whitespace-nowrap hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary ${
                    activeTab === 'overview'
                      ? 'border-brand-primary text-brand-primary'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <span>Bài nộp</span>
                </button>

                <button
                  type="button"
                  role="tab"
                  id="submission-tab-diagnosis"
                  aria-controls="submission-tab-panel"
                  aria-selected={activeTab === 'diagnosis'}
                  tabIndex={activeTab === 'diagnosis' ? 0 : -1}
                  onClick={() => setActiveTab('diagnosis')}
                  className={`flex min-h-11 shrink-0 items-center border-b-2 px-3 text-sm font-medium transition-colors whitespace-nowrap hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary ${
                    activeTab === 'diagnosis'
                      ? 'border-red-600 text-red-700 font-semibold'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  <span>Code Doctor</span>
                  {diagnosis && (
                    <span aria-hidden="true" className="ml-0.5 inline-block h-1.5 w-1.5 rounded-full bg-red-600" />
                  )}
                </button>
              </div>
            </DialogHeader>

            <div ref={contentRef} id="submission-tab-panel" role="tabpanel" aria-labelledby={`submission-tab-${activeTab}`} tabIndex={0} className="min-h-0 flex-1 overflow-y-auto overscroll-contain focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary lg:overflow-hidden">
              {activeTab === 'overview' && (
                <div className="grid min-h-0 gap-2 bg-card-subtle p-2 lg:h-full lg:grid-cols-2">
                  <section aria-label="Đề bài" tabIndex={0} className="min-w-0 rounded-md border border-border bg-card p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary lg:min-h-0 lg:overflow-y-auto lg:p-5">
                    <div className="mx-auto max-w-[78ch] space-y-5">
                      <div className="space-y-2 border-b border-border pb-3">
                        <h2 className="text-base font-semibold text-text-primary">Đề bài</h2>
                        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-text-secondary sm:text-sm">
                          <span>Giới hạn thời gian <strong className="font-mono font-medium text-text-primary">{detail.time_limit} giây</strong></span>
                          <span>Giới hạn bộ nhớ <strong className="font-mono font-medium text-text-primary">{detail.memory_limit} MB</strong></span>
                        </div>
                      </div>

                      <div className="min-w-0">
                        {problemDescription ? (
                          <MarkdownMath
                            content={problemDescription}
                            className="markdown-submission text-sm leading-7 text-text-primary sm:text-[15px] sm:leading-7"
                          />
                        ) : (
                          <p className="py-6 text-center text-sm text-text-secondary">
                            Bài toán này chưa có nội dung mô tả chi tiết trong hệ thống.
                          </p>
                        )}
                      </div>
                    </div>
                  </section>

                  <div className="grid min-h-0 min-w-0 gap-2 lg:grid-rows-[minmax(0,1fr)_minmax(180px,0.48fr)]">
                    <section aria-label="Mã nguồn" className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-md border-2 border-white bg-black">
                      <div className="flex shrink-0 items-center justify-between border-b border-white bg-black px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Code2 className="h-4 w-4 text-white" />
                          <h2 className="text-sm font-semibold text-white">Mã nguồn <span className="ml-1 font-normal text-slate-300">{detail.language_name}</span></h2>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCopyCode}
                          className="min-h-11 gap-1 border-white bg-black px-2 text-xs text-white hover:border-white hover:bg-slate-900"
                        >
                          {copied ? (
                            <>
                              <Check className="h-3 w-3 text-emerald-400" />
                              <span>Đã sao chép</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3 text-slate-300" />
                              <span>Sao chép mã</span>
                            </>
                          )}
                        </Button>
                      </div>

                      <div tabIndex={0} aria-label="Nội dung mã nguồn" className="submission-source max-h-[45dvh] min-h-0 flex-1 overflow-auto bg-black p-3 font-mono text-[13px] leading-6 text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white lg:max-h-none">
                        <div className="flex min-w-max">
                          <div aria-hidden="true" className="select-none border-r border-white/20 pr-3 text-right text-xs text-slate-400">
                            {Array.from({ length: codeLineCount }, (_, index) => <div key={index} className="h-6">{index + 1}</div>)}
                          </div>
                          <pre className="m-0 pl-3 font-mono leading-6"><code className="hljs">{highlightedCode === null ? detail.source_code : <span dangerouslySetInnerHTML={{ __html: highlightedCode }} />}</code></pre>
                        </div>
                      </div>
                    </section>

                    <section aria-label="Kết quả kiểm thử" className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-md border border-border bg-card">
                      <div className="flex shrink-0 items-center justify-between border-b border-border bg-card-subtle/70 px-3 py-3 text-sm">
                        <h2 className="font-semibold text-text-primary">Kết quả kiểm thử</h2>
                        <span className="text-text-secondary">{totalCases > 0 ? `${passedCases} / ${totalCases} đạt` : 'Chưa có dữ liệu'}</span>
                      </div>
                      <div tabIndex={0} aria-label="Danh sách kết quả kiểm thử" className="max-h-[35dvh] min-h-0 flex-1 overflow-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-primary lg:max-h-none">
                        {totalCases === 0 ? (
                          <div className="p-8 text-center text-sm text-text-secondary">
                            Chưa có dữ liệu kết quả từng test case cho bài nộp này.
                          </div>
                        ) : (
                          <div className="p-3">
                            <ol className="grid grid-cols-5 gap-2 xl:grid-cols-10">
                              {testcases.map((tc, index) => (
                                <li key={`${tc.case}-${index}`}>
                                  <button
                                    type="button"
                                    onClick={() => setSelectedCaseIndex(index)}
                                    aria-label={`Kiểm thử ${tc.case}: ${tc.status === 'AC' ? 'đạt' : 'không đạt'}`}
                                    aria-pressed={selectedCaseIndex === index}
                                    className={`flex min-h-11 w-full items-center justify-center gap-1 rounded-sm border px-1 font-mono text-sm font-semibold text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${tc.status === 'AC' ? 'border-emerald-800 bg-emerald-700 hover:bg-emerald-800' : 'border-red-800 bg-red-700 hover:bg-red-800'} ${selectedCaseIndex === index ? 'ring-2 ring-brand-primary ring-offset-2' : ''}`}
                                  >
                                    {tc.status === 'AC' ? <Check aria-hidden="true" className="h-3 w-3 shrink-0" /> : <XCircle aria-hidden="true" className="h-3 w-3 shrink-0" />}
                                    #{tc.case}
                                  </button>
                                </li>
                              ))}
                            </ol>
                            {selectedCase && (
                              <div className="mt-4 border-t border-border pt-3 text-sm">
                                <div className="flex items-center gap-2">
                                  <strong className="font-mono text-text-primary">Kiểm thử #{selectedCase.case}</strong>
                                  {getVerdictBadge(selectedCase.status)}
                                </div>
                                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
                                  <div><dt className="text-text-secondary">Điểm</dt><dd className="font-mono text-text-primary">{selectedCase.points !== null && selectedCase.total !== null ? `${selectedCase.points}/${selectedCase.total}` : selectedCase.points ?? '0'}</dd></div>
                                  <div><dt className="text-text-secondary">Thời gian</dt><dd className="font-mono text-text-primary">{selectedCase.time !== null && selectedCase.time !== undefined ? `${selectedCase.time.toFixed(3)}s` : 'N/A'}</dd></div>
                                  <div><dt className="text-text-secondary">Bộ nhớ</dt><dd className="font-mono text-text-primary">{formatMemory(selectedCase.memory)}</dd></div>
                                </dl>
                                {(selectedCase.feedback || selectedCase.output || selectedCase.status !== 'AC') && (
                                  <p className="mt-2 break-words text-xs text-text-secondary">{selectedCase.feedback || selectedCase.output || 'Không có chi tiết phản hồi'}</p>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </section>
                  </div>
                </div>
              )}

              {activeTab === 'diagnosis' && (
                <div className="mx-auto h-full max-w-4xl space-y-3.5 overflow-y-auto p-4 sm:p-6">
                  {diagnosing ? (
                    <div role="status" aria-live="polite" className="rounded-md border border-border bg-card p-6 space-y-3 text-center">
                      <div className="p-3 w-12 h-12 rounded-full bg-red-50 border border-red-200 text-red-600 mx-auto flex items-center justify-center">
                        <Loader2 aria-hidden="true" className="w-6 h-6 motion-safe:animate-spin" />
                      </div>
                      <h4 className="text-sm font-semibold text-text-primary">
                        Đang phân tích bài nộp
                      </h4>
                      <p className="mx-auto max-w-md text-sm leading-relaxed text-text-secondary">
                        Đang đối chiếu đề bài, mã nguồn và kết quả kiểm thử.
                      </p>
                    </div>
                  ) : diagnosisError ? (
                    <div className="rounded-md border border-red-200 bg-red-50 p-4 space-y-2 text-center">
                      <AlertCircle className="w-6 h-6 text-red-600 mx-auto" />
                      <p className="text-sm font-medium text-red-700">{diagnosisError}</p>
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
                            <h4 className="text-sm font-semibold text-text-primary">
                              Chẩn đoán bài nộp
                            </h4>
                            <p className="text-xs text-text-secondary">
                              {detail.problem_name}
                            </p>
                          </div>
                        </div>
                        <Badge variant="wa" className="font-mono text-xs">
                          {diagnosis.error_category}
                        </Badge>
                      </div>

                      {/* Single Cohesive Paragraph */}
                      <div className="rounded-md bg-card-subtle/70 border border-border/70 p-4">
                        <MarkdownMath
                          content={diagnosis.advice || diagnosis.summary || ''}
                          className="markdown-submission text-sm leading-7 text-text-primary"
                        />
                      </div>

                      <div className="pt-1 flex justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRunDiagnosis(true)}
                          disabled={diagnosing}
                          className="min-h-9 gap-1.5 px-2.5 text-xs"
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
                        <h4 className="text-sm font-semibold text-text-primary">
                          Chưa có nhận xét cho bài nộp này
                        </h4>
                        <p className="mx-auto max-w-md text-sm leading-relaxed text-text-secondary">
                          Chẩn đoán sẽ dựa trên đề bài, mã nguồn và kết quả kiểm thử.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRunDiagnosis(false)}
                        className="min-h-10 gap-1.5 border-red-200 bg-red-50 px-3 text-xs text-red-700 hover:bg-red-100"
                      >
                        <Stethoscope className="w-3.5 h-3.5 text-red-600" />
                        <span>Chẩn đoán bài nộp này</span>
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
