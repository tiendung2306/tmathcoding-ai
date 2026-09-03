import React, { useEffect, useState } from 'react';
import { fetchTeacherClasses, fetchClassHeatmap, fetchStudentDetail } from '../services/api';
import { ClassHeatmapResponseData, StudentDetailResponseData } from '../types';
import { ClassHeatmap } from '../components/ClassHeatmap';
import { StudentDetailModal } from '../components/StudentDetailModal';
import { ErrorPanel } from '../components/ErrorPanel';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { GraduationCap, Filter } from 'lucide-react';

interface TeacherDashboardProps {
  onSelectStudent: (userId: number, name: string) => void;
}

export const TeacherDashboard: React.FC<TeacherDashboardProps> = ({ onSelectStudent }) => {
  const [classes, setClasses] = useState<any[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<number>(19);
  const [heatmapData, setHeatmapData] = useState<ClassHeatmapResponseData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [classesError, setClassesError] = useState<string | null>(null);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<StudentDetailResponseData | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  useEffect(() => {
    loadClasses();
  }, []);

  useEffect(() => {
    if (selectedOrgId) {
      loadHeatmap(selectedOrgId);
    }
  }, [selectedOrgId]);

  // F2.2: click vào học sinh trong heatmap -> mở modal chi tiết
  const handleRowClick = async (userId: number) => {
    setDetailLoading(true);
    try {
      const detail = await fetchStudentDetail(userId);
      setDetailData(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  const loadClasses = async () => {
    setClassesError(null);
    try {
      const list = await fetchTeacherClasses();
      setClasses(list);
      if (list.length > 0) {
        // If current selectedOrgId is already in the list, keep it; otherwise default to list[0].id
        const exists = list.some((c: any) => c.id === selectedOrgId);
        if (!exists) {
          setSelectedOrgId(list[0].id);
        }
      }
    } catch (err) {
      console.error(err);
      setClassesError('Không tải được danh sách lớp. Vui lòng thử lại.');
    }
  };

  const loadHeatmap = async (orgId: number) => {
    setLoading(true);
    setHeatmapError(null);
    try {
      const data = await fetchClassHeatmap(orgId);
      setHeatmapData(data);
    } catch (err) {
      console.error(err);
      setHeatmapError('Không tải được bản đồ nhiệt của lớp. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-3.5 sm:p-5 lg:p-6 max-w-7xl mx-auto space-y-5">
      {/* Teacher Workspace Header */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-xl font-bold text-text-primary tracking-tight">
              Tổng quan lớp học
            </h1>
            <p className="text-xs text-text-secondary">
              Theo dõi phân bố năng lực học sinh theo từng lớp học
            </p>
          </div>

          {/* Class Selector Dropdown */}
          <div className="flex items-center gap-2.5 bg-card-subtle p-1.5 rounded-md border border-border">
            <Filter className="w-3.5 h-3.5 text-text-tertiary ml-1.5 flex-shrink-0" />
            <select
              value={selectedOrgId}
              onChange={(e) => setSelectedOrgId(Number(e.target.value))}
              aria-label="Chọn lớp học"
              className="bg-transparent text-xs text-text-primary rounded-md cursor-pointer pr-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id} className="bg-card text-text-primary">
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Heatmap Content Area */}
      {loading && !heatmapData ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : heatmapError && !heatmapData ? (
        <div id="section-heatmap">
          <ErrorPanel
            title="Không thể tải bản đồ nhiệt lớp học"
            message={heatmapError}
            onRetry={() => loadHeatmap(selectedOrgId)}
          />
        </div>
      ) : heatmapData ? (
        <div id="section-heatmap">
          <ClassHeatmap data={heatmapData} onSelectStudent={handleRowClick} />
        </div>
      ) : classesError ? (
        <div id="section-heatmap">
          <ErrorPanel
            title="Không thể tải danh sách lớp"
            message={classesError}
            onRetry={loadClasses}
          />
        </div>
      ) : (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      )}

      {/* F2.2: Student Detail Modal */}
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
