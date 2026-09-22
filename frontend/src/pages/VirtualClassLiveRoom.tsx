import React, { useState, useEffect } from 'react';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Square, AlertTriangle, AlertCircle, CheckCircle2, Clock, Inbox, ArchiveX } from 'lucide-react';
import { stopVirtualClass, fetchLiveSubmissions } from '../services/api';
import { SubmissionDetailModal } from '../components/SubmissionDetailModal';

interface VirtualClassLiveRoomProps {
  sessionId: number;
  sessionName: string;
  isActive: boolean;
  onSessionStopped: () => void;
}

export const VirtualClassLiveRoom: React.FC<VirtualClassLiveRoomProps> = ({
  sessionId,
  sessionName,
  isActive,
  onSessionStopped
}) => {
  const [loading, setLoading] = useState(false);
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [lastId, setLastId] = useState(0);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [showConfirmStop, setShowConfirmStop] = useState(false);
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null);

  // Poll submissions every 3 seconds if active, or just fetch once if not active
  useEffect(() => {
    let intervalId: NodeJS.Timeout;
    
    const fetchSubmissions = async () => {
      try {
        setFetchError(null);
        const res = await fetchLiveSubmissions(sessionId, lastId);
        if (res.submissions.length > 0) {
          setSubmissions(prev => {
            return [...res.submissions, ...prev];
          });
          setLastId(res.last_id);
        }
      } catch (err) {
        console.error("Lỗi khi fetch live submissions:", err);
        setFetchError("Không thể tải dữ liệu bài nộp.");
      }
    };

    if (isActive) {
      intervalId = setInterval(fetchSubmissions, 3000);
    } else {
      fetchSubmissions();
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isActive, sessionId, lastId]);

  const handleStopClass = async () => {
    setLoading(true);
    try {
      await stopVirtualClass(sessionId);
      setShowConfirmStop(false);
      onSessionStopped();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Calculate Stats
  const statAiWarnings = submissions.filter(s => s.ai_flags?.is_ai_generated || s.ai_flags?.is_copied).length;
  const statErrors = submissions.filter(s => s.ai_flags?.has_error).length;
  const statAc = submissions.filter(s => s.result === 'AC').length;

  // Determine left border color for a submission card
  const getSubmissionBorderClass = (sub: any): string => {
    if (sub.ai_flags?.is_ai_generated || sub.ai_flags?.is_copied) {
      return 'border-l-[3px] border-l-orange-400';
    }
    if (sub.result === 'AC') {
      return 'border-l-[3px] border-l-emerald-400';
    }
    return 'border-l-[3px] border-l-red-400';
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            {sessionName}
            {isActive ? (
               <Badge variant="ac">Đang diễn ra</Badge>
            ) : (
               <Badge variant="outline">Đã kết thúc</Badge>
            )}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {isActive
              ? 'Theo dõi thời gian thực quá trình làm bài, phát hiện lỗi và sử dụng AI.'
              : 'Xem lại dữ liệu bài nộp của phiên học đã kết thúc.'
            }
          </p>
        </div>
        <div>
          {isActive && (
            <button
              onClick={() => setShowConfirmStop(true)}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md font-medium hover:bg-red-700 transition-colors disabled:opacity-50 shadow-sm"
            >
              <Square className="w-4 h-4 fill-current" />
              Kết thúc lớp học
            </button>
          )}
        </div>
      </div>

      {/* Confirm Stop Dialog */}
      {showConfirmStop && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/50 flex items-center justify-center px-4"
          onClick={() => setShowConfirmStop(false)}
        >
          <Card
            className="p-6 w-full max-w-sm shadow-xl z-50 bg-card border-border animate-modal-in"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-semibold text-text-primary mb-2">Kết thúc phiên học?</h3>
            <p className="text-xs text-text-secondary mb-5">
              Phiên học sẽ dừng lại và không thể bắt đầu lại. Dữ liệu bài nộp vẫn được lưu.
            </p>
            <div className="flex items-center gap-3 justify-end">
              <button
                onClick={() => setShowConfirmStop(false)}
                className="px-4 py-1.5 text-xs font-medium rounded-md border border-border text-text-secondary hover:bg-card-subtle transition-colors"
              >
                Hủy
              </button>
              <button
                onClick={handleStopClass}
                disabled={loading}
                className="px-4 py-1.5 text-xs font-medium rounded-md bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {loading ? 'Đang xử lý...' : 'Xác nhận kết thúc'}
              </button>
            </div>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Feed */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold flex items-center gap-2 border-b border-border pb-2">
            {isActive && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
              </span>
            )}
            {isActive ? 'Luồng bài nộp trực tiếp' : 'Lịch sử bài nộp'}
          </h3>
          
          {/* Error state */}
          {fetchError && submissions.length === 0 && (
            <Card className="p-6 text-center border-dashed border-red-200 bg-red-50/50">
              <AlertCircle className="w-6 h-6 text-red-400 mx-auto mb-2" />
              <p className="text-sm text-red-600 mb-3">{fetchError}</p>
              <button
                onClick={() => {
                  setFetchError(null);
                  setLastId(0);
                }}
                className="text-xs font-medium text-brand-primary hover:underline"
              >
                Thử lại
              </button>
            </Card>
          )}

          {/* Empty state */}
          {!fetchError && submissions.length === 0 ? (
            <Card className="p-10 text-center bg-card-subtle/30 border-dashed">
              {isActive ? (
                <div className="space-y-3">
                  <Inbox className="w-8 h-8 text-text-disabled mx-auto" />
                  <div>
                    <p className="text-sm text-text-secondary">Phiên đang chạy, bài nộp sẽ hiện khi học sinh submit.</p>
                    <div className="dot-bounce mt-3" aria-label="Đang chờ">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <ArchiveX className="w-8 h-8 text-text-disabled mx-auto" />
                  <p className="text-sm text-text-secondary">Không có bài nộp trong phiên này.</p>
                </div>
              )}
            </Card>
          ) : (
            <div className="space-y-3">
              {submissions.map((sub, idx) => (
                <Card key={sub.id || idx} className={`p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-4 animate-in slide-in-from-top-2 fade-in duration-300 ${getSubmissionBorderClass(sub)}`}>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-text-primary">{sub.user_name}</span>
                      <span className="text-xs text-text-tertiary flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(sub.date).toLocaleTimeString('vi-VN')}
                      </span>
                    </div>
                    <p className="text-sm text-text-secondary mb-2">
                      Đã nộp bài <span className="font-medium text-text-primary">{sub.problem_name}</span>
                    </p>
                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      {sub.result === 'AC' ? (
                        <Badge variant="ac" className="px-2 py-0.5">Accepted</Badge>
                      ) : (
                        <Badge variant="wa" className="px-2 py-0.5">{sub.result}</Badge>
                      )}
                      {sub.ai_flags?.is_ai_generated && (
                        <Badge variant="outline" className="border-red-500 text-red-500 bg-red-500/10 px-2 py-0.5 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> Nghi ngờ dùng AI
                        </Badge>
                      )}
                      {sub.ai_flags?.is_copied && (
                        <Badge variant="outline" className="border-orange-500 text-orange-500 bg-orange-500/10 px-2 py-0.5 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> Đạo văn (Chép Code)
                        </Badge>
                      )}
                      {sub.ai_flags?.has_error && (
                        <Badge variant="outline" className="border-yellow-500 text-yellow-600 bg-yellow-500/10 px-2 py-0.5 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> Chẩn đoán lỗi
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-lg font-mono font-bold text-text-primary">{sub.points} <span className="text-xs text-text-secondary font-sans font-normal">pts</span></div>
                    <button
                      onClick={() => setSelectedSubmissionId(sub.id)}
                      className="text-xs text-brand-primary hover:underline mt-2 font-medium"
                    >
                      Xem chi tiết
                    </button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar Stats */}
        <div className="space-y-6">
          <Card className="p-4 sticky top-20">
            <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-4">
              Thống kê phiên học
            </h4>
            <div className="space-y-2.5">
              <div className="flex justify-between items-center rounded-md bg-slate-50 border border-slate-100 px-3 py-2.5">
                <span className="text-xs text-text-secondary">Tổng bài nộp</span>
                <span className="text-lg font-mono font-semibold text-text-primary">{submissions.length}</span>
              </div>
              <div className="flex justify-between items-center rounded-md bg-red-50 border border-red-100 px-3 py-2.5">
                <span className="text-xs text-red-600 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5"/>
                  Cảnh báo AI / Copy
                </span>
                <span className="text-lg font-mono font-semibold text-red-600">{statAiWarnings}</span>
              </div>
              <div className="flex justify-between items-center rounded-md bg-amber-50 border border-amber-100 px-3 py-2.5">
                <span className="text-xs text-amber-600 flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5"/>
                  Có lỗi (WA/RTE)
                </span>
                <span className="text-lg font-mono font-semibold text-amber-600">{statErrors}</span>
              </div>
              <div className="flex justify-between items-center rounded-md bg-emerald-50 border border-emerald-100 px-3 py-2.5">
                <span className="text-xs text-emerald-600 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5"/>
                  Accepted
                </span>
                <span className="text-lg font-mono font-semibold text-emerald-600">{statAc}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Submission Detail Modal */}
      <SubmissionDetailModal
        submissionId={selectedSubmissionId}
        isOpen={selectedSubmissionId !== null}
        onClose={() => setSelectedSubmissionId(null)}
      />
    </div>
  );
};
