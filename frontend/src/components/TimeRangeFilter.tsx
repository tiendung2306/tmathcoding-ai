import React from 'react';
import { TimeRange } from '../types';
import { Calendar } from 'lucide-react';

interface TimeRangeFilterProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
  disabled?: boolean;
  className?: string;
}

const OPTIONS: { key: TimeRange; label: string; tooltip: string }[] = [
  { key: '1d', label: '1 ngày qua', tooltip: 'Đánh giá hoạt động trong 1 ngày gần nhất' },
  { key: '7d', label: '1 tuần qua', tooltip: 'Đánh giá hoạt động trong 7 ngày gần nhất' },
  { key: '30d', label: '1 tháng qua', tooltip: 'Đánh giá hoạt động trong 30 ngày gần nhất' },
  { key: '1y', label: '1 năm qua', tooltip: 'Đánh giá hoạt động trong 1 năm qua' },
  { key: 'all', label: 'Cả quá trình', tooltip: 'Toàn bộ dữ liệu tích lũy từ trước tới nay' },
];

export const TimeRangeFilter: React.FC<TimeRangeFilterProps> = ({
  value,
  onChange,
  disabled = false,
  className = '',
}) => {
  return (
    <div className={`inline-flex items-center gap-1.5 p-1 bg-card-subtle/80 border border-border/80 rounded-lg ${className}`}>
      <div className="flex items-center gap-1 pl-1.5 pr-1 text-text-tertiary">
        <Calendar className="w-3.5 h-3.5" />
        <span className="text-[11px] font-medium hidden sm:inline">Mốc:</span>
      </div>
      <div className="flex items-center gap-1" role="group" aria-label="Chọn mốc thời gian đánh giá">
        {OPTIONS.map((opt) => {
          const isActive = value === opt.key;
          return (
            <button
              key={opt.key}
              type="button"
              disabled={disabled}
              onClick={() => onChange(opt.key)}
              title={opt.tooltip}
              aria-pressed={isActive}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary ${
                isActive
                  ? 'bg-card text-brand-primary shadow-xs font-semibold border border-border/80'
                  : 'text-text-secondary hover:text-text-primary hover:bg-card/50 border border-transparent'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
