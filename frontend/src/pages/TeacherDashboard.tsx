import React, { useEffect, useState } from 'react';
import { fetchTeacherClasses, fetchClassHeatmap } from '../services/api';
import { ClassHeatmapResponseData } from '../types';
import { ClassHeatmap } from '../components/ClassHeatmap';
import { Users, Filter, RefreshCw } from 'lucide-react';

interface TeacherDashboardProps {
  onSelectStudent: (userId: number, name: string) => void;
}

export const TeacherDashboard: React.FC<TeacherDashboardProps> = ({ onSelectStudent }) => {
  const [classes, setClasses] = useState<any[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<number>(19);
  const [heatmapData, setHeatmapData] = useState<ClassHeatmapResponseData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    loadClasses();
  }, []);

  useEffect(() => {
    if (selectedOrgId) {
      loadHeatmap(selectedOrgId);
    }
  }, [selectedOrgId]);

  const loadClasses = async () => {
    try {
      const list = await fetchTeacherClasses();
      setClasses(list);
      if (list.length > 0) {
        setSelectedOrgId(list[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadHeatmap = async (orgId: number) => {
    setLoading(true);
    try {
      const data = await fetchClassHeatmap(orgId);
      setHeatmapData(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Teacher Header & Class Selector */}
      <div className="bg-gradient-to-r from-dark-card via-dark-card to-dark-bg border border-dark-border rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-xs text-brand-purple font-medium tracking-wide uppercase">Teacher Workspace & Class Management</span>
          <h1 className="text-2xl font-bold text-slate-100">Bảng Quản Lý Lớp Học & Super Admin</h1>
          <p className="text-xs text-slate-400 mt-1">Super Admin có quyền xem và tìm kiếm toàn bộ 252 lớp học và 21,416 học sinh</p>
        </div>

        {/* Class Selector Dropdown */}
        <div className="flex items-center gap-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={selectedOrgId}
            onChange={(e) => setSelectedOrgId(Number(e.target.value))}
            className="bg-dark-bg border border-dark-border rounded-xl px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-brand-blue"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} (ID: {c.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading || !heatmapData ? (
        <div className="flex items-center justify-center h-96">
          <RefreshCw className="w-8 h-8 text-brand-purple animate-spin" />
        </div>
      ) : (
        <ClassHeatmap data={heatmapData} onSelectStudent={onSelectStudent} />
      )}
    </div>
  );
};
