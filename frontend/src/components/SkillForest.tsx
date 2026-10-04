import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';
import { Pager, QueryError } from './SkillForestControls';
import { SkillForestNode, TimeRange } from '../types';
import { fetchSkillProblems } from '../services/api';

const ProblemDialog = lazy(() => import('./SkillProblemDialog'));

const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').toLowerCase();

function Problems({ tagId, userId, timeRange }: {tagId: number; userId: number; timeRange: TimeRange}) {
  const [input, setInput] = useState('');
  const [q, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(1);
  const [problem, setProblem] = useState<number | null>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {if (input.trim() === q) return; const timer = window.setTimeout(() => {setQuery(input.trim()); setPage(1);}, 300); return () => window.clearTimeout(timer);}, [input, q]);
  useEffect(() => {setPage(1); setProblem(null);}, [timeRange, userId]);
  const results = useQuery({queryKey: ['skill-problems', tagId, userId, timeRange, q, status, page],
    queryFn: ({signal}) => fetchSkillProblems(tagId, userId, timeRange, status, q, page, signal)});
  const data = results.data;
  return <div className="forest-catalog">
    <div className="forest-filters"><div className="skill-search"><Search size={16} aria-hidden="true" /><input aria-label="Tìm bài theo tên hoặc mã" placeholder="Tìm tên hoặc mã bài" value={input} onChange={event => setInput(event.target.value)} /></div>
      <select className="skill-input" aria-label="Lọc trạng thái bài" value={status} onChange={event => {setStatus(event.target.value); setPage(1);}}>
        <option value="all">Tất cả bài</option><option value="ac">Có AC</option><option value="attempted">Đã thử, chưa AC</option><option value="unattempted">Chưa làm</option>
      </select></div>
    {timeRange !== 'all' && <p className="text-xs text-text-secondary">Trạng thái và lượt nộp tính trong khoảng đã chọn.</p>}
    {results.isPending && <p role="status" className="py-5 text-sm text-text-secondary">Đang tải bài toán...</p>}
    {results.isError && <QueryError retry={() => void results.refetch()} />}
    {data && <>
      {data.items.length === 0 ? <p className="py-6 text-sm text-text-secondary">Không có bài khớp bộ lọc.</p> : <ul className="forest-problems">{data.items.map(item => <li key={item.id}><button onClick={event => {opener.current = event.currentTarget; setProblem(item.id);}} className="forest-problem-row">
        <span className="forest-problem-code">{item.code}</span><span className="forest-problem-title">{item.title}</span>
        <span className={`forest-problem-status ${item.solved ? 'forest-ac' : ''}`}>{item.solved ? 'AC' : item.attempts ? 'Đã thử, chưa AC' : 'Chưa làm'}<small>{item.attempts} lượt nộp</small></span><ChevronRight size={16} aria-hidden="true" />
      </button></li>)}</ul>}
      <Pager page={data.page} pages={data.total_pages} total={data.total} onPage={setPage} />
    </>}
    <Suspense fallback={<p role="status" className="text-sm text-text-secondary">Đang mở đề bài...</p>}>{problem !== null && <ProblemDialog id={problem} userId={userId} timeRange={timeRange} onClose={() => setProblem(null)} onRestoreFocus={() => opener.current?.focus()} />}</Suspense>
  </div>;
}

export function SkillForest({ roots, userId, timeRange = 'all' }: {roots: SkillForestNode[]; userId: number; timeRange?: TimeRange}) {
  const [rootId, setRoot] = useState<string | null>(null);
  const [tagId, setTag] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const detailRef = useRef<HTMLDivElement>(null);
  const rootButtons = useRef(new Map<string, HTMLButtonElement>());
  const root = roots.find(item => item.id === rootId);
  const children = root?.children.filter(item => normalize(item.title).includes(normalize(search))) || [];
  const selectedTag = root?.children.find(item => item.id === tagId);
  function choose(id: string) {
    setRoot(id === rootId ? null : id); setTag(null); setSearch('');
    if (id !== rootId) requestAnimationFrame(() => detailRef.current?.scrollIntoView({block: 'nearest'}));
  }
  return <section className="space-y-4" aria-label="Cây kỹ năng">
    <div className="forest-heading"><h2 className="text-lg font-semibold">Cây kỹ năng</h2><span className="text-xs text-text-secondary">{timeRange === 'all' ? 'Kết quả toàn bộ lịch sử' : 'Kết quả trong khoảng đã chọn'}</span></div>
    <p className="text-sm text-text-secondary">Chọn nhóm để xem dạng bài và bài toán. Số bài AC đếm theo bài riêng biệt.</p>
    {roots.length === 0 ? <p className="skill-panel p-6 text-sm text-text-secondary">Chưa có nhóm kỹ năng chứa bài toán.</p> : <div className="forest-roots">{roots.map((item, index) => <button key={item.id} ref={element => {if (element) rootButtons.current.set(item.id, element); else rootButtons.current.delete(item.id);}} aria-expanded={rootId === item.id} aria-controls="forest-detail" className={`forest-root-choice ${rootId === item.id ? 'forest-root-selected' : ''}`} onClick={() => choose(item.id)}>
      <span className="forest-root-number" aria-hidden="true">{item.id === 'other' ? '+' : String(index + 1).padStart(2, '0')}</span>
      <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{item.id === 'other' ? 'Khác / chưa phân loại' : item.title}</span><span className="block text-xs text-text-secondary mt-1">{item.children.length} dạng · {item.problem_count} bài</span></span>
      <span className="forest-root-result"><span>{item.ac_count}</span><small>bài AC</small></span>{rootId === item.id ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
    </button>)}</div>}
    <div id="forest-detail" ref={detailRef}>
      {root && <div className="forest-detail"><header className="forest-detail-heading"><div className="min-w-0"><h3 className="text-lg font-medium">{root.id === 'other' ? 'Khác / chưa phân loại' : root.title}</h3><p className="text-sm text-text-secondary mt-1">{root.description}</p></div><button className="skill-secondary" onClick={() => {rootButtons.current.get(root.id)?.focus(); setRoot(null); setTag(null);}}>Thu gọn nhóm</button></header>
        <div className="forest-tag-search"><div className="skill-search"><Search size={16} aria-hidden="true" /><input aria-label="Tìm dạng bài trong nhóm" placeholder="Tìm dạng bài trong nhóm" value={search} onChange={event => setSearch(event.target.value)} /></div><span className="text-xs text-text-secondary">{children.length}/{root.children.length} dạng · {root.attempted_count} bài đã thử</span></div>
        <div className="forest-tags">{children.map(child => <section key={child.id} className="forest-tag"><button className="forest-tag-trigger" aria-expanded={child.id === selectedTag?.id} aria-controls={`catalog-${child.id}`} onClick={() => setTag(tagId === child.id ? null : child.id)}>
          {tagId === child.id ? <ChevronDown size={18} aria-hidden="true" /> : <ChevronRight size={18} aria-hidden="true" />}<span className="min-w-0 flex-1"><span className="block text-sm font-medium">{child.title}</span><small className="text-text-secondary">{child.problem_count} bài · {child.attempted_count} bài đã thử</small></span><span className="text-sm tabular-nums">{child.ac_count} bài AC</span>
        </button><div id={`catalog-${child.id}`}>{tagId === child.id && child.id.startsWith('topic:') && <Problems key={child.id} tagId={Number(child.id.slice(6))} userId={userId} timeRange={timeRange} />}</div></section>)}
        {children.length === 0 && <p className="p-5 text-sm text-text-secondary">Không có dạng bài khớp tìm kiếm.</p>}</div>
        <p className="forest-note">Một bài có thể thuộc nhiều tag. Tổng của nhóm chỉ đếm bài đó một lần theo phân loại hiện tại.</p>
      </div>}
    </div>
  </section>;
}
