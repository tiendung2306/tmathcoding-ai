import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DndContext, DragOverlay, DragEndEvent, PointerSensor, KeyboardSensor, useSensor, useSensors, useDraggable, useDroppable, pointerWithin, closestCenter } from '@dnd-kit/core';
import { GripVertical, ChevronDown, ChevronRight, FolderTree, Search, Wand2, ListChecks } from 'lucide-react';
import { SkillConfigState, SkillDefinition, SkillDocument, SkillTag } from '../types';
import { assignTag } from '../lib/skillConfig';
import { classifyTags } from '../lib/skillClassification';
import { loadSkillConfig, saveSkillConfiguration, suggestSkillTags, cancelSkillAI, rejectSkillProposals, approveSkillProposals, skillError, SkillProposal } from '../services/skillConfig';
import { queryClient } from '../lib/queryClient';
import { nodeContext, pendingProposals, unresolvedProposals, mergeProposals } from '../lib/skillProposals';
import { SkillProposalDialog } from '../components/SkillProposalDialog';


const empty: SkillDocument = {nodes: [], assignments: {}};
const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').toLowerCase();

function TagItem({tag, document, enabled, move}: {tag: SkillTag; document: SkillDocument; enabled: boolean; move: (tag: number, node: string | null) => void}) {
  const {attributes, listeners, setNodeRef, isDragging} = useDraggable({id: `tag-${tag.id}`, data: {tag}, disabled: !enabled});
  return <div ref={setNodeRef} className={`skill-tag ${isDragging ? 'skill-tag-dragging' : ''}`}>
    <button {...attributes} {...listeners} disabled={!enabled} aria-label={`Kéo ${tag.title}`} className="skill-grip"><GripVertical size={16} /></button>
    <div className="min-w-0 flex-1"><span className="block text-sm font-medium break-words">{tag.title}</span><span className="text-xs text-text-secondary">{tag.problem_count} bài</span></div>
    <select aria-label={`Chuyển ${tag.title} vào`} value={document.assignments[tag.id] || ''} onChange={event => move(tag.id, event.target.value || null)} disabled={!enabled} className="skill-move-select">
      <option value="">Chưa phân loại</option>{document.nodes.map(node => <option key={node.id} value={node.id}>{node.parent_id ? '↳ ' : ''}{node.title}</option>)}
    </select>
  </div>;
}

function DropZone({id, enabled, children}: {id: string; enabled: boolean; children: React.ReactNode}) {
  const {setNodeRef, isOver} = useDroppable({id, disabled: !enabled});
  return <div ref={setNodeRef} className={`skill-dropzone ${isOver ? 'skill-dropzone-over' : ''}`}>{children}{isOver && <div className="skill-drop-hint">Thả để chuyển vào nhóm</div>}</div>;
}

export function SkillConfiguration() {
  const [state, setState] = useState<SkillConfigState | null>(null);
  const [document, setDocument] = useState<SkillDocument>(empty);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [aiError, setAIError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [aiProgress, setAIProgress] = useState('');
  const currentDocument = useRef(document);
  const [search, setSearch] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [dragged, setDragged] = useState<SkillTag | null>(null);
  const [suggestions, setSuggestions] = useState<SkillProposal[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [proposalOpen, setProposalOpen] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const lastReview = useRef<(() => Promise<void>) | null>(null);
  const mutation = useRef(false);
  const aiController = useRef<AbortController | null>(null);
  const aiRunId = useRef<string | null>(null);
  function stopAI() {
    aiController.current?.abort();
    if (aiRunId.current) void cancelSkillAI(aiRunId.current).catch(() => setAIError('Đã dừng nhận đề xuất. Không thể xác nhận model đã dừng; hãy chờ rồi thử lại AI.'));
  }
  useEffect(() => () => {aiController.current?.abort(); if (aiRunId.current) void cancelSkillAI(aiRunId.current).catch(() => {});}, []);
  const [reduceMotion, setReduceMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {const media = window.matchMedia('(prefers-reduced-motion: reduce)'); const update = () => setReduceMotion(media.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update);}, []);
  const sensors = useSensors(useSensor(PointerSensor, {activationConstraint: {distance: 7}}), useSensor(KeyboardSensor));
  const hasRoots = document.nodes.some(node => node.id !== 'other' && node.parent_id === null);
  const enabled = hasRoots && !busy && !aiProgress;
  const unassigned = useMemo(() => (state?.tags || []).filter(tag => !document.assignments[tag.id]), [state, document]);
  const filtered = unassigned.filter(tag => normalize(tag.title + ' ' + tag.key).includes(normalize(search)));
  const context = nodeContext(document.nodes);
  const reusable = suggestions.filter(item => nodeContext(item.nodes) === context && !document.assignments[item.tag_id]);
  const remainingAI = unassigned.filter(tag => !reusable.some(item => item.tag_id === tag.id));
  const proposalItems = unresolvedProposals(suggestions, document);
  function accept(next: SkillConfigState, merge = false) {
    if (currentDocument.current.nodes.length === 0) setCollapsed(new Set(next.document.nodes.map(node => node.id)));
    currentDocument.current = next.document;
    setState(next); setDocument(next.document); setSuggestions(current => merge ? mergeProposals(current, next.proposals || [], next.document) : next.proposals || []);
    setSelected(current => new Set([...current].filter(id => !next.document.assignments[id] && next.proposals?.some(item => item.tag_id === id && item.status === 'pending'))));
  }
  async function load() {
    setLoading(true); setError(''); setMessage('');
    try {accept(await loadSkillConfig()); setReviewError(''); setAIError(''); lastReview.current = null;} catch (err) {setError(skillError(err));} finally {setLoading(false);}
  }
  useEffect(() => {void load();}, []);
  const act = async (name: string, action: () => Promise<void>) => {
    if (mutation.current || aiController.current) return;
    setAIProgress(name); setError(''); setMessage('');
    try {await action();} catch (err) {setError(skillError(err));} finally {setAIProgress('');}
  };
  async function commit(next: SkillDocument, success: string, inModal = false, onSuccess?: () => void) {
    if (!state || mutation.current || (!inModal && aiController.current) || busy) return;
    mutation.current = true; setBusy('Đang lưu thay đổi...'); setMessage('');
    if (inModal) setReviewError(''); else setError('');
    try {
      accept(await saveSkillConfiguration(state.revision, next), true);
      onSuccess?.(); setMessage(success); void queryClient.invalidateQueries();
    } catch (err) {if (inModal) setReviewError(skillError(err)); else setError(skillError(err));}
    finally {mutation.current = false; setBusy('');}
  }
  function move(tag: number, node: string | null, inModal = false) {
    if (!hasRoots || busy || mutation.current || (!inModal && aiController.current)) return;
    const action = () => commit(assignTag(document, tag, node), node ? `Đã gắn tag vào ${document.nodes.find(item => item.id === node)?.title}.` : 'Đã đưa tag về chưa phân loại; dashboard gom vào Khác.', inModal);
    if (inModal) lastReview.current = action;
    void action();
  }
  function endDrag(event: DragEndEvent) {
    setDragged(null);
    if (event.over) move(event.active.data.current?.tag.id, event.over.id === 'unassigned' ? null : String(event.over.id));
  }
  const toggle = (id: string) => setCollapsed(current => {const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next;});
  async function classifyAll() {
    setProposalOpen(true); setReviewError('');
    const controller = new AbortController();
    aiController.current = controller;
    const runId = crypto.randomUUID();
    aiRunId.current = runId;
    const previous = reusable;
    let completed = previous.length;
    setAIError('');
    try {
      await classifyTags(document, state!.tags, previous, async (doc, signal) => {
        const result = await suggestSkillTags(doc, signal, runId);
        if (!signal.aborted) setSuggestions(current => mergeProposals(current, result.proposals, currentDocument.current));
        return result;
      }, controller.signal, (items, total, waiting) => {
        completed = items.length;
        setAIProgress(`Đã xử lý ${completed}/${total} tag${waiting ? ' · AI đang phân loại tiếp...' : ''}`);
      });
      setMessage('AI đã hoàn tất. Duyệt các đề xuất trong danh sách.');
    } catch (err) {
      if (controller.signal.aborted) setMessage(`Đã dừng AI. Giữ lại ${completed} đề xuất để duyệt.`);
      else setAIError(skillError(err));
    } finally {aiController.current = null; aiRunId.current = null;}
  }
  async function approveProposals(ids: number[]) {
    if (busy || !state || mutation.current) return;
    const pending = new Set(pendingProposals(suggestions, document).map(item => item.tag_id));
    const chosen = ids.filter(id => pending.has(id));
    if (!chosen.length) return;
    lastReview.current = () => approveProposals(chosen);
    mutation.current = true; setBusy('Đang duyệt và gắn tag...'); setReviewError(''); setMessage('');
    try {
      accept(await approveSkillProposals(state.revision, document, chosen), true);
      setMessage(`Đã duyệt và gắn ${chosen.length} tag.`); void queryClient.invalidateQueries();
    } catch (err) {setReviewError(skillError(err));}
    finally {mutation.current = false; setBusy('');}
  }
  async function rejectProposals(ids: number[]) {
    if (busy || mutation.current) return;
    lastReview.current = () => rejectProposals(ids);
    mutation.current = true; setBusy('Đang lưu từ chối...'); setReviewError('');
    try {
      const result = await rejectSkillProposals(document, ids);
      setSuggestions(current => mergeProposals(current, result.proposals, currentDocument.current));
      setSelected(current => new Set([...current].filter(id => !ids.includes(id)))); setMessage(`Đã từ chối ${ids.length} đề xuất. Các tag vẫn chưa được gắn.`);
    } catch (err) {setReviewError(skillError(err));} finally {mutation.current = false; setBusy('');}
  }
  function branch(node: SkillDefinition): React.ReactNode {
    const tags = state!.tags.filter(tag => document.assignments[tag.id] === node.id);
    const closed = collapsed.has(node.id);
    return <section key={node.id} className="skill-config-root">
      <DropZone id={node.id} enabled={enabled}>
        <div className="flex items-start gap-2 p-3 sm:p-4">
          <button aria-label={`${closed ? 'Mở' : 'Thu'} ${node.title}`} aria-expanded={!closed} onClick={() => toggle(node.id)} className="skill-icon-button">{closed ? <ChevronRight size={18} /> : <ChevronDown size={18} />}</button>
          <div className="min-w-0 flex-1"><h3 className="font-medium text-base break-words">{node.title}</h3><p className="text-xs text-text-secondary mt-1 break-words">{node.description}</p></div>
          <span className="text-xs text-text-secondary whitespace-nowrap pt-2">{tags.length} tag</span>
        </div>
        {!closed && <div className="px-3 pb-3 sm:px-4 space-y-2">{tags.map(tag => <TagItem key={tag.id} tag={tag} document={document} enabled={enabled} move={move} />)}
          {tags.length === 0 && <p className="skill-empty-drop">Kéo tag vào đây hoặc chọn nhóm trong danh sách tag.</p>}
        </div>}
      </DropZone>
    </section>;
  }
  return <div className="max-w-[1440px] mx-auto p-4 sm:p-6 space-y-5">
    <nav aria-label="Quản trị" className="flex gap-2 border-b border-border pb-3"><Link to="/admin" className="skill-nav">Gắn nhãn bài toán</Link><Link to="/admin/skills" aria-current="page" className="skill-nav skill-nav-active">Cây kỹ năng</Link></nav>
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><div className="flex items-center gap-2 text-text-secondary text-xs mb-2"><FolderTree size={16} />Phân loại năng lực</div><h1 className="text-2xl font-semibold tracking-tight">Cấu hình cây kỹ năng</h1><p className="text-sm text-text-secondary mt-2">10 nhóm kỹ năng cố định và Khác. Gắn các dạng bài vào nhóm phù hợp.</p></div>
      {state && <div className="text-right text-xs text-text-secondary space-y-1"><p>{state.has_published ? 'Cấu hình đang áp dụng' : 'Chưa áp dụng cấu hình'}</p><p>Chọn nhóm hoặc kéo tag để lưu ngay.</p></div>}
    </header>
    <div className="skill-policy"><strong className="text-text-primary">Nhóm có bài mới xuất hiện trên dashboard.</strong> Nhóm không có bài trong các tag sẽ được ẩn. Học sinh chưa làm bài vẫn thấy nhóm. Tag chưa phân loại được gom vào Khác khi áp dụng.</div>
    {error && !proposalOpen && <div role="alert" className="skill-error">{error}<button className="skill-text-button ml-2" disabled={!!busy} onClick={() => void load()}>Tải lại cấu hình</button></div>}
    <p aria-live="polite" role="status" className="text-xs text-text-secondary min-h-4">{busy || aiProgress || message}</p>
    {loading ? <p role="status" className="skill-panel p-8">Đang tải cây và danh mục tag...</p> : state && <>
      <div className="skill-toolbar">
        <button className="skill-secondary" disabled={!enabled || remainingAI.length === 0} onClick={() => void act('AI đang đề xuất phân loại...', classifyAll)}><Wand2 size={16} />AI phân loại tag chưa gắn</button>
        <button className="skill-secondary" onClick={() => setProposalOpen(true)}><ListChecks size={16} />Danh sách đề xuất ({proposalItems.length})</button>
        {aiController.current && <button className="skill-secondary" onClick={stopAI}>Dừng AI</button>}
      </div>
      <DndContext sensors={sensors} collisionDetection={args => args.pointerCoordinates ? pointerWithin(args) : closestCenter(args)}
        accessibility={{screenReaderInstructions: {draggable: 'Nhấn Space để bắt đầu kéo, phím mũi tên để di chuyển, Space để thả, Escape để hủy. Có thể dùng danh sách Chuyển vào để chọn nhóm.'}, announcements: {onDragStart: ({active}) => `Đang kéo ${active.data.current?.tag.title}.`, onDragOver: ({over}) => over ? `Đích: ${over.id === 'unassigned' ? 'Chưa phân loại' : document.nodes.find(n => n.id === over.id)?.title}.` : 'Chưa có đích thả.', onDragEnd: ({over}) => over ? 'Đã chuyển tag.' : 'Đã hủy kéo.', onDragCancel: () => 'Đã hủy kéo.'}}}
        onDragStart={event => setDragged(event.active.data.current?.tag || null)} onDragCancel={() => setDragged(null)} onDragEnd={endDrag}>
        <div className="skill-workspace">
          <aside className="skill-panel skill-tag-pool"><div className="p-4 border-b border-border"><h2 className="font-semibold flex justify-between gap-2">Tag chưa phân loại <span className="text-text-secondary font-normal tabular-nums">{unassigned.length}</span></h2><div className="skill-search mt-3"><Search size={16} /><input aria-label="Tìm tag chưa phân loại" placeholder="Tìm tên dạng bài" value={search} onChange={event => setSearch(event.target.value)} /></div></div>
            <DropZone id="unassigned" enabled={enabled}><div className="skill-pool-list">{filtered.map(tag => <TagItem key={tag.id} tag={tag} document={document} enabled={enabled} move={move} />)}{filtered.length === 0 && <p className="p-6 text-sm text-text-secondary">{unassigned.length ? 'Không có tag khớp tìm kiếm.' : 'Tất cả tag đã được phân loại.'}</p>}</div></DropZone>
          </aside>
          <div className="min-w-0 space-y-4"><div className="flex flex-wrap justify-between gap-2 text-xs text-text-secondary px-1"><span>{document.nodes.filter(node => node.parent_id === null && node.id !== 'other').length} gốc · {Object.keys(document.assignments).length}/{state.tags.length} tag đã gắn</span><span>Kéo bằng tay nắm bên trái tag</span></div>{document.nodes.filter(node => node.parent_id === null).sort((a,b) => Number(a.id === 'other') - Number(b.id === 'other')).map(node => branch(node))}</div>
        </div>
        <DragOverlay dropAnimation={reduceMotion ? null : {duration: 220, easing: 'cubic-bezier(.2,.8,.2,1)'}}>{dragged && <div className="skill-drag-overlay"><GripVertical size={18} /><div><strong className="block text-sm">{dragged.title}</strong><span className="text-xs text-text-secondary">{dragged.problem_count} bài · chọn nhóm để thả</span></div></div>}</DragOverlay>
      </DndContext>
      <SkillProposalDialog open={proposalOpen} onOpenChange={setProposalOpen} items={proposalItems} tags={state.tags} document={document} selected={selected} onSelected={setSelected} busy={busy} progress={aiProgress} running={!!aiController.current} error={reviewError || aiError || error} retryLabel={reviewError ? 'Thử lại thao tác' : aiError ? 'Thử lại AI' : 'Tải lại cấu hình'} message={message} onStop={stopAI} onRetry={() => {if (reviewError && lastReview.current) void lastReview.current(); else if (aiError) void act('Đang thử lại AI...', classifyAll); else void load();}} onReload={() => void load()} onApprove={ids => void approveProposals(ids)} onReject={ids => void rejectProposals(ids)} onEdit={(id, node) => move(id, node, true)} />
    </>}
  </div>;
}
