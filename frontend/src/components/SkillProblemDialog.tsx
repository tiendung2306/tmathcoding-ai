import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { TimeRange } from '../types';
import { fetchSkillProblemDetail } from '../services/api';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog';
import { SubmissionDetailModal } from './SubmissionDetailModal';
import { Pager, QueryError } from './SkillForestControls';
export default function ProblemDialog({ id, userId, timeRange, onClose, onRestoreFocus }: {id: number | null; userId: number; timeRange: TimeRange; onClose: () => void; onRestoreFocus: () => void}) {
  const [page, setPage] = useState(1);
  const [submission, setSubmission] = useState<number | null>(null);
  useEffect(() => {setPage(1); setSubmission(null);}, [id, userId, timeRange]);
  const detail = useQuery({queryKey: ['skill-problem', id, userId, timeRange, page], enabled: id !== null,
    queryFn: ({signal}) => fetchSkillProblemDetail(id!, userId, timeRange, page, signal)});
  const data = detail.data;
  return <>
    <Dialog open={id !== null} onOpenChange={open => {if (!open) onClose();}}><DialogContent className="forest-problem-modal" onCloseAutoFocus={event => {event.preventDefault(); onRestoreFocus();}}>
      <DialogTitle className="pr-8 leading-normal">{data ? `${data.code} · ${data.title}` : 'Bài toán'}</DialogTitle>
      <DialogDescription>Đề bài và các lượt nộp của học sinh{timeRange === 'all' ? '.' : ' trong khoảng đã chọn.'}</DialogDescription>
      {detail.isPending && <p role="status">Đang tải đề bài...</p>}
      {detail.isError && <QueryError retry={() => void detail.refetch()} />}
      {data && <>
        <div className="flex flex-wrap gap-4 text-xs text-text-secondary"><span>Thời gian: {data.time_limit} giây</span><span>Bộ nhớ: {data.memory_limit} KB</span></div>
        <article className="forest-statement" aria-label="Đề bài">{data.description ? <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, {trust: false}]]} components={{a: props => <a {...props} target="_blank" rel="noopener noreferrer" />}}>{data.description}</ReactMarkdown> : <p>Kho bài chưa có nội dung đề.</p>}</article>
        <section className="space-y-3 border-t border-border pt-4"><h3 className="font-medium">Lịch sử nộp{timeRange !== 'all' && ' trong khoảng đã chọn'}</h3>
          {data.submissions.items.length === 0 ? <p className="text-sm text-text-secondary">Không có lượt nộp{timeRange !== 'all' && ' trong khoảng này'}.</p> : <ul className="forest-submissions">{data.submissions.items.map(item => <li key={item.id}>
            <button onClick={() => setSubmission(item.id)} className="forest-submission-link"><span>#{item.id} · {new Date(item.date + (item.date.endsWith('Z') ? '' : 'Z')).toLocaleString('vi-VN')}</span><span className={item.result === 'AC' ? 'forest-ac' : ''}>{item.result} · {item.points ?? 0} điểm</span></button>
          </li>)}</ul>}
          <Pager page={data.submissions.page} pages={data.submissions.total_pages} total={data.submissions.total} onPage={setPage} />
        </section>
      </>}
    </DialogContent></Dialog>
    <SubmissionDetailModal submissionId={submission} isOpen={submission !== null} onClose={() => setSubmission(null)} initialTab="code" />
  </>;
}
