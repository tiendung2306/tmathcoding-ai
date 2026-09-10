import React, { useEffect, useState, useMemo } from 'react';
import { fetchClassHeatmap, fetchStudentDetail } from '../services/api';
import {
  ClassSummaryData,
  ClassStudentItemData,
  ClassHeatmapResponseData,
  StudentDetailResponseData,
  TimeRange,
} from '../types';
import { ClassStudentRoster } from '../components/ClassStudentRoster';
import { ClassHeatmap } from '../components/ClassHeatmap';
import { StudentDetailModal } from '../components/StudentDetailModal';
import { ErrorPanel } from '../components/ErrorPanel';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import {
  Users,
  Layers,
  Filter,
  AlertTriangle,
  Award,
  Activity,
  UserX
} from 'lucide-react';

interface TeacherDashboardProps {
  selectedOrgId: number;
  onSelectOrgId: (orgId: number) => void;
  classes: ClassSummaryData[];
  classStudents: ClassStudentItemData[];
  studentsLoading: boolean;
  onSelectStudent: (userId: number, name: string) => void;
  initialViewMode?: 'roster' | 'heatmap';
}

export const TeacherDashboard: React.FC<TeacherDashboardProps> = ({
  selectedOrgId,
  onSelectOrgId,
  classes,
  classStudents,
  studentsLoading,
  onSelectStudent,
  initialViewMode = 'roster',
}) => {
  const [viewMode, setViewMode] = useState<'roster' | 'heatmap'>(initialViewMode);
  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [heatmapData, setHeatmapData] = useState<ClassHeatmapResponseData | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState<boolean>(false);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<StudentDetailResponseData | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  // Synchronize initialViewMode when passed from navigation
  useEffect(() => {
    if (initialViewMode) {
      setViewMode(initialViewMode);
    }
  }, [initialViewMode]);

  // Load heatmap when switching to heatmap view or when selected class changes
  useEffect(() => {
    if (selectedOrgId && viewMode === 'heatmap') {
      loadHeatmap(selectedOrgId, timeRange);
    }
  }, [selectedOrgId, viewMode]);

  const loadHeatmap = async (orgId: number, range: TimeRange = timeRange) => {
    setHeatmapLoading(true);
    setHeatmapError(null);
    try {
      const data = await fetchClassHeatmap(orgId, range);
      setHeatmapData(data);
    } catch (err) {
      console.error(err);
      setHeatmapError('Không tải được bản đồ nhiệt của lớp. Vui lòng thử lại sau.');
    } finally {
      setHeatmapLoading(false);
    }
  };

  const handleOpenDetailModal = async (userId: number) => {
    setDetailLoading(true);
    try {
      const detail = await fetchStudentDetail(userId, timeRange);
      setDetailData(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  const selectedClass = useMemo(() => {
    return classes.find((c) => c.id === selectedOrgId);
  }, [classes, selectedOrgId]);

  const classNameTitle = selectedClass ? selectedClass.name : `Lớp #${selectedOrgId}`;

  // Summary Metrics
  const summaryStats = useMemo(() => {
    const total = classStudents.length;
    let withAlerts = 0;
    let stuck = 0;
    let inactive = 0;
    let totalPoints = 0;

    classStudents.forEach((s) => {
      totalPoints += s.points;
      if (s.alerts.length > 0) withAlerts++;
      if (s.alerts.includes('STUCK')) stuck++;
      if (s.alerts.includes('INACTIVE')) inactive++;
    });

    const avgPoints = total > 0 ? Math.round(totalPoints / total) : 0;
    return { total, withAlerts, stuck, inactive, avgPoints };
  }, [classStudents]);

  return (
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-4">
      {/* Top Header Card: Title, Class Selector & View Mode Switcher */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-lg sm:text-xl font-bold text-text-primary tracking-tight">
                Không gian quản lý lớp học
              </h1>
              <Badge variant="outline" className="text-[10px] font-mono">
                {classStudents.length} học sinh
              </Badge>
            </div>
            <p className="text-xs text-text-secondary">
              Theo dõi danh bạ học sinh, tiến độ giải bài và bản đồ năng lực chuyên sâu
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Class Selector Dropdown */}
            <div className="flex items-center gap-1.5 bg-card-subtle px-2 py-1 rounded-md border border-border">
              <Filter className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0" />
              <label htmlFor="teacher-class-select" className="sr-only">Chọn lớp học</label>
              <select
                id="teacher-class-select"
                value={selectedOrgId}
                onChange={(e) => onSelectOrgId(Number(e.target.value))}
                className="bg-transparent text-xs text-text-primary rounded-md cursor-pointer pr-2 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              >
                {classes.map((c) => (
                  <option key={c.id} value={c.id} className="bg-card text-text-primary">
                    {c.name} ({c.member_count} HS)
                  </option>
                ))}
              </select>
            </div>

            {/* View Mode Toggle Button Group */}
            <div className="flex items-center bg-card-subtle p-0.5 rounded-md border border-border">
              <button
                type="button"
                onClick={() => setViewMode('roster')}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-sm transition-colors ${
                  viewMode === 'roster'
                    ? 'bg-card text-text-primary shadow-xs border border-border/80'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                <Users className="w-3.5 h-3.5" />
                <span>Danh sách học sinh</span>
              </button>

              <button
                type="button"
                onClick={() => setViewMode('heatmap')}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-sm transition-colors ${
                  viewMode === 'heatmap'
                    ? 'bg-card text-text-primary shadow-xs border border-border/80'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Bản đồ năng lực</span>
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Class Telemetry Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-card border border-border rounded-lg p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-secondary">Sĩ số lớp</span>
            <Users className="w-3.5 h-3.5 text-brand-primary" />
          </div>
          <p className="text-lg font-bold text-text-primary font-mono">
            {summaryStats.total}
          </p>
          <span className="text-[10px] text-text-tertiary">học sinh chính thức</span>
        </div>

        <div className="bg-card border border-border rounded-lg p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-secondary">Cần chú ý</span>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
          </div>
          <p className="text-lg font-bold text-amber-700 font-mono">
            {summaryStats.withAlerts}
          </p>
          <span className="text-[10px] text-text-tertiary">có cảnh báo học tập</span>
        </div>

        <div className="bg-card border border-border rounded-lg p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-secondary">Ngừng nộp bài</span>
            <UserX className="w-3.5 h-3.5 text-rose-600" />
          </div>
          <p className="text-lg font-bold text-rose-700 font-mono">
            {summaryStats.inactive}
          </p>
          <span className="text-[10px] text-text-tertiary">trên 7 ngày chưa nộp</span>
        </div>

        <div className="bg-card border border-border rounded-lg p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-secondary">Điểm trung bình</span>
            <Award className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <p className="text-lg font-bold text-text-primary font-mono">
            {summaryStats.avgPoints.toLocaleString('vi-VN')}
          </p>
          <span className="text-[10px] text-text-tertiary">điểm toàn lớp</span>
        </div>
      </div>

      {/* Main Content Area based on View Mode */}
      {viewMode === 'roster' ? (
        <div id="section-roster">
          <ClassStudentRoster
            students={classStudents}
            classNameTitle={classNameTitle}
            loading={studentsLoading}
            onOpenDetailModal={handleOpenDetailModal}
            onSelectStudentForDashboard={(userId, name) => onSelectStudent(userId, name)}
          />
        </div>
      ) : (
        <div id="section-heatmap">
          {heatmapLoading && !heatmapData ? (
            <div className="space-y-4">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-96 w-full" />
            </div>
          ) : heatmapError && !heatmapData ? (
            <ErrorPanel
              title="Không thể tải bản đồ nhiệt lớp học"
              message={heatmapError}
              onRetry={() => loadHeatmap(selectedOrgId)}
            />
          ) : heatmapData ? (
            <ClassHeatmap
              data={heatmapData}
              onSelectStudent={handleOpenDetailModal}
              timeRange={timeRange}
              onTimeRangeChange={(r) => {
                setTimeRange(r);
                loadHeatmap(selectedOrgId, r);
              }}
            />
          ) : (
            <div className="space-y-4">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-96 w-full" />
            </div>
          )}
        </div>
      )}

      {/* Student Detail Modal */}
      <StudentDetailModal
        data={detailData}
        loading={detailLoading}
        onClose={() => setDetailData(null)}
        onOpenDashboard={(userId) => {
          setDetailData(null);
          onSelectStudent(userId, detailData?.name ?? '');
        }}
      />
    </div>
  );
};
