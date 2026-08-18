import React from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import { BloomRadarData } from '../types';

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

  return (
    <div className="bg-dark-card border border-dark-border rounded-2xl p-5 shadow-xl">
      <h2 className="text-base font-semibold text-slate-200 mb-1">Thang Độ Khó Bloom Chart (A-F)</h2>
      <p className="text-xs text-slate-400 mb-4">Trực quan hóa tỷ lệ thuần thục 6 mức tư duy lập trình</p>
      
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="80%" data={chartData}>
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="subject" stroke="#9CA3AF" tick={{ fill: '#9CA3AF', fontSize: 11 }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#4B5563" />
            <Radar
              name="Mastery"
              dataKey="A"
              stroke="#3B82F6"
              fill="#3B82F6"
              fillOpacity={0.35}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
