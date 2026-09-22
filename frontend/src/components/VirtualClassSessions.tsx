import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Play, Calendar, Clock, ArrowRight, Radio } from 'lucide-react';
import { ClassSummaryData } from '../types';
import { getVirtualClassSessions, startVirtualClass } from '../services/api';

interface VirtualClassSessionsProps {
  selectedOrgId?: number;
  classes: ClassSummaryData[];
  onEnterSession: (sessionId: number, sessionName: string, isActive: boolean) => void;
}

export const VirtualClassSessions: React.FC<VirtualClassSessionsProps> = ({
  selectedOrgId,
  classes,
  onEnterSession
}) => {
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedClass = classes.find((c) => c.id === selectedOrgId);

  useEffect(() => {
    if (selectedOrgId) {
      loadSessions(selectedOrgId);
    }
  }, [selectedOrgId]);

  // Auto-dismiss error after 5 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const loadSessions = async (orgId: number) => {
    setLoading(true);
    try {
      const data = await getVirtualClassSessions(orgId);
      setSessions(data.sessions);
      setActiveSession(data.active_session);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSession = async () => {
    if (!selectedOrgId) return;
    setLoading(true);
    setError(null);
    try {
      const newSession = await startVirtualClass(selectedOrgId);
      onEnterSession(newSession.id, newSession.name, true);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Lỗi khi tạo phiên học ảo. Vui lòng thử lại.");
      setLoading(false);
    }
  };

  if (!selectedClass) {
    return (
      <div className="p-6 text-center text-text-secondary">
        Vui lòng chọn một lớp học để bắt đầu.
      </div>
    );
  }

  const endedSessions = sessions.filter(s => s.end_time !== null);

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Radio className="w-5 h-5 text-brand-primary" />
            Lớp học ảo: {selectedClass.name}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Chọn một phiên học đang diễn ra để theo dõi, hoặc xem lại lịch sử các phiên trước đó.
          </p>
        </div>
        <div>
          <button
            onClick={handleCreateSession}
            disabled={loading || activeSession !== null}
            className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
              activeSession !== null 
                ? 'bg-card-subtle text-text-disabled cursor-not-allowed border border-border'
                : 'bg-brand-primary text-white hover:bg-brand-primary/90 shadow-sm'
            }`}
          >
            <Play className="w-4 h-4" />
            Bắt đầu phiên học mới
          </button>
          {activeSession && (
            <p className="text-[11px] text-orange-500 mt-2 text-right font-medium">
              *Đang có phiên học diễn ra
            </p>
          )}
        </div>
      </div>

      {/* Inline error message */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700 text-xs font-medium ml-4 shrink-0"
          >
            Đóng
          </button>
        </div>
      )}

      {/* Active session section */}
      {activeSession && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
            </span>
            Phiên đang diễn ra
          </h3>
          <Card className="p-4 border-l-[3px] border-l-brand-primary bg-blue-50/40 hover:bg-blue-50/60 transition-colors">
            <div className="flex items-start justify-between mb-3">
              <h4 className="font-semibold text-text-primary text-sm flex items-center gap-2">
                {activeSession.name}
              </h4>
              <Badge variant="ac">Đang diễn ra</Badge>
            </div>
            
            <div className="space-y-1.5 text-xs text-text-secondary mb-4">
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" />
                Bắt đầu: {new Date(activeSession.start_time).toLocaleString('vi-VN')}
              </div>
            </div>

            <button
              onClick={() => onEnterSession(activeSession.id, activeSession.name, true)}
              className="w-full py-2 rounded-md text-sm font-medium flex items-center justify-center gap-1.5 transition-colors bg-brand-primary text-white hover:bg-brand-primary/90 shadow-sm"
            >
              Vào phòng ngay
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </Card>
        </div>
      )}

      {/* Past sessions */}
      <div className="space-y-4 mt-2">
        <h3 className="text-sm font-semibold text-text-primary border-b border-border pb-2">
          {activeSession ? 'Phiên học trước đó' : 'Danh sách Phiên học'}
        </h3>

        {loading ? (
          <div className="text-sm text-text-secondary animate-pulse">Đang tải dữ liệu...</div>
        ) : endedSessions.length === 0 && !activeSession ? (
          <Card className="p-12 border-dashed flex flex-col items-center justify-center text-center bg-card-subtle/50">
            <p className="text-sm text-text-secondary">Lớp này chưa có phiên học ảo nào.</p>
          </Card>
        ) : endedSessions.length === 0 ? (
          <p className="text-xs text-text-tertiary py-2">Chưa có phiên học nào kết thúc.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {endedSessions.map((session) => (
              <Card 
                key={session.id} 
                className="p-4 hover:border-border-strong transition-colors group"
              >
                <div className="flex items-start justify-between mb-3">
                  <h4 className="font-semibold text-text-primary text-sm">
                    {session.name}
                  </h4>
                  <Badge variant="outline" className="text-text-tertiary">Đã kết thúc</Badge>
                </div>
                
                <div className="space-y-1.5 text-xs text-text-tertiary mb-4">
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5" />
                    Bắt đầu: {new Date(session.start_time).toLocaleString('vi-VN')}
                  </div>
                  {session.end_time && (
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5" />
                      Kết thúc: {new Date(session.end_time).toLocaleString('vi-VN')}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => onEnterSession(session.id, session.name, false)}
                  className="w-full py-1.5 rounded-md text-xs font-medium flex items-center justify-center gap-1.5 transition-colors border border-border text-text-secondary hover:bg-card-subtle hover:text-text-primary group-hover:border-border-strong"
                >
                  Xem lại dữ liệu
                  <ArrowRight className="w-3 h-3" />
                </button>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
