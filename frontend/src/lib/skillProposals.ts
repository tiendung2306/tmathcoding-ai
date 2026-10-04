import type { SkillDefinition, SkillDocument } from '../types';
import type { SkillProposal } from '../services/skillConfig';

export function nodeContext(nodes: SkillDefinition[]) {
  return JSON.stringify(nodes.map(({id, title, description, parent_id}) => ({id, title, description, parent_id}))
    .sort((a, b) => a.id.localeCompare(b.id)));
}

export function proposalStatus(item: SkillProposal, document: SkillDocument) {
  const assigned = document.assignments[item.tag_id];
  if (assigned) return 'assigned';
  if (item.status === 'rejected') return 'rejected';
  if (nodeContext(item.nodes) !== nodeContext(document.nodes) || !document.nodes.some(node => node.id === item.node_id)) return 'stale';
  return 'pending';
}

export function pendingProposals(items: SkillProposal[], document: SkillDocument) {
  return unresolvedProposals(items, document).filter(item => proposalStatus(item, document) === 'pending');
}

export function unresolvedProposals(items: SkillProposal[], document: SkillDocument) {
  return items.filter(item => item.status === 'pending' && !document.assignments[item.tag_id]);
}

export function mergeProposals(current: SkillProposal[], incoming: SkillProposal[], document: SkillDocument) {
  const entries = new Map(current.map(item => [item.tag_id, item]));
  for (const item of incoming) {
    const previous = entries.get(item.tag_id);
    if (previous?.status === 'rejected' && item.status === 'pending' && nodeContext(previous.nodes) === nodeContext(item.nodes)) continue;
    entries.set(item.tag_id, item);
  }
  return [...entries.values()].filter(item => !document.assignments[item.tag_id] && item.status !== 'assigned');
}
