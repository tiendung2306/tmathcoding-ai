import React, { useMemo, useState } from 'react';
import { TagMetricItemData, TagStatus, TagWeight } from '../types';
import { Search, FileSearch, AlertTriangle, ListFilter } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';

type TagFilter = 'all' | 'strong' | 'weak' | 'unattempted';

interface TagCompletionGridProps {
  tags: TagMetricItemData[];
}

const FILTERS: { key: TagFilter; label: string }[] = [
  { key: 'all', label: 'Tất cả' },
  { key: 'strong', label: 'Điểm mạnh' },
  { key: 'weak', label: 'Cần luyện' },
  { key: 'unattempted', label: 'Chưa làm' },
];

const WEIGHT_LABEL: Record<TagWeight, string> = {
  small: 'Nhỏ',
  medium: 'Vừa',
  large: 'Lớn',
};

const STATUS_LABEL: Record<TagStatus, string> = {
  MASTERED: 'Điểm mạnh',
  PRACTICING: 'Đang luyện',
  NEEDS_IMPROVEMENT: 'Cần luyện',
  UNATTEMPTED: 'Chưa làm',
};

// Bỏ dấu tiếng Việt để tìm kiếm "quy hoach" vẫn khớp "Quy hoạch"
const normalize = (s: string) =>
  s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();

const statusStyles: Record<TagStatus, { bar: string; badge: string; frame: string }> = {
  MASTERED: {
    bar: 'bg-emerald-600',
    badge: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    frame: 'border-emerald-200 bg-emerald-50/50',
  },
  PRACTICING: {
    bar: 'bg-blue-600',
    badge: 'text-blue-700 bg-blue-50 border-blue-200',
    frame: 'border-blue-200 bg-blue-50/40',
  },
  NEEDS_IMPROVEMENT: {
    bar: 'bg-red-600',
    badge: 'text-red-700 bg-red-50 border-red-200',
    frame: 'border-red-200 bg-red-50/50',
  },
  UNATTEMPTED: {
    bar: 'bg-slate-300',
    badge: 'text-text-secondary bg-card-subtle border-border',
    frame: 'border-border/60 bg-card-subtle/30 opacity-70 hover:opacity-100',
  },
};

export const TagCompletionGrid: React.FC<TagCompletionGridProps> = ({ tags }) => {
  const [filter, setFilter] = useState<TagFilter>('all');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = normalize(query.trim());
    return tags.filter((t) => {
      let passFilter: boolean;
      if (filter === 'all') {
        // Ẩn các tag rỗng (không có bài & không có lượt nộp) ở chế độ Tất cả
        passFilter = !(t.total_problems === 0 && t.submissions_stat.total_submissions === 0);
      } else if (filter === 'strong') {
        passFilter = t.status === 'MASTERED';
      } else if (filter === 'weak') {
        passFilter = t.status === 'NEEDS_IMPROVEMENT';
      } else {
        passFilter = t.status === 'UNATTEMPTED';
      }
      if (!passFilter) return false;
      if (!q) return true;
      return normalize(t.name).includes(q) || normalize(t.key).includes(q);
    });
  }, [tags, filter, query]);

  const getVerdictBadge = (label: string, rate: number, variant: 'ac' | 'wa' | 'tle') => (
    <Badge variant={variant} className="text-[10px] py-0 px-1.5 font-mono">
      {label} {Math.round(rate)}%
    </Badge>
  );

  return (
    <Card>
      <CardHeader className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3">
        <div>
          <CardTitle className="text-sm flex items-center gap-2">
            <ListFilter className="w-4 h-4 text-brand-primary" />
            Tiến độ theo dạng bài
          </CardTitle>
          <CardDescription className="text-xs">
            Hiển thị {filtered.length}/{tags.length} dạng bài
          </CardDescription>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          {/* Filters */}
          <div className="flex items-center gap-1 bg-card-subtle p-1 rounded-md border border-border overflow-x-auto max-w-full">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary ${
                  filter === f.key
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative w-full sm:w-48">
            <Input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm dạng bài..."
              className="pl-8 h-8 text-xs bg-card-subtle"
            />
            <Search className="w-3.5 h-3.5 text-text-tertiary absolute left-2.5 top-2.5" />
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0 pb-4">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-text-tertiary">
            <FileSearch className="w-8 h-8 mb-2 stroke-1 text-text-disabled" />
            <p className="text-xs text-text-secondary">Không có dạng bài nào khớp bộ lọc hoặc từ khóa tìm kiếm.</p>
            {(query || filter !== 'all') && (
              <button
                type="button"
                onClick={() => { setFilter('all'); setQuery(''); }}
                className="mt-2.5 text-xs text-brand-primary hover:underline font-medium"
              >
                Đặt lại bộ lọc
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 max-h-[560px] overflow-y-auto pr-1">
            {filtered.map((tag) => (
              <TagCard key={tag.tag_id} tag={tag} getVerdictBadge={getVerdictBadge} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

interface TagCardProps {
  tag: TagMetricItemData;
  getVerdictBadge: (label: string, rate: number, variant: 'ac' | 'wa' | 'tle') => JSX.Element;
}

const TagCard: React.FC<TagCardProps> = ({ tag, getVerdictBadge }) => {
  const st = tag.submissions_stat;
  const style = statusStyles[tag.status];
  const hasHighError = st.wa_rate > 50 || st.tle_rate > 50;

  return (
    <div
      className={`border rounded-md p-3.5 transition-colors ${style.frame} ${
        hasHighError ? 'ring-1 ring-red-500' : ''
      }`}
    >
      {/* Title row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <h4 className="text-xs font-medium text-text-primary truncate" title={tag.name}>
            {tag.name} <span className="text-text-tertiary font-normal">({tag.total_problems} bài)</span>
          </h4>
          <span className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider block truncate">
            {tag.key}
          </span>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className={`text-[10px] px-1.5 py-0.2 rounded-sm border font-medium ${style.badge}`}>
            {STATUS_LABEL[tag.status]}
          </span>
          <span className="text-[10px] text-text-tertiary">Quy mô {WEIGHT_LABEL[tag.tag_weight]}</span>
        </div>
      </div>

      {/* Completion progress bar */}
      <div className="w-full bg-card h-1.5 rounded-full overflow-hidden mb-1 border border-border/40">
        <div
          className={`h-full rounded-full transition-all duration-300 ${style.bar}`}
          style={{ width: `${Math.min(100, tag.completion_rate)}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-text-secondary mb-2">
        <span>Tỷ lệ hoàn thành</span>
        <span className="font-mono">
          {tag.ac_problems}/{tag.total_problems} • {tag.completion_rate}%
        </span>
      </div>

      {/* Verdict distribution badges (7 days) */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] text-text-tertiary">Nộp {st.total_submissions} lần:</span>
        {getVerdictBadge('AC', st.ac_rate, 'ac')}
        {getVerdictBadge('WA', st.wa_rate, 'wa')}
        {getVerdictBadge('TLE', st.tle_rate, 'tle')}
      </div>

      {/* Cảnh báo đỏ khi WA/TLE > 50% */}
      {hasHighError && (
        <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-medium text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate">
            {st.primary_error
              ? `Lỗi: ${st.primary_error} > 50% lượt nộp`
              : 'Tỷ lệ lỗi > 50%'}
          </span>
        </div>
      )}
    </div>
  );
};
