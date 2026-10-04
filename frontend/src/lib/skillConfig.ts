import { SkillDocument } from '../types';

export function descendants(document: SkillDocument, id: string): Set<string> {
  const found = new Set([id]);
  let previous = 0;
  while (previous !== found.size) {
    previous = found.size;
    for (const node of document.nodes) if (node.parent_id && found.has(node.parent_id)) found.add(node.id);
  }
  return found;
}

export function assignTag(document: SkillDocument, tagId: number, nodeId: string | null): SkillDocument {
  const assignments = { ...document.assignments };
  if (nodeId) assignments[tagId] = nodeId; else delete assignments[tagId];
  return { ...document, assignments };
}

export function removeBranch(document: SkillDocument, id: string): SkillDocument {
  const removed = descendants(document, id);
  return { nodes: document.nodes.filter(node => !removed.has(node.id)),
    assignments: Object.fromEntries(Object.entries(document.assignments).filter(([, node]) => !removed.has(node))) };
}
