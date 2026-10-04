import type { SkillDocument, SkillTag } from '../types';
import type { Suggestion } from '../services/skillConfig';
import { assignTag } from './skillConfig';

export async function classifyTags(
  document: SkillDocument,
  tags: SkillTag[],
  previous: Suggestion[],
  request: (document: SkillDocument, signal: AbortSignal) => Promise<{suggestions: Suggestion[]}>,
  signal: AbortSignal,
  progress: (suggestions: Suggestion[], total: number, waiting: boolean) => void,
) {
  const pending = tags.filter(tag => !document.assignments[tag.id]);
  const pendingIds = new Set(pending.map(tag => tag.id));
  const collected = previous.filter(item => pendingIds.has(item.tag_id));
  let working = document;
  for (const item of collected) working = assignTag(working, item.tag_id, item.node_id);
  progress([...collected], pending.length, false);
  while (collected.length < pending.length && !signal.aborted) {
    progress([...collected], pending.length, true);
    const result = await request(working, signal);
    if (signal.aborted) break;
    if (!result.suggestions.length) throw new Error('AI không trả đề xuất cho các tag còn lại.');
    for (const item of result.suggestions) {
      if (!pendingIds.has(item.tag_id) || working.assignments[item.tag_id]) throw new Error('AI trả tag trùng hoặc ngoài danh sách cần phân loại.');
      working = assignTag(working, item.tag_id, item.node_id);
      collected.push(item);
    }
    progress([...collected], pending.length, false);
  }
  return collected;
}
