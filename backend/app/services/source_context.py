"""Bound source excerpts without cutting literals or syntax units."""
from dataclasses import dataclass
import re
from bisect import bisect_left, bisect_right

from app.services.source_cleaner import PreparedSource, source_lines

PROMPT_POLICY_VERSION = "context-v2"


@dataclass(frozen=True)
class SourceContext:
    text: str
    is_complete: bool
    estimated_tokens: int
    warnings: tuple[str, ...]


def build_source_context(source: PreparedSource, system_prompt: str, base_prompt: str,
                         context_window: int, max_output_tokens: int) -> SourceContext:
    # UTF-8 bytes are a conservative proxy for the configured byte-level tokenizer.
    def cost(value: str) -> int:
        return len(value.encode("utf-8", errors="surrogatepass"))

    budget = max(0, context_window - max_output_tokens - 512 - cost(system_prompt + base_prompt))
    lines = source_lines(source.prompt_source)
    mapping = source.line_map
    fence = "`" * max(3, max((len(part) for part in re.findall(r"`+", source.prompt_source)), default=2) + 1)

    def render(indices: list[int]) -> str:
        # Original line numbers stay visible after comment-only lines disappear.
        body = "".join(f"L{mapping[i]}: {lines[i]}" + ("\n" if not lines[i].endswith(("\n", "\r")) else "")
                       for i in indices)
        return f"MÃ NGUỒN ({source.language_tag}; L = dòng gốc):\n{fence}\n{body}{fence}"

    all_indices = list(range(len(lines)))
    full = render(all_indices)
    if cost(full) <= budget:
        return SourceContext(full, True, cost(system_prompt + base_prompt + full), source.warnings)

    selected: set[int] = set()
    marker = "NGỮ CẢNH KHÔNG ĐẦY ĐỦ: chỉ gửi các đơn vị mã vừa giới hạn; không suy đoán phần bị thiếu.\n"
    for unit in sorted(source.units, key=lambda unit: (not unit.is_entry, unit.start_line)):
        indices = set(range(bisect_left(mapping, unit.start_line), bisect_right(mapping, unit.end_line)))
        candidate = selected | indices
        if indices and cost(marker + render(sorted(candidate))) <= budget:
            selected = candidate
    excerpt = marker + render(sorted(selected))
    warnings = source.warnings + ("Source context is incomplete; whole syntax units were omitted.",)
    if not selected or cost(excerpt) > budget:
        excerpt = ""
    return SourceContext(excerpt, False, cost(system_prompt + base_prompt + excerpt), warnings)
