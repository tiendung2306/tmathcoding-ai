export function applyLiveSubmissionEvents(previous, events, snapshot = false) {
  const byId = new Map(snapshot ? [] : previous.map(item => [item.id, item]));
  for (const event of events ?? []) {
    if (event.kind === 'deleted') byId.delete(event.submission_id);
    else if (event.record) byId.set(event.submission_id, event.record);
  }
  return [...byId.values()].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime() || b.id - a.id
  );
}

export function shouldResetLiveFeed(previousSessionId, nextSessionId) {
  return previousSessionId !== nextSessionId;
}
