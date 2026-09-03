import React from 'react';
import { SkillTreeNodeData } from '../types';
import { CheckCircle, AlertTriangle, XCircle, Lock } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Badge } from './ui/badge';

interface SkillTreeProps {
  nodes: SkillTreeNodeData[];
}

export const SkillTree: React.FC<SkillTreeProps> = ({ nodes }) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'GREEN':
        return (
          <Badge variant="ac" className="gap-1 text-[10px]">
            <CheckCircle className="w-2.5 h-2.5" /> Đạt
          </Badge>
        );
      case 'YELLOW':
        return (
          <Badge variant="tle" className="gap-1 text-[10px]">
            <AlertTriangle className="w-2.5 h-2.5" /> Đang rèn
          </Badge>
        );
      case 'RED':
        return (
          <Badge variant="wa" className="gap-1 text-[10px]">
            <XCircle className="w-2.5 h-2.5" /> Cần luyện
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary" className="gap-1 text-[10px] text-text-disabled">
            <Lock className="w-2.5 h-2.5" /> Chưa mở
          </Badge>
        );
    }
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-sm">Cây kỹ năng</CardTitle>
          <CardDescription className="text-xs">
            Mức độ thuần thục theo từng chuyên đề thuật toán
          </CardDescription>
        </div>
        <div className="flex items-center gap-3 text-xs text-text-secondary">
          <span className="flex items-center gap-1.5 text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-600"></span> Đạt
          </span>
          <span className="flex items-center gap-1.5 text-[11px]">
            <span className="w-2 h-2 rounded-full bg-amber-600"></span> Đang rèn
          </span>
          <span className="flex items-center gap-1.5 text-[11px]">
            <span className="w-2 h-2 rounded-full bg-red-600"></span> Cần luyện
          </span>
        </div>
      </CardHeader>

      <CardContent className="flex-1 pt-0 pb-3">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-[460px] overflow-y-auto pr-1">
          {nodes.map((node) => (
            <div
              key={node.topic_id}
              className={`border rounded-md p-3 transition-colors ${
                node.status === 'GREEN'
                  ? 'border-emerald-200 bg-emerald-50/60'
                  : node.status === 'YELLOW'
                  ? 'border-amber-200 bg-amber-50/60'
                  : node.status === 'RED'
                  ? 'border-red-200 bg-red-50/60'
                  : 'border-border/60 bg-card-subtle/40 opacity-70 hover:opacity-100'
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="min-w-0 flex-1">
                  <span className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider block truncate">
                    {node.key}
                  </span>
                  <h4 className="text-xs font-medium text-text-primary truncate" title={node.name}>
                    {node.name}
                  </h4>
                </div>
                <div className="flex-shrink-0">{getStatusBadge(node.status)}</div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-card h-1.5 rounded-full overflow-hidden mb-1.5 border border-border/40">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    node.status === 'GREEN'
                      ? 'bg-emerald-600'
                      : node.status === 'YELLOW'
                      ? 'bg-amber-600'
                      : node.status === 'RED'
                      ? 'bg-red-600'
                      : 'bg-slate-300'
                  }`}
                  style={{ width: `${node.mastery_score}%` }}
                />
              </div>

              <div className="flex justify-between text-[10px] text-text-secondary">
                <span>Tiến độ</span>
                <span className="font-mono font-medium">{node.mastery_score}%</span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
