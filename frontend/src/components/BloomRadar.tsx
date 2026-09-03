import React from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import { BloomRadarData } from '../types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';

interface BloomRadarProps {
  data: BloomRadarData;
}

export const BloomRadar: React.FC<BloomRadarProps> = ({ data }) => {
  const chartData = [
    { subject: 'A - Nhớ', A: data.A_Nho, fullMark: 100 },
    { subject: 'B - Hiểu', A: data.B_Hieu, fullMark: 100 },
    { subject: 'C - Vận dụng', A: data.C_VanDung, fullMark: 100 },
    { subject: 'D - Phân tích', A: data.D_PhanTich, fullMark: 100 },
    { subject: 'E - Đánh giá', A: data.E_DanhGia, fullMark: 100 },
    { subject: 'F - Đặc biệt', A: data.F_DacBiet, fullMark: 100 },
  ];

  const levels = [
    { label: 'Mức A (Nhớ)', val: data.A_Nho },
    { label: 'Mức B (Hiểu)', val: data.B_Hieu },
    { label: 'Mức C (Vận dụng)', val: data.C_VanDung },
    { label: 'Mức D (Phân tích)', val: data.D_PhanTich },
    { label: 'Mức E (Đánh giá)', val: data.E_DanhGia },
    { label: 'Mức F (Sáng tạo)', val: data.F_DacBiet },
  ];

  return (
    <Card className="h-full flex flex-col justify-between">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Phân bố năng lực Bloom</CardTitle>
      </CardHeader>

      <CardContent className="pt-2 pb-3 flex-1 flex flex-col justify-between">
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={chartData}>
              <PolarGrid stroke="#E2E8F0" />
              <PolarAngleAxis
                dataKey="subject"
                stroke="#64748B"
                tick={{ fill: '#475569', fontSize: 10, fontWeight: 500 }}
              />
              <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#CBD5E1" tick={{ fill: '#64748B', fontSize: 9 }} />
              <Radar
                name="Điểm Bloom"
                dataKey="A"
                stroke="#2563EB"
                fill="#2563EB"
                fillOpacity={0.15}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Compact Level Breakdown Strip */}
        <div className="grid grid-cols-3 gap-1.5 pt-2 border-t border-border/50 text-[11px]">
          {levels.map((lvl) => (
            <div key={lvl.label} className="bg-card-subtle rounded px-2 py-1 flex items-center justify-between">
              <span className="text-text-secondary text-[10px]">{lvl.label}</span>
              <span className="font-mono font-medium text-[11px] text-text-primary">{lvl.val}%</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
