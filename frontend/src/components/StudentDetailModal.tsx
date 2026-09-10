import React from 'react';
import { StudentDetailResponseData } from '../types';
import { User, Users, Trophy, Activity, Clock, AlertOctagon, AlertCircle, BarChart3, ExternalLink } from 'lucide-react';
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

interface StudentDetailModalProps {
  data: StudentDetailResponseData | null;
  loading: boolean;
  onClose: () => void;
  onOpenDashboard: (userId: number) => void;
}

const ALERT_META: Record<string, { label: string; variant: 'wa' | 'tle' | 'secondary'; icon: React.ReactNode }> = {
  STUCK: {
    label: 'Kẹt bài (>8 lần sai)',
    variant: 'wa',
    icon: <AlertOctagon className="w-3.5 h-3.5" />,
  },
  GAP: {
    label: 'Hổng kiến thức nền',
    variant: 'tle',
    icon: <AlertCircle className="w-3.5 h-3.5" />,
  },
  INACTIVE: {
    label: 'Chưa nộp bài >7 ngày',
    variant: 'secondary',
    icon: <Clock className="w-3.5 h-3.5" />,
  },
};

const barColor = (score: number) => {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 50) return 'bg-sky-500';
  if (score >= 20) return 'bg-amber-500';
  return 'bg-rose-500';
};

export const StudentDetailModal: React.FC<StudentDetailModalProps> = ({
  data,
  loading,
  onClose,
  onOpenDashboard,
}) => {
  const isOpen = loading || !!data;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {loading || !data ? (
          <div className="space-y-3 py-6">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-32 w-full" />
            <p className="text-xs text-text-tertiary">Đang tải hồ sơ chi tiết học sinh...</p>
          </div>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-start gap-3">
                <div className="h-9 w-9 rounded-md bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary flex-shrink-0">
                  <User className="w-5 h-5" />
                </div>
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <DialogTitle className="text-base font-semibold">
                      {data.name}
                    </DialogTitle>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      #{data.user_id}
                    </Badge>
                  </div>
                  <DialogDescription className="text-xs">
                    @{data.username} • Hạng{' '}
                    <span className="text-text-primary font-medium">{data.display_rank}</span> •{' '}
                    <span className="font-mono text-sky-700 font-medium">{data.points} pts</span>
                  </DialogDescription>
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <Users className="w-3.5 h-3.5 text-text-tertiary" />
                    {data.organizations.length > 0 ? (
                      data.organizations.map((org) => (
                        <Badge key={org} variant="secondary" className="text-[10px] font-sans">
                          {org}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-[10px] text-text-tertiary">Chưa thuộc lớp nào</span>
                    )}
                  </div>
                </div>
              </div>
            </DialogHeader>

            {/* Alerts */}
            {data.alerts.length > 0 && (
              <div className="flex flex-wrap gap-1.5 py-1">
                {data.alerts.map((alert) => {
                  const meta = ALERT_META[alert] || {
                    label: alert,
                    variant: 'secondary',
                    icon: null,
                  };
                  return (
                    <Badge key={alert} variant={meta.variant} className="gap-1 text-[11px] py-0.5 px-2">
                      {meta.icon}
                      {meta.label}
                    </Badge>
                  );
                })}
              </div>
            )}

            {/* 8-pillar algorithm competencies */}
            <div className="rounded-md border border-border bg-card-subtle/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-text-primary flex items-center gap-1.5">
                  <BarChart3 className="w-3.5 h-3.5 text-brand-primary" />
                  Năng lực 8 Trụ cột Thuật toán
                </h4>
                {data.time_range && data.time_range !== 'all' && (
                  <Badge variant="outline" className="text-[10px] font-sans text-brand-primary border-brand-primary/30 bg-brand-primary/5">
                    {data.time_range === '1d' ? '1 ngày qua' : data.time_range === '7d' ? '1 tuần qua' : data.time_range === '30d' ? '1 tháng qua' : '1 năm qua'}
                  </Badge>
                )}
              </div>
              <div className="space-y-2">
                {data.bloom_scores.map((b) => (
                  <div key={b.group_id} className="space-y-1">
                    <div className="flex justify-between text-[11px] text-text-secondary">
                      <span>{b.label}</span>
                      <span className="font-mono font-medium">{b.score}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-card rounded-full overflow-hidden border border-border/40">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${barColor(b.score)}`}
                        style={{ width: `${Math.min(100, b.score)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="rounded-md border border-border bg-card-subtle/50 p-2.5 space-y-1">
                <Trophy className="w-3.5 h-3.5 text-emerald-600" />
                <p className="text-sm font-bold text-text-primary font-mono">
                  {data.summary.total_solved_unique}
                </p>
                <p className="text-[10px] text-text-tertiary">Bài đã giải</p>
              </div>

              <div className="rounded-md border border-border bg-card-subtle/50 p-2.5 space-y-1">
                <Activity className="w-3.5 h-3.5 text-brand-primary" />
                <p className="text-sm font-bold text-text-primary font-mono">
                  {data.summary.total_submissions_7d}
                </p>
                <p className="text-[10px] text-text-tertiary">Lượt nộp 7 ngày</p>
              </div>

              <div className="rounded-md border border-border bg-card-subtle/50 p-2.5 space-y-1">
                <BarChart3 className="w-3.5 h-3.5 text-purple-600" />
                <p className="text-sm font-bold text-text-primary font-mono">{data.problem_count}</p>
                <p className="text-[10px] text-text-tertiary">Tổng bài đã nộp</p>
              </div>

              <div className="rounded-md border border-border bg-card-subtle/50 p-2.5 space-y-1">
                <Clock className="w-3.5 h-3.5 text-amber-600" />
                <p className="text-[11px] font-bold text-text-primary font-mono leading-5 truncate">
                  {data.last_submission_at
                    ? new Date(data.last_submission_at).toLocaleDateString('vi-VN')
                    : 'Chưa có'}
                </p>
                <p className="text-[10px] text-text-tertiary">Nộp gần nhất</p>
              </div>
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" size="sm" onClick={onClose} className="text-xs">
                Đóng
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => onOpenDashboard(data.user_id)}
                className="text-xs gap-1.5"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Xem trang học sinh
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
