import React from 'react';
import { AICommentaryResponseData } from '../types';
import { Lightbulb, RefreshCw, Clock, Target, AlertCircle } from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';

interface AIAdvisorCardProps {
  data: AICommentaryResponseData | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const AIAdvisorCard: React.FC<AIAdvisorCardProps> = ({
  data,
  loading,
  refreshing,
  error,
  onRefresh,
}) => {
  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  return (
    <Card className="border-border bg-card shadow-xs relative overflow-hidden">
      <CardContent className="p-4 sm:p-5">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-2.5">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-md bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary flex-shrink-0">
              <Lightbulb className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-semibold text-text-primary tracking-tight">
              Nhận xét học tập
            </h2>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={loading || refreshing}
            title="Làm mới nhận xét"
            className="h-7 px-2.5 text-[11px] text-text-secondary hover:text-text-primary border-border hover:border-border-strong flex-shrink-0"
          >
            <RefreshCw
              className={`w-3 h-3 mr-1.5 ${refreshing ? 'animate-spin text-brand-primary' : ''}`}
            />
            {refreshing ? 'Đang cập nhật...' : 'Làm mới'}
          </Button>
        </div>

        {/* Body */}
        {loading ? (
          <div className="space-y-2 py-1">
            <Skeleton className="h-3.5 w-11/12" />
            <Skeleton className="h-3.5 w-4/5" />
            <Skeleton className="h-3.5 w-3/5" />
            <p className="text-[10px] text-text-tertiary pt-1">
              Đang tổng hợp dữ liệu học tập...
            </p>
          </div>
        ) : error ? (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-md p-3 text-xs">
            <AlertCircle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-red-700">{error}</p>
              <button
                type="button"
                onClick={onRefresh}
                className="mt-1.5 text-[11px] text-brand-primary hover:underline font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded-sm"
              >
                Thử lại
              </button>
            </div>
          </div>
        ) : data ? (
          <div className="space-y-3">
            <p className="text-xs text-text-primary leading-relaxed whitespace-pre-line border-l-2 border-brand-primary/50 pl-3 py-0.5 bg-card-subtle/50 rounded-r-md">
              {data.commentary}
            </p>

            {/* Chips: active tags & recommendations */}
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              {data.recent_7days_summary.active_tags.slice(0, 4).map((tag) => (
                <Badge key={tag} variant="outline" className="text-[10px] font-sans">
                  {tag}
                </Badge>
              ))}

              {data.recent_7days_summary.active_tags.length > 4 && (
                <span className="text-[10px] text-text-tertiary">
                  +{data.recent_7days_summary.active_tags.length - 4} khác
                </span>
              )}
            </div>

            {data.recommended_tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 text-[11px] pt-0.5">
                <span className="flex items-center gap-1 text-text-secondary text-[11px] font-medium">
                  <Target className="w-3 h-3 text-brand-primary" />
                  Chủ đề gợi ý:
                </span>
                {data.recommended_tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="secondary"
                    className="text-[10px] font-sans"
                  >
                    {tag}
                  </Badge>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[10px] text-text-tertiary">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Cập nhật: {formatTime(data.generated_at)}
              </span>
              {refreshing && (
                <span className="text-text-secondary">
                  Đang xử lý nền, bạn vẫn có thể thao tác các mục khác
                </span>
              )}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
};
