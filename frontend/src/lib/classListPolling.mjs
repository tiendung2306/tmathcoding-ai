const QUERY_FIELDS = ['page', 'page_size', 'q', 'sort_by', 'sort_order', 'starred_only'];

export function isSameClassListQuery(left, right) {
  return QUERY_FIELDS.every((field) => left[field] === right[field]);
}
