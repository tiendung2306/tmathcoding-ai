import React, { useState } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { BloomRadarData, PillarBreakdownItem } from '../types';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Compass, ChevronDown, ChevronUp, Info, CheckCircle2, AlertTriangle } from 'lucide-react';

interface BloomRadarProps {
  data: BloomRadarData;
}

const RANGE_LABELS: Record<string, string> = {
  '1d': '1 ngày qua',
  '7d': '1 tuần qua',
  '30d': '1 tháng qua',
  '1y': '1 năm qua',
  'all': 'Cả quá trình',
};

const PILLAR_CONFIG = [
  { key: 'quy_hoach_dong', subject: 'Quy hoạch động', fullSubject: 'Quy hoạch động (DP)' },
  { key: 'cau_truc_du_lieu', subject: 'Cấu trúc dữ liệu', fullSubject: 'Cấu trúc dữ liệu (DS)' },
  { key: 'xu_ly_xau', subject: 'Xử lý xâu', fullSubject: 'Xử lý xâu ký tự' },
  { key: 'ham_co_ban', subject: 'Hàm cơ bản', fullSubject: 'Hàm & Đệ quy cơ bản' },
  { key: 'toan_hoc', subject: 'Toán học', fullSubject: 'Toán học & Số học' },
  { key: 'hinh_hoc', subject: 'Hình học', fullSubject: 'Hình học tính toán' },
  { key: 'do_thi', subject: 'Lý thuyết đồ thị', fullSubject: 'Lý thuyết đồ thị' },
  { key: 'tham_lam', subject: 'Thuật toán tham lam', fullSubject: 'Thuật toán tham lam' },
];

export const BloomRadar: React.FC<BloomRadarProps> = ({ data }) => {
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);
  const [selectedPillarKey, setSelectedPillarKey] = useState<string | null>(null);

  const isPillars = data.quy_hoach_dong !== undefined;

  const chartData = isPillars
    ? PILLAR_CONFIG.map((p) => {
        const score = (data as any)[p.key] || 0;
        const b = data.breakdown ? data.breakdown[p.key] : null;
        return {
          key: p.key,
          subject: p.subject,
          fullSubject: p.fullSubject,
          A: score,
          fullMark: 100,
          breakdown: b,
        };
      })
    : [
        { subject: 'A - Nhớ', fullSubject: 'Mức A (Nhớ)', A: data.A_Nho || 0, fullMark: 100 },
        { subject: 'B - Hiểu', fullSubject: 'Mức B (Hiểu)', A: data.B_Hieu || 0, fullMark: 100 },
        { subject: 'C - Vận dụng', fullSubject: 'Mức C (Vận dụng)', A: data.C_VanDung || 0, fullMark: 100 },
        { subject: 'D - Phân tích', fullSubject: 'Mức D (Phân tích)', A: data.D_PhanTich || 0, fullMark: 100 },
        { subject: 'E - Đánh giá', fullSubject: 'Mức E (Đánh giá)', A: data.E_DanhGia || 0, fullMark: 100 },
        { subject: 'F - Đặc biệt', fullSubject: 'Mức F (Sáng tạo)', A: data.F_DacBiet || 0, fullMark: 100 },
      ];

  const timeRangeLabel =
    data.time_range && data.time_range !== 'all'
      ? RANGE_LABELS[data.time_range] || data.time_range
      : null;

  return (
    <Card className="h-full flex flex-col border-border bg-card">
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-md bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary">
            <Compass className="w-3.5 h-3.5" />
          </div>
          <div>
            <CardTitle className="text-sm font-semibold">
              {isPillars ? 'Bản đồ Năng lực Thuật toán' : 'Phân bố Năng lực Bloom'}
            </CardTitle>
            <p className="text-[11px] text-text-tertiary">
              Đánh giá đa chiều 4 thành phần: Độ khó bài AC, hành vi nộp, tối ưu thời gian/bộ nhớ và chất lượng mã nguồn
            </p>
          </div>
        </div>
        {timeRangeLabel && (
          <Badge variant="outline" className="text-[10px] font-sans font-medium text-brand-primary border-brand-primary/30 bg-brand-primary/5">
            {timeRangeLabel}
          </Badge>
        )}
      </CardHeader>

      <CardContent className="pt-2 pb-4 flex-1 flex flex-col items-center justify-center">
        {/* Vùng vẽ Radar phóng to */}
        <div className="h-[400px] sm:h-[460px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="74%" data={chartData}>
              <PolarGrid stroke="#E2E8F0" />
              <PolarAngleAxis
                dataKey="subject"
                stroke="#64748B"
                tick={{ fill: '#334155', fontSize: 12, fontWeight: 500 }}
              />
              <PolarRadiusAxis
                angle={30}
                domain={[0, 100]}
                stroke="#CBD5E1"
                tick={{ fill: '#64748B', fontSize: 9 }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload;
                    const b: PillarBreakdownItem | undefined = item.breakdown;
                    return (
                      <div className="bg-card/95 backdrop-blur border border-border shadow-xl rounded-lg p-3 text-xs max-w-xs sm:max-w-sm space-y-2 z-50">
                        <div className="flex items-center justify-between gap-2 border-b border-border/60 pb-1.5">
                          <p className="font-bold text-text-primary text-sm">{item.fullSubject || item.subject}</p>
                          <span className="font-mono font-bold text-brand-primary text-sm bg-brand-primary/10 px-2 py-0.5 rounded">
                            {item.A}%
                          </span>
                        </div>

                        {b ? (
                          <div className="space-y-2 pt-0.5">
                            <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                              <div className="bg-card-subtle/80 px-2 py-1 rounded border border-border/40">
                                <span className="text-text-secondary block text-[10px]">🎯 Nền tảng độ khó</span>
                                <span className="font-mono font-semibold text-text-primary">{b.base_score}đ / 50đ</span>
                              </div>
                              <div className="bg-card-subtle/80 px-2 py-1 rounded border border-border/40">
                                <span className="text-text-secondary block text-[10px]">⚡ Độ chính xác nộp</span>
                                <span className={`font-mono font-semibold ${b.precision_mod >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                                  {b.precision_mod >= 0 ? `+${b.precision_mod}` : b.precision_mod}đ
                                </span>
                              </div>
                              <div className="bg-card-subtle/80 px-2 py-1 rounded border border-border/40">
                                <span className="text-text-secondary block text-[10px]">⏱️ Tối ưu thực thi</span>
                                <span className={`font-mono font-semibold ${b.efficiency_mod >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                                  {b.efficiency_mod >= 0 ? `+${b.efficiency_mod}` : b.efficiency_mod}đ
                                </span>
                              </div>
                              <div className="bg-card-subtle/80 px-2 py-1 rounded border border-border/40">
                                <span className="text-text-secondary block text-[10px]">🧹 Chất lượng mã nguồn</span>
                                <span className={`font-mono font-semibold ${b.code_quality_mod >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                                  {b.code_quality_mod >= 0 ? `+${b.code_quality_mod}` : b.code_quality_mod}đ
                                </span>
                              </div>
                            </div>

                            {b.breakdown_items && b.breakdown_items.length > 0 && (
                              <div className="space-y-1 pt-1 border-t border-border/40">
                                <p className="text-[10px] font-medium text-text-tertiary">Chi tiết cộng / trừ điểm:</p>
                                <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                                  {b.breakdown_items.map((it, idx) => (
                                    <div key={idx} className="flex items-start justify-between text-[10px] gap-2">
                                      <span className="text-text-secondary truncate">{it.label}</span>
                                      <span className={`font-mono font-medium shrink-0 ${it.val > 0 ? 'text-emerald-700' : it.val < 0 ? 'text-rose-700' : 'text-text-tertiary'}`}>
                                        {it.val > 0 ? `+${it.val}` : it.val}đ
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <p className="text-[11px] text-text-tertiary">Điểm năng lực: {item.A}%</p>
                        )}
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Radar
                name="Năng lực"
                dataKey="A"
                stroke="#2563EB"
                strokeWidth={2}
                fill="#2563EB"
                fillOpacity={0.18}
                dot={{ r: 4, fill: '#2563EB', strokeWidth: 1.5, stroke: '#FFFFFF' }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>

      {/* Bảng Giải trình Chi tiết Cộng/Trừ Điểm (Explainability Panel) */}
      {isPillars && data.breakdown && (
        <div className="border-t border-border/60 bg-card-subtle/40 rounded-b-lg">
          <button
            type="button"
            onClick={() => setShowBreakdown(!showBreakdown)}
            className="w-full flex items-center justify-between p-3 sm:px-4 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-card-subtle/70 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-primary"
          >
            <span className="flex items-center gap-2">
              <Info className="w-3.5 h-3.5 text-brand-primary" />
              <span>Xem chi tiết bảng giải trình cộng / trừ điểm (8 chuyên đề)</span>
            </span>
            <div className="flex items-center gap-1.5 text-[11px] text-text-tertiary">
              <span>{showBreakdown ? 'Thu gọn' : 'Mở rộng'}</span>
              {showBreakdown ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </div>
          </button>

          {showBreakdown && (
            <div className="p-3 sm:p-4 pt-1 space-y-3 border-t border-border/40">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-border/60 text-text-tertiary text-[11px]">
                      <th className="py-2 px-2 font-medium">Chuyên đề thuật toán</th>
                      <th className="py-2 px-2 font-medium text-center">Bài AC</th>
                      <th className="py-2 px-2 font-medium text-right">Nền tảng (0–50)</th>
                      <th className="py-2 px-2 font-medium text-right">Chính xác (±15)</th>
                      <th className="py-2 px-2 font-medium text-right">Hiệu năng (±15)</th>
                      <th className="py-2 px-2 font-medium text-right">Source code (±10)</th>
                      <th className="py-2 px-2 font-medium text-right">Tổng điểm</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono text-[11px]">
                    {PILLAR_CONFIG.map((p) => {
                      const b = data.breakdown ? data.breakdown[p.key] : null;
                      if (!b) return null;
                      const isSelected = selectedPillarKey === p.key;
                      return (
                        <React.Fragment key={p.key}>
                          <tr
                            onClick={() => setSelectedPillarKey(isSelected ? null : p.key)}
                            className={`cursor-pointer transition-colors ${
                              isSelected ? 'bg-brand-primary/5 font-semibold' : 'hover:bg-card-subtle'
                            }`}
                          >
                            <td className="py-2 px-2 font-sans font-medium text-text-primary flex items-center gap-1.5">
                              <span>{p.fullSubject}</span>
                              {isSelected ? (
                                <ChevronUp className="w-3 h-3 text-brand-primary" />
                              ) : (
                                <ChevronDown className="w-3 h-3 text-text-tertiary" />
                              )}
                            </td>
                            <td className="py-2 px-2 text-center text-text-secondary">{b.ac_count}</td>
                            <td className="py-2 px-2 text-right text-text-primary">{b.base_score}</td>
                            <td
                              className={`py-2 px-2 text-right ${
                                b.precision_mod > 0
                                  ? 'text-emerald-700'
                                  : b.precision_mod < 0
                                  ? 'text-rose-700'
                                  : 'text-text-tertiary'
                              }`}
                            >
                              {b.precision_mod > 0 ? `+${b.precision_mod}` : b.precision_mod}
                            </td>
                            <td
                              className={`py-2 px-2 text-right ${
                                b.efficiency_mod > 0
                                  ? 'text-emerald-700'
                                  : b.efficiency_mod < 0
                                  ? 'text-rose-700'
                                  : 'text-text-tertiary'
                              }`}
                            >
                              {b.efficiency_mod > 0 ? `+${b.efficiency_mod}` : b.efficiency_mod}
                            </td>
                            <td
                              className={`py-2 px-2 text-right ${
                                b.code_quality_mod > 0
                                  ? 'text-emerald-700'
                                  : b.code_quality_mod < 0
                                  ? 'text-rose-700'
                                  : 'text-text-tertiary'
                              }`}
                            >
                              {b.code_quality_mod > 0 ? `+${b.code_quality_mod}` : b.code_quality_mod}
                            </td>
                            <td className="py-2 px-2 text-right font-bold text-brand-primary font-sans">
                              {b.score}%
                            </td>
                          </tr>

                          {isSelected && (
                            <tr className="bg-card-subtle/70">
                              <td colSpan={7} className="p-3 font-sans">
                                <div className="space-y-1.5">
                                  <p className="text-[11px] font-semibold text-text-primary">
                                    Chi tiết yếu tố cộng/trừ điểm của {p.fullSubject}:
                                  </p>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                                    {b.breakdown_items.map((it, idx) => (
                                      <div
                                        key={idx}
                                        className="bg-card p-2 rounded border border-border/50 flex items-start justify-between gap-2"
                                      >
                                        <div className="min-w-0">
                                          <p className="text-xs font-medium text-text-primary truncate">{it.label}</p>
                                          {it.desc && (
                                            <p className="text-[10px] text-text-tertiary mt-0.5">{it.desc}</p>
                                          )}
                                        </div>
                                        <span
                                          className={`font-mono text-xs font-bold shrink-0 ${
                                            it.val > 0
                                              ? 'text-emerald-700'
                                              : it.val < 0
                                              ? 'text-rose-700'
                                              : 'text-text-tertiary'
                                          }`}
                                        >
                                          {it.val > 0 ? `+${it.val}đ` : `${it.val}đ`}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
