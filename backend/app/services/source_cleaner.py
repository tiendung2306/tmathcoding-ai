"""Conservative source comment masking and prompt-oriented line compaction."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from bisect import bisect_right
from dataclasses import dataclass
from typing import Iterable

SOURCE_POLICY_VERSION = "clean-v2"
MAX_PARSE_BYTES = 1024 * 1024


def source_lines(source: str) -> list[str]:
    # Unicode separators inside a literal are not source-code line endings.
    parts = source.split("\n")
    return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


@dataclass(frozen=True)
class SourceUnit:
    start_line: int
    end_line: int
    is_entry: bool = False


@dataclass(frozen=True)
class PreparedSource:
    analysis_source: str
    prompt_source: str
    line_map: tuple[int, ...]
    language_tag: str
    warnings: tuple[str, ...]
    removed_comment_count: int
    original_bytes: int
    removed_comment_bytes: int
    policy_version: str
    units: tuple[SourceUnit, ...]


def prepare_source(source: str, language_key: str) -> PreparedSource:
    """Prepare source without changing executable text or source line positions.

    Unsupported or uncertain inputs are passed through. ``analysis_source`` is
    always character-for-character aligned with the input, including newlines.
    """
    if not isinstance(source, str):
        source = str(source)
    key = (language_key or "").strip().lower().replace("_", "-")
    adapter, tag = _language_adapter(key)
    original_bytes = len(source.encode("utf-8", errors="surrogatepass"))
    full_unit = _all_file_unit(source)
    warnings: list[str] = []
    if adapter is None:
        if key:
            warnings.append(f"No vetted comment adapter for language {language_key!r}; source passed through.")
        return _result(source, source, (), (), tag, warnings, original_bytes, 0, (full_unit,))
    if original_bytes > MAX_PARSE_BYTES:
        warnings.append("Source exceeds the 1 MiB parse limit; source passed through without parsing.")
        return _result(source, source, (), (), tag, warnings, original_bytes, 0, (full_unit,))

    try:
        if adapter in ("c", "cpp"):
            spans, protected, units, adapter_warnings = _tree_sitter_spans(source, adapter)
            warnings.extend(adapter_warnings)
        elif adapter == "python3":
            spans, protected, units = _python3_spans(source)
        else:
            spans, protected, units = _pygments_spans(source, adapter)
    except Exception as exc:  # Adapter failures must never make submission handling fail.
        warnings.append(f"Comment parsing failed ({type(exc).__name__}); source passed through.")
        return _result(source, source, (), (), tag, warnings, original_bytes, 0, (full_unit,))

    if spans is None:
        warnings.append("Source could not be parsed with confidence; source passed through.")
        return _result(source, source, (), (), tag, warnings, original_bytes, 0, (full_unit,))

    analysis = _mask_spans(source, spans)
    prompt, line_map = _compact_prompt(analysis, protected, spans)
    removed_bytes = sum(len(source[a:b].encode("utf-8", errors="surrogatepass")) for a, b in spans)
    return _result(analysis, prompt, line_map, spans, tag, warnings, original_bytes, removed_bytes, units or (full_unit,))


def _language_adapter(key: str) -> tuple[str | None, str]:
    if key in {"c", "c89", "c99", "c11", "c17", "c23", "gnu-c", "gcc"}:
        return "c", "C"
    if key in {"cpp", "cpp03", "cpp11", "cpp14", "cpp17", "cpp20", "cpp23", "c++", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23", "gnu-c++", "g++"}:
        return "cpp", "C++"
    if key in {"python3", "python-3", "py3", "pypy3", "python"}:
        return "python3", "Python 3"
    if key in {"python2", "python-2", "py2"}:
        return "python2", "Python 2"
    if key in {"pascal", "fpc", "free-pascal"}:
        return "pascal", "Pascal"
    return None, language_key_tag(key)


def language_key_tag(key: str) -> str:
    return key.upper() if key else "Unknown"


def _tree_sitter_spans(source: str, grammar: str):
    from tree_sitter import Language, Parser
    if grammar == "c":
        import tree_sitter_c as language_module
    else:
        import tree_sitter_cpp as language_module

    language = Language(language_module.language())
    parser = Parser(language)
    data = source.encode("utf-8", errors="surrogatepass")
    tree = parser.parse(data)
    root = tree.root_node
    line_starts = _byte_line_starts(data)
    for node in _walk(root):
        if node.type == "ERROR":
            fragment = data[node.start_byte:node.end_byte]
            if b'"' in fragment or b"'" in fragment:
                return None, (), (), ()
    macro_nodes = []
    for node in _walk(root):
        if node.type in {"preproc_def", "preproc_function_def"}:
            macro_nodes.append((node.start_byte, node.end_byte))

    # C translation-phase line splicing changes comment boundaries. Keep the
    # whole file if a splice is outside a confidently recognized macro.
    for match in re.finditer(rb"\\(?:\r\n|\n|\r)", data):
        if not any(a <= match.start() < b for a, b in macro_nodes):
            return None, (), (), ()

    spans: list[tuple[int, int]] = []
    literal_nodes = [
        (node.start_byte, node.end_byte)
        for node in _walk(root)
        if node.type in {"string_literal", "char_literal", "raw_string_literal", "concatenated_string"}
    ]
    protected_bytes = list(macro_nodes) + literal_nodes
    malformed_comment = False
    for node in _walk(root):
        if node.type == "comment":
            if any(a <= node.start_byte and node.end_byte <= b for a, b in macro_nodes):
                continue
            if any(a <= node.start_byte and node.end_byte <= b for a, b in literal_nodes):
                continue
            raw_comment = data[node.start_byte:node.end_byte]
            if raw_comment.startswith(b"/*") and not raw_comment.endswith(b"*/"):
                malformed_comment = True
                continue
            spans.append((node.start_byte, node.end_byte))

    if malformed_comment:
        return None, (), (), ()

    # Byte offsets are converted at boundaries; UTF-8 spans never split a code point.
    boundaries = _byte_char_boundaries(data, [point for span in spans + protected_bytes for point in span])
    char_spans = [(boundaries[a], boundaries[b]) for a, b in spans]
    protected = tuple((boundaries[a], boundaries[b]) for a, b in protected_bytes)
    units = _c_units(root, line_starts, data) if not root.has_error else ()
    parse_warnings = ("Parser reported syntax errors; recognized comments were masked and top-level units omitted.",) if root.has_error else ()
    return char_spans, protected, units, parse_warnings


def _python3_spans(source: str):
    try:
        tree = ast.parse(source)
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        offsets = _char_line_starts(source)
        spans = []
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            value = token.string
            # Keep interpreter and source-encoding declarations intact.
            if token.start[0] == 1 and value.startswith("#!"):
                continue
            if token.start[0] <= 2 and re.match(r"^[ \t]*#.*?coding[:=][ \t]*[-\w.]+", value):
                continue
            spans.append((_token_offset(offsets, token.start), _token_offset(offsets, token.end)))
    except (SyntaxError, tokenize.TokenError, IndentationError, UnicodeDecodeError):
        return None, (), ()
    protected = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant,)) and isinstance(node.value, (str, bytes)):
            if hasattr(node, "end_lineno") and node.end_lineno:
                protected.append((offsets[node.lineno - 1], _line_end_offset(source, offsets, node.end_lineno)))
    units = []
    for node in tree.body:
        start = getattr(node, "lineno", 1)
        decorators = getattr(node, "decorator_list", ())
        if decorators:
            start = min(start, *(decorator.lineno for decorator in decorators))
        end = getattr(node, "end_lineno", start)
        is_entry = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
        units.append(SourceUnit(start, end, is_entry))
    return spans, tuple(protected), tuple(units)


def _pygments_spans(source: str, language: str):
    from pygments.lexers import DelphiLexer, Python2Lexer
    from pygments.token import Comment, Error, String

    lexer = Python2Lexer() if language == "python2" else DelphiLexer()
    spans = []
    offset = 0
    protected = []
    for start, token_type, value in lexer.get_tokens_unprocessed(source):
        if start != offset:
            return None, (), ()
        end = start + len(value)
        if token_type in Error:
            return None, (), ()
        if token_type in String:
            protected.append((start, end))
        if token_type in (Comment.Single, Comment.Multiline):
            trimmed = value.lstrip()
            if language == "pascal" and ((trimmed.startswith("{") and not trimmed.endswith("}")) or (trimmed.startswith("(*") and not trimmed.endswith("*)"))):
                return None, (), ()
            first_line_end = source.find("\n") + 1 if "\n" in source else len(source)
            if language == "pascal" and (trimmed.startswith("{$") or trimmed.startswith("(*$")):
                protected.append((offset, end))
            elif language == "python2" and start == 0 and value.startswith("#!"):
                protected.append((start, end))
            elif language == "python2" and start <= first_line_end and re.match(r"^[ \t]*#.*?coding[:=][ \t]*[-\w.]+", value):
                protected.append((start, end))
            else:
                spans.append((offset, end))
        elif token_type in (Comment.Preproc, Comment.PreprocFile):
            protected.append((offset, end))
        offset = end
    # Pygments is a lexer, so only accept exact token coverage.
    if offset != len(source):
        return None, (), ()
    units = (_all_file_unit(source),)
    return spans, tuple(protected), units


def _c_units(root, line_starts: list[int], data: bytes) -> tuple[SourceUnit, ...]:
    units = []
    for node in root.named_children:
        if node.type == "comment":
            continue
        start = bisect_right(line_starts, node.start_byte)
        end = bisect_right(line_starts, max(node.start_byte, node.end_byte - 1))
        is_entry = False
        for child in _walk(node):
            if child.type == "function_declarator":
                name = next((x for x in child.named_children if x.type == "identifier"), None)
                if name is not None and data[name.start_byte:name.end_byte] == b"main":
                    is_entry = True
        units.append(SourceUnit(start, end, is_entry))
    return tuple(units)


def _walk(node) -> Iterable:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _mask_spans(source: str, spans: Iterable[tuple[int, int]]) -> str:
    chars = list(source)
    for start, end in spans:
        for index in range(start, end):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def _compact_prompt(analysis: str, protected: Iterable[tuple[int, int]], comment_spans: Iterable[tuple[int, int]]):
    lines = source_lines(analysis)
    if not lines and analysis == "":
        return "", ()
    offsets = _char_line_starts(analysis)
    merged = []
    for start, end in sorted(protected):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    protected = tuple(merged)
    protected_ends = [end for _, end in protected]
    comment_spans = tuple(sorted(comment_spans, key=lambda span: span[1]))
    comment_ends = [end for _, end in comment_spans]
    kept: list[str] = []
    line_map: list[int] = []
    for number, line in enumerate(lines, 1):
        start = offsets[number - 1]
        end = start + len(line)
        body = line.rstrip("\r\n")
        newline = line[len(body):]
        protected_index = bisect_right(protected_ends, start)
        overlaps = protected_index < len(protected) and protected[protected_index][0] < end
        if not body.strip() and not overlaps:
            continue
        # Trailing spaces left by a masked line comment are presentation-only.
        body_end = start + len(body)
        comment_index = bisect_right(comment_ends, body_end) - 1
        if comment_index >= 0 and start <= comment_spans[comment_index][0] < body_end and not analysis[comment_spans[comment_index][0]:body_end].strip(" \t\f\v"):
            body = body.rstrip(" \t\f\v")
        kept.append(body + newline)
        line_map.append(number)
    return "".join(kept), tuple(line_map)


def _result(analysis, prompt, line_map, spans, tag, warnings, original_bytes, removed_bytes, units):
    if not line_map and prompt:
        line_map = tuple(range(1, len(source_lines(prompt)) + 1))
    return PreparedSource(
        analysis_source=analysis,
        prompt_source=prompt,
        line_map=tuple(line_map),
        language_tag=tag,
        warnings=tuple(warnings),
        removed_comment_count=len(spans),
        original_bytes=original_bytes,
        removed_comment_bytes=removed_bytes,
        policy_version=SOURCE_POLICY_VERSION,
        units=tuple(units),
    )


def _all_file_unit(source: str) -> SourceUnit:
    line_count = max(1, len(source_lines(source)))
    return SourceUnit(1, line_count, False)


def _char_line_starts(source: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(source):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _line_end_offset(source: str, starts: list[int], line: int) -> int:
    return starts[line] if line < len(starts) else len(source)


def _token_offset(starts: list[int], position: tuple[int, int]) -> int:
    line, column = position
    return starts[line - 1] + column


def _byte_line_starts(data: bytes) -> list[int]:
    return [0] + [index + 1 for index, value in enumerate(data) if value == 10]


def _byte_char_boundaries(data: bytes, offsets: Iterable[int]) -> dict[int, int]:
    result = {}
    previous = 0
    characters = 0
    for offset in sorted(set(offsets)):
        characters += len(data[previous:offset].decode("utf-8", errors="surrogatepass"))
        result[offset] = characters
        previous = offset
    return result
