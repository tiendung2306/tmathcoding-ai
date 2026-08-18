import React from 'react';
import { SkillTreeNodeData } from '../types';
import { CheckCircle, AlertTriangle, XCircle, Lock } from 'lucide-react';

interface SkillTreeProps {
  nodes: SkillTreeNodeData[];
}

export const SkillTree: React.FC<SkillTreeProps> = ({ nodes }) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'GREEN':
        return <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" /> Mastered</span>;
      case 'YELLOW':
        return <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full"><AlertTriangle className="w-3 h-3" /> Practicing</span>;
      case 'RED':
        return <span className="flex items-center gap-1 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-full"><XCircle className="w-3 h-3" /> Weak</span>;
      default:
        return <span className="flex items-center gap-1 text-xs text-slate-500 bg-slate-800 border border-slate-700 px-2 py-0.5 rounded-full"><Lock className="w-3 h-3" /> Locked</span>;
    }
  };

  return (
    <div className="bg-dark-card border border-dark-border rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-slate-200">Sơ Đồ Kỹ Năng 99 Node (Skill Tree)</h2>
          <p className="text-xs text-slate-400">Trạng thái làm bài chi tiết theo các danh mục judge_problemtype</p>
        </div>
        <div className="flex gap-2 text-xs text-slate-400">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Mastered</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Practicing</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Weak</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 max-h-[500px] overflow-y-auto pr-2">
        {nodes.map((node) => (
          <div
            key={node.topic_id}
            className={`border rounded-xl p-3.5 transition-all ${
              node.status === 'GREEN' ? 'border-emerald-500/30 bg-emerald-950/10' :
              node.status === 'YELLOW' ? 'border-amber-500/30 bg-amber-950/10' :
              node.status === 'RED' ? 'border-rose-500/30 bg-rose-950/10' :
              'border-dark-border bg-dark-bg/50 opacity-60'
            }`}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">{node.key}</span>
                <h3 className="text-sm font-medium text-slate-200">{node.name}</h3>
              </div>
              {getStatusBadge(node.status)}
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-dark-bg h-1.5 rounded-full overflow-hidden mb-1">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  node.status === 'GREEN' ? 'bg-emerald-500' :
                  node.status === 'YELLOW' ? 'bg-amber-500' :
                  node.status === 'RED' ? 'bg-rose-500' :
                  'bg-slate-700'
                }`}
                style={{ width: `${node.mastery_score}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>Mastery</span>
              <span className="font-mono">{node.mastery_score}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
