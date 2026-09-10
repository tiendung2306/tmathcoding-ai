import React from 'react';
import { ClassHeatmapResponseData, TimeRange } from '../types';
import { AlertCircle, AlertOctagon, Clock, Layers } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { TimeRangeFilter } from './TimeRangeFilter';

interface ClassHeatmapProps {
  data: ClassHeatmapResponseData;
  onSelectStudent: (userId: number, name: string) => void;
  timeRange?: TimeRange;
  onTimeRangeChange?: (range: TimeRange) => void;
}

export const ClassHeatmap: React.FC<ClassHeatmapProps> = ({
  data,
  onSelectStudent,
  timeRange,
  onTimeRangeChange,
}) => {
  const getCellColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (score >= 50) return 'bg-sky-50 text-sky-700 border-sky-200';
    if (score >= 20) return 'bg-amber-50 text-amber-700 border-amber-200';
    if (score > 0) return 'bg-red-50 text-red-700 border-red-200';
    return 'bg-card-subtle text-text-secondary border-border/40';
  };

  const getAlertBadge = (alert: string) => {
    switch (alert) {
      case 'STUCK':
        return (
          <Badge variant="wa" className="gap-1 text-[10px] py-0 px-1" title="Kẹt bài: >= 8 lần nộp sai trong 24h">
            <AlertOctagon className="w-2.5 h-2.5" /> Kẹt bài
          </Badge>
        );
      case 'GAP':
        return (
          <Badge variant="tle" className="gap-1 text-[10px] py-0 px-1" title="Hổng nền tảng">
            <AlertCircle className="w-2.5 h-2.5" /> Hổng kiến thức
          </Badge>
        );
      case 'INACTIVE':
        return (
          <Badge variant="secondary" className="gap-1 text-[10px] py-0 px-1" title="> 7 ngày không nộp bài">
            <Clock className="w-2.5 h-2.5" /> Ngừng nộp
          </Badge>
        );
      default:
        return null;
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
        <div>
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="w-4 h-4 text-brand-primary" />
            Bản đồ năng lực lớp học (8 Trụ cột thuật toán)
          </CardTitle>
          <CardDescription className="text-xs">
            Lớp: <span className="text-text-primary font-medium">{data.organization_name}</span>
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {timeRange && onTimeRangeChange && (
            <TimeRangeFilter value={timeRange} onChange={onTimeRangeChange} />
          )}
          <Badge variant="outline" className="font-mono text-xs">
            {data.students.length} học sinh
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-0 pb-3">
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-border bg-card-subtle/80 text-text-secondary">
                <th className="py-2.5 px-3 font-semibold text-[11px] uppercase tracking-wider sticky left-0 bg-card-subtle z-10 border-r border-border/40">Học sinh</th>
                {data.columns.map((col, idx) => (
                  <th key={idx} className="py-2.5 px-3 font-semibold text-[11px] text-center uppercase tracking-wider">
                    {col}
                  </th>
                ))}
                <th className="py-2.5 px-3 font-semibold text-[11px] text-center uppercase tracking-wider">Cảnh báo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {data.students.map((st) => (
                <tr
                  key={st.user_id}
                  onClick={() => onSelectStudent(st.user_id, st.student_name)}
                  className="hover:bg-card-hover cursor-pointer transition-colors"
                >
                  <td className="py-2 px-3 font-medium text-text-primary flex items-center gap-2 sticky left-0 bg-card z-10 border-r border-border/40">
                    <span className="truncate max-w-[140px] sm:max-w-none">{st.student_name}</span>
                    <span className="text-[10px] font-mono text-text-tertiary">#{st.user_id}</span>
                  </td>
                  {st.scores.map((score, sIdx) => (
                    <td key={sIdx} className="py-2 px-2 text-center">
                      <span
                        className={`inline-block w-12 py-0.5 rounded-sm text-xs font-mono font-medium border ${getCellColor(
                          score
                        )}`}
                      >
                        {score}%
                      </span>
                    </td>
                  ))}
                  <td className="py-2 px-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {st.alerts.map((alt, aIdx) => (
                        <React.Fragment key={aIdx}>{getAlertBadge(alt)}</React.Fragment>
                      ))}
                      {st.alerts.length === 0 && <span className="text-text-disabled">-</span>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            {/* Class Averages Row */}
            <tfoot>
              <tr className="border-t-2 border-border bg-card-subtle font-semibold">
                <td className="py-2.5 px-3 text-text-primary text-[11px] uppercase tracking-wider sticky left-0 bg-card-subtle z-10 border-r border-border/40">
                  Trung bình lớp
                </td>
                {data.class_averages.map((avg, idx) => (
                  <td key={idx} className="py-2.5 px-2 text-center">
                    <span className="inline-block w-12 py-0.5 rounded-sm text-xs font-mono font-bold bg-card text-sky-700 border border-border">
                      {Math.round(avg)}%
                    </span>
                  </td>
                ))}
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
