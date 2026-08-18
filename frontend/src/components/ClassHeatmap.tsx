import React from 'react';
import { ClassHeatmapResponseData } from '../types';
import { AlertCircle, AlertOctagon, Clock } from 'lucide-react';

interface ClassHeatmapProps {
  data: ClassHeatmapResponseData;
  onSelectStudent: (userId: number, name: string) => void;
}

export const ClassHeatmap: React.FC<ClassHeatmapProps> = ({ data, onSelectStudent }) => {
  const getCellColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-600/40 text-emerald-300 border-emerald-500/30';
    if (score >= 50) return 'bg-emerald-800/30 text-emerald-400 border-emerald-600/20';
    if (score >= 20) return 'bg-amber-600/30 text-amber-300 border-amber-500/30';
    return 'bg-rose-600/30 text-rose-300 border-rose-500/30';
  };

  const getAlertBadge = (alert: string) => {
    switch (alert) {
      case 'STUCK':
        return <span className="flex items-center gap-1 text-[10px] text-rose-400 bg-rose-500/20 border border-rose-500/30 px-1.5 py-0.5 rounded" title="Kẹt bài: nộp sai >= 8 lần trong 24h"><AlertOctagon className="w-3 h-3" /> STUCK</span>;
      case 'GAP':
        return <span className="flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/20 border border-amber-500/30 px-1.5 py-0.5 rounded" title="Hổng nền tảng"><AlertCircle className="w-3 h-3" /> GAP</span>;
      case 'INACTIVE':
        return <span className="flex items-center gap-1 text-[10px] text-slate-400 bg-slate-800 border border-slate-700 px-1.5 py-0.5 rounded" title="> 7 ngày không nộp bài"><Clock className="w-3 h-3" /> INACTIVE</span>;
      default:
        return null;
    }
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-slate-200">Bản Đồ Nhiệt Năng Lực 2D Lớp Học (Class Heatmap)</h2>
          <p className="text-xs text-slate-400">{data.organization_name} • Thống kê tỷ lệ AC và cờ cảnh báo thông minh</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-dark-border text-slate-400">
              <th className="py-2.5 px-3 font-medium">Học sinh</th>
              {data.columns.map((col, idx) => (
                <th key={idx} className="py-2.5 px-3 font-medium text-center">{col}</th>
              ))}
              <th className="py-2.5 px-3 font-medium text-center">Cảnh báo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-border/50">
            {data.students.map((st) => (
              <tr
                key={st.user_id}
                onClick={() => onSelectStudent(st.user_id, st.student_name)}
                className="hover:bg-dark-hover/50 cursor-pointer transition-colors"
              >
                <td className="py-3 px-3 font-medium text-slate-200">{st.student_name}</td>
                {st.scores.map((score, sIdx) => (
                  <td key={sIdx} className="py-3 px-3 text-center">
                    <span className={`inline-block w-12 py-1 rounded-md text-xs font-mono font-semibold border ${getCellColor(score)}`}>
                      {score}%
                    </span>
                  </td>
                ))}
                <td className="py-3 px-3 text-center">
                  <div className="flex items-center justify-center gap-1">
                    {st.alerts.map((alt, aIdx) => (
                      <React.Fragment key={aIdx}>{getAlertBadge(alt)}</React.Fragment>
                    ))}
                    {st.alerts.length === 0 && <span className="text-slate-600">-</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
