import React, { useEffect, useState } from 'react';
import { fetchSkillTree, requestCodeDoctor } from '../services/api';
import { SkillTreeResponseData, CodeDoctorResponseData } from '../types';
import { BloomRadar } from '../components/BloomRadar';
import { SkillTree } from '../components/SkillTree';
import { CodeDoctorModal } from '../components/CodeDoctorModal';
import { Stethoscope, Award, Flame, RefreshCw } from 'lucide-react';

interface StudentDashboardProps {
  studentId: number;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({ studentId }) => {
  const [data, setData] = useState<SkillTreeResponseData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [doctorModalData, setDoctorModalData] = useState<CodeDoctorResponseData | null>(null);
  const [doctorLoading, setDoctorLoading] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, [studentId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchSkillTree(studentId);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDiagnoseMock = async () => {
    setDoctorLoading(true);
    try {
      const res = await requestCodeDoctor(3447100); // Mock submission id
      setDoctorModalData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setDoctorLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 text-brand-blue animate-spin" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Student Overview Header */}
      <div className="bg-gradient-to-r from-dark-card via-dark-card to-dark-bg border border-dark-border rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-xs text-brand-blue font-medium tracking-wide uppercase">Student Competency Overview</span>
          <h1 className="text-2xl font-bold text-slate-100">{data.student_name}</h1>
          <p className="text-xs text-slate-400 mt-1">Học sinh tự do • Đang tích cực rèn luyện trên tmath OJ</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleDiagnoseMock}
            disabled={doctorLoading}
            className="flex items-center gap-2 bg-gradient-to-r from-rose-600 to-rose-700 hover:from-rose-500 hover:to-rose-600 text-white text-sm font-medium px-4 py-2.5 rounded-xl shadow-lg shadow-rose-600/25 transition-all"
          >
            <Stethoscope className="w-4 h-4" />
            {doctorLoading ? 'Đang chẩn đoán...' : 'Hỏi AI Code Doctor (Demo)'}
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <BloomRadar data={data.bloom_radar} />
        </div>
        <div className="lg:col-span-2">
          <SkillTree nodes={data.skill_tree_nodes} />
        </div>
      </div>

      <CodeDoctorModal data={doctorModalData} onClose={() => setDoctorModalData(null)} />
    </div>
  );
};
