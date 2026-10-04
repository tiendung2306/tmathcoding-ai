import { useEffect, useRef } from 'react';
import { Check, X, ChevronRight, MoreHorizontal } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import type { SkillDocument, SkillTag } from '../types';
import type { SkillProposal } from '../services/skillConfig';
import { pendingProposals, proposalStatus } from '../lib/skillProposals';

interface Props {
  open: boolean; onOpenChange: (open: boolean) => void;
  items: SkillProposal[]; tags: SkillTag[]; document: SkillDocument;
  selected: Set<number>; onSelected: (ids: Set<number>) => void;
  busy: string; progress: string; running: boolean; error: string; message: string;
  retryLabel: string;
  onStop: () => void; onRetry: () => void;
  onReload: () => void;
  onApprove: (ids: number[]) => void; onReject: (ids: number[]) => void;
  onEdit: (id: number, node: string) => void;
}

function ProposalActions({item, tagTitle, document, locked, eligible, onApprove, onReject, onEdit, onReturnFocus}: {
  item: SkillProposal; tagTitle: string; document: SkillDocument; locked: boolean; eligible: boolean;
  onApprove: Props['onApprove']; onReject: Props['onReject']; onEdit: Props['onEdit'];
  onReturnFocus: () => void;
}) {
  const acted = useRef(false);
  const perform = (action: () => void) => {acted.current = true; action();};
  const groupTitle = (id: string): string => {
    const node = document.nodes.find(entry => entry.id === id);
    return node ? node.parent_id ? `${groupTitle(node.parent_id)} / ${node.title}` : node.title : '';
  };
  return <DropdownMenu.Root modal={false}>
    <DropdownMenu.Trigger asChild><button className="skill-row-actions" disabled={locked} aria-label={`Hành động cho ${tagTitle}`}><MoreHorizontal size={18} /><span>Hành động</span></button></DropdownMenu.Trigger>
    <DropdownMenu.Portal><DropdownMenu.Content className="skill-action-menu" align="end" sideOffset={4} collisionPadding={12} onCloseAutoFocus={event => {if (acted.current) {event.preventDefault(); acted.current = false; onReturnFocus();}}}>
      <DropdownMenu.Item className="skill-action-item" disabled={!eligible} onSelect={() => perform(() => onApprove([item.tag_id]))}><Check size={16} />Duyệt</DropdownMenu.Item>
      <DropdownMenu.Item className="skill-action-item" disabled={!eligible} onSelect={() => perform(() => onReject([item.tag_id]))}><X size={16} />Từ chối</DropdownMenu.Item>
      <DropdownMenu.Separator className="skill-action-separator" />
      <DropdownMenu.Sub>
        <DropdownMenu.SubTrigger className="skill-action-item" disabled={!document.nodes.some(node => node.id !== 'other' && node.parent_id === null)}><span>Chọn nhóm</span><ChevronRight size={16} className="ml-auto" /></DropdownMenu.SubTrigger>
        <DropdownMenu.Portal><DropdownMenu.SubContent className="skill-action-menu skill-group-menu" sideOffset={4} collisionPadding={12}>
          <DropdownMenu.Label className="skill-group-hint">Chọn để gắn và lưu ngay</DropdownMenu.Label>
          {document.nodes.map(node => <DropdownMenu.Item key={node.id} className="skill-action-item" onSelect={() => perform(() => onEdit(item.tag_id, node.id))}><span>{groupTitle(node.id)}</span></DropdownMenu.Item>)}
        </DropdownMenu.SubContent></DropdownMenu.Portal>
      </DropdownMenu.Sub>
    </DropdownMenu.Content></DropdownMenu.Portal>
  </DropdownMenu.Root>;
}

export function SkillProposalDialog(props: Props) {
  const {items, document, selected, busy, running} = props;
  const pending = pendingProposals(items, document);
  const pendingIds = pending.map(item => item.tag_id);
  const chosen = pendingIds.filter(id => selected.has(id));
  const selectAll = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {if (selectAll.current) selectAll.current.indeterminate = chosen.length > 0 && chosen.length < pending.length;}, [chosen.length, pending.length, props.open]);
  const staleCount = items.filter(item => proposalStatus(item, document) === 'stale').length;
  const locked = !!busy;
  return <Dialog open={props.open} onOpenChange={props.onOpenChange}><DialogContent className="skill-proposal-modal">
    <div className="skill-proposal-heading"><DialogTitle>Danh sách đề xuất</DialogTitle><DialogDescription>Duyệt để dùng đề xuất AI, hoặc chọn nhóm để gắn ngay. Tag đã gắn sẽ rời danh sách.</DialogDescription>
      <p className="text-sm text-text-secondary mt-3">{pending.length} đề xuất chờ duyệt{staleCount > 0 ? ` · ${staleCount} cần phân loại lại` : ''}</p>
    </div>
    {(busy || props.progress || props.message) && <div className="skill-proposal-status"><p role="status" aria-live="polite" className="text-sm">{busy || props.progress || props.message}</p>
      {running && <button className="skill-secondary shrink-0" onClick={props.onStop}>Dừng AI</button>}
    </div>}
    {props.error && <div role="alert" className="skill-error">{props.error}<button disabled={locked} className="skill-text-button ml-2" onClick={props.onRetry}>{props.retryLabel}</button><button disabled={locked} className="skill-text-button ml-2" onClick={props.onReload}>Tải lại cấu hình</button></div>}
    <div className="skill-proposal-actions">
      <span className="text-xs text-text-secondary">Đã chọn {chosen.length}/{pending.length} chờ duyệt</span>
      <div className="skill-proposal-buttons">
        <button className="skill-primary" disabled={locked || chosen.length === 0} onClick={() => props.onApprove(chosen)}><Check size={16} />Duyệt đã chọn ({chosen.length})</button>
        <button className="skill-secondary" disabled={locked || pending.length === 0} onClick={() => props.onApprove(pendingIds)}>Duyệt tất cả ({pending.length})</button>
        <button className="skill-secondary" disabled={locked || chosen.length === 0} onClick={() => props.onReject(chosen)}><X size={16} />Từ chối đã chọn ({chosen.length})</button>
        <button className="skill-secondary" disabled={locked || pending.length === 0} onClick={() => props.onReject(pendingIds)}>Từ chối tất cả ({pending.length})</button>
      </div>
      {running && <p className="text-xs text-text-secondary">Bạn có thể duyệt, đổi nhóm hoặc từ chối ngay trong lúc AI phân loại tiếp.</p>}
    </div>
    <div ref={list} tabIndex={-1} role="region" aria-label="Các đề xuất phân loại tag" className="skill-proposal-list">
      {items.length === 0 ? <p className="skill-proposal-empty">{running ? 'Đang chờ nhóm đề xuất đầu tiên từ AI...' : 'Chưa có đề xuất. Tạo nút gốc rồi chạy AI phân loại tag chưa gắn.'}</p> : <table className="skill-proposal-table">
        <thead><tr><th className="skill-proposal-check"><label className="skill-check-target"><input ref={selectAll} type="checkbox" aria-label="Chọn tất cả đề xuất chờ duyệt" disabled={locked || pending.length === 0} checked={pending.length > 0 && chosen.length === pending.length} onChange={event => props.onSelected(event.target.checked ? new Set(pendingIds) : new Set())} /></label></th><th>Tag</th><th>Nhóm AI đề xuất</th><th>Lý do AI</th><th className="skill-actions-heading">Hành động</th></tr></thead>
        <tbody>{items.map(item => {
          const status = proposalStatus(item, document);
          const editable = status === 'pending';
          const tagTitle = props.tags.find(tag => tag.id === item.tag_id)?.title || `Tag #${item.tag_id}`;
          const proposedNode = document.nodes.find(node => node.id === item.node_id) || item.nodes.find(node => node.id === item.node_id);
          return <tr key={item.tag_id} data-status={status}>
            <td className="skill-proposal-check"><label className="skill-check-target"><input type="checkbox" aria-label={`Chọn ${tagTitle}`} disabled={locked || !editable} checked={editable && selected.has(item.tag_id)} onChange={event => {const next = new Set(selected); if (event.target.checked) next.add(item.tag_id); else next.delete(item.tag_id); props.onSelected(next);}} /></label></td>
            <td className="skill-proposal-tag"><strong>{tagTitle}</strong></td>
            <td className="skill-proposal-destination"><span className="skill-mobile-label">Nhóm AI đề xuất</span><span className="skill-proposal-result">{proposedNode?.title || 'Nhóm đã xóa'}</span>{status === 'stale' && <p className="skill-proposal-stale">Phạm vi nhóm đã thay đổi. Chạy AI lại hoặc chọn nhóm trong Hành động.</p>}</td>
            <td className="skill-proposal-reason"><span className="skill-mobile-label">Lý do AI</span>{item.reason}</td>
            <td className="skill-proposal-row-actions"><ProposalActions item={item} tagTitle={tagTitle} document={document} locked={locked || !props.tags.some(tag => tag.id === item.tag_id)} eligible={editable} onApprove={props.onApprove} onReject={props.onReject} onEdit={props.onEdit} onReturnFocus={() => list.current?.focus()} /></td>
          </tr>;
        })}</tbody>
      </table>}
    </div>
    <div className="skill-proposal-footer"><span className="text-xs text-text-secondary">Duyệt, gắn hoặc từ chối xong, đề xuất sẽ rời danh sách.</span><button className="skill-secondary" onClick={() => props.onOpenChange(false)}>Đóng danh sách</button></div>
  </DialogContent></Dialog>;
}
