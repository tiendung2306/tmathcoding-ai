import React from 'react';
import { AICommentaryResponseData } from '../types';
import { Lightbulb, RefreshCw, Clock, Target, AlertCircle } from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';

interface AIAdvisorCardProps {
  data: AICommentaryResponseData | null;
  loading: boolean;
  generating: boolean;
  error: string | null;
  onGenerate: () => void;
}

export const AIAdvisorCard: React.FC<AIAdvisorCardProps> = ({ data, loading, generating, error, onGenerate }) => {
  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
    } catch {
      return iso;
    }
  };

  return <section className="min-w-0" aria-labelledby="ai-advisor-title">
    <div className="mb-2 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 text-text-primary">
        <Lightbulb aria-hidden className="h-4 w-4 text-brand-primary" />
        <h2 id="ai-advisor-title" className="text-sm font-semibold">Nhận xét học tập</h2>
      </div>
      <Button variant="outline" size="sm" onClick={onGenerate} disabled={loading || generating} title={data ? 'Tạo lại nhận xét' : 'Tạo nhận xét'} className="h-8 px-2.5 text-xs flex-shrink-0">
        <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${generating ? 'animate-spin' : ''}`} />
        {generating ? 'Đang tạo...' : data ? 'Tạo lại' : 'Tạo nhận xét'}
      </Button>
    </div>

    {loading ? <div className="space-y-2" aria-busy="true">
      <Skeleton className="h-3.5 w-11/12" />
      <Skeleton className="h-3.5 w-4/5" />
    </div> : error ? <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-2.5 text-xs">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
      <div><p className="text-red-700">{error}</p><button type="button" onClick={onGenerate} className="mt-1 text-brand-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary">Thử lại</button></div>
    </div> : data ? <div className="space-y-2">
      <p className="text-sm leading-relaxed text-text-primary whitespace-pre-line">{data.commentary}</p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-secondary">
        {data.recommended_tags.length > 0 && <span className="inline-flex items-center gap-1"><Target aria-hidden className="h-3.5 w-3.5 text-brand-primary" />Gợi ý: {data.recommended_tags.slice(0, 2).map((tag, index) => <React.Fragment key={tag}>{index > 0 && ', '}<Badge variant="outline" className="px-1.5 py-0 text-[11px] font-normal">{tag}</Badge></React.Fragment>)}</span>}
        <span className="inline-flex items-center gap-1"><Clock aria-hidden className="h-3.5 w-3.5" />{formatTime(data.generated_at)}</span>
      </div>
    </div> : <p className="text-sm text-text-secondary">Chưa có nhận xét cho khoảng thời gian này.</p>}
  </section>;
};
