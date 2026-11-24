"""Static program model adapted from Clara (Gulwani, Radiček, Zuleger, PLDI 2018).

Clara keeps only the looping structure of a program as control flow and
collapses loop-free code into single locations. Two programs can only be
matched (and one repaired from the other) when that loop structure is the
same. Clara then compares variable traces on test inputs; this module has no
execution yet, so it records the loop structure, an identifier-abstracted
token stream (used as a syntactic repair-cost proxy) and algorithmic
features. Line numbers always refer to the original submission.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field

from app.services.feature_extractor import feature_extractor
from app.services.source_cleaner import prepare_source

MAX_MODEL_BYTES = 256 * 1024
MAX_TOKENS = 6000

# Library names that carry meaning for "how" a solution works; every other
# identifier becomes ID so that renamed variables do not change the distance.
KEEP_NAMES = frozenset({
    "vector", "map", "set", "multiset", "unordered_map", "unordered_set", "priority_queue",
    "queue", "stack", "deque", "pair", "string", "bitset", "array", "list", "tuple",
    "sort", "stable_sort", "lower_bound", "upper_bound", "binary_search", "unique", "reverse",
    "accumulate", "partial_sum", "max", "min", "swap", "abs", "gcd", "__gcd", "lcm", "pow",
    "sqrt", "memset", "fill", "next_permutation", "push_back", "pop_back", "push", "pop",
    "insert", "erase", "find", "count", "size", "begin", "end", "front", "back", "top",
    "cin", "cout", "scanf", "printf", "getline", "endl", "main",
    "range", "len", "sorted", "sum", "enumerate", "zip", "input", "print", "int", "map",
    "bisect_left", "bisect_right", "heappush", "heappop", "heapify", "deque", "defaultdict",
    "Counter", "append", "appendleft", "popleft", "dict", "set", "readline", "split",
})

FEATURE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("ds:vector", r"\bvector\s*<"),
    ("ds:map", r"\b(?:unordered_)?map\s*<|\bdict\(|\bdefaultdict\(|\bCounter\("),
    ("ds:set", r"\b(?:unordered_|multi)?set\s*<"),
    ("ds:heap", r"\bpriority_queue\s*<|\bheapq\b|\bheappush\("),
    ("ds:queue", r"\bqueue\s*<|\bdeque\b|\bpopleft\("),
    ("ds:stack", r"\bstack\s*<"),
    ("ds:2d-array", r"\b\w+\s*\[[^\]\n]+\]\s*\[[^\]\n]+\]"),
    ("algo:sort", r"\b(?:stable_)?sort\s*\(|\bsorted\s*\(|\.sort\s*\("),
    ("algo:binary-search", r"\b(?:lower_bound|upper_bound|binary_search|bisect_left|bisect_right|bisect)\b"),
    ("algo:gcd", r"\b(?:__gcd|gcd)\s*\("),
    ("algo:prefix-sum", r"\b(?:pre|pref|prefix|ps|sum|s)\s*\[\s*\w+\s*\]\s*=\s*\w+\s*\[\s*\w+\s*-\s*1\s*\]\s*\+"),
    ("algo:two-pointers", r"while\s*\(?\s*(?:l|i|left|lo)\s*<\s*(?:r|j|right|hi)\b"),
    ("algo:bitmask", r"1\s*<<|<<\s*1\b|&\s*\(\s*1\s*<<"),
    ("algo:memo-dp", r"\b(?:dp|memo|f)\s*\["),
    ("type:64bit", r"\blong\s+long\b|\bint64_t\b|\b__int128\b|\buint64_t\b"),
    ("io:fast", r"sync_with_stdio|cin\.tie|sys\.stdin|stdin\.readline"),
    ("io:cin", r"\bcin\s*>>"),
    ("io:scanf", r"\bscanf\s*\("),
    ("io:input", r"\binput\s*\("),
    ("py:recursionlimit", r"setrecursionlimit"),
)
# Features that describe the algorithm (used to decide "same approach").
TECHNIQUE_PREFIXES = ("ds:", "algo:")


@dataclass
class LoopNode:
    kind: str
    start_line: int
    end_line: int
    header: str
    children: list["LoopNode"] = field(default_factory=list)

    def shape(self) -> str:
        return "L(" + "".join(child.shape() for child in self.children) + ")"

    def depth(self) -> int:
        return 1 + max((child.depth() for child in self.children), default=0)

    def deepest(self) -> list["LoopNode"]:
        if not self.children:
            return [self]
        best = max(self.children, key=lambda child: child.depth())
        return [self] + best.deepest()


@dataclass
class FunctionModel:
    name: str
    start_line: int
    end_line: int
    loops: list[LoopNode] = field(default_factory=list)
    recursive: bool = False
    is_entry: bool = False

    def shape(self) -> str:
        return ("R" if self.recursive else "") + "".join(loop.shape() for loop in self.loops)

    def depth(self) -> int:
        return max((loop.depth() for loop in self.loops), default=0)


@dataclass
class StaticArray:
    name: str
    size: int
    line: int


@dataclass
class ProgramModel:
    language: str
    parse_ok: bool
    line_count: int
    functions: list[FunctionModel]
    tokens: list[str]
    features: frozenset[str]
    techniques: list[str]
    static_arrays: list[StaticArray]
    warnings: list[str] = field(default_factory=list)

    @property
    def cf_signature(self) -> str:
        """Clara control flow: only loops; loop-free functions collapse away."""
        if not self.parse_ok:
            return "?"
        entry = [f.shape() for f in self.functions if f.is_entry]
        helpers = sorted(f.shape() for f in self.functions if not f.is_entry and f.shape())
        return "E[" + "".join(entry) + "]" + "".join("F[" + shape + "]" for shape in helpers)

    @property
    def technique_key(self) -> frozenset[str]:
        return frozenset(f for f in self.features if f.startswith(TECHNIQUE_PREFIXES))

    @property
    def max_loop_depth(self) -> int:
        return max((f.depth() for f in self.functions), default=0)

    @property
    def recursive(self) -> bool:
        return any(f.recursive for f in self.functions)

    def deepest_loop_lines(self) -> list[int]:
        best: list[LoopNode] = []
        for function in self.functions:
            for loop in function.loops:
                chain = loop.deepest()
                if len(chain) > len(best):
                    best = chain
        return [loop.start_line for loop in best]

    def complexity(self) -> tuple[float, str]:
        """Rough static estimate from loop depth; a log-time structure adds log n.

        Only a ranking hint for comparing solutions of the same problem, never a proof.
        """
        depth = self.max_loop_depth
        log = bool(self.features & {"algo:sort", "algo:binary-search", "ds:set", "ds:heap"}) or (
            "ds:map" in self.features and self.language in ("cpp", "c"))
        if self.recursive and depth == 0:
            return 1.5, "đệ quy, phụ thuộc số lần gọi"
        if depth == 0:
            return (0.5, "O(log n)") if log else (0.0, "O(1)")
        if depth == 1:
            return (1.5, "O(n log n)") if log else (1.0, "O(n)")
        return float(depth), f"O(n^{depth})"

    def summary(self) -> dict:
        rank, label = self.complexity()
        return {
            "language": self.language,
            "control_flow": self.cf_signature,
            "max_loop_depth": self.max_loop_depth,
            "recursive": self.recursive,
            "estimated_complexity": label,
            "complexity_rank": rank,
            "features": sorted(self.features),
            "techniques": self.techniques,
            "functions": [
                {"name": f.name, "lines": [f.start_line, f.end_line], "loop_shape": f.shape(), "recursive": f.recursive}
                for f in self.functions
            ],
        }


def language_family(language_key: str | None) -> str:
    key = (language_key or "").strip().lower().replace("_", "-")
    if key.startswith(("cpp", "c++", "gnu-c++", "g++", "clang++")):
        return "cpp"
    if key in {"c", "c89", "c99", "c11", "c17", "c23", "gnu-c", "gcc"}:
        return "c"
    if key.startswith(("py", "python", "pypy")):
        return "python"
    return "other"


def build_program_model(source: str, language_key: str | None) -> ProgramModel:
    family = language_family(language_key)
    source = source or ""
    prepared = prepare_source(source, language_key or "")
    analysis = prepared.analysis_source
    line_count = len(source.splitlines()) or 1
    features = _features(analysis)
    techniques = feature_extractor.extract_code_features(analysis).get("detected_features", [])
    warnings: list[str] = []
    if len(source.encode("utf-8", errors="surrogatepass")) > MAX_MODEL_BYTES:
        warnings.append("Mã nguồn quá lớn để dựng mô hình chương trình.")
        return ProgramModel(family, False, line_count, [], _regex_tokens(analysis), features, techniques, [], warnings)
    try:
        if family in ("cpp", "c"):
            functions, tokens, arrays, ok = _cpp_model(analysis, family)
        elif family == "python":
            functions, tokens, arrays, ok = _python_model(analysis)
        else:
            functions, tokens, arrays, ok = [], _regex_tokens(analysis), [], False
    except Exception as exc:  # A model failure must not stop the diagnosis.
        warnings.append(f"Không dựng được mô hình chương trình ({type(exc).__name__}).")
        functions, tokens, arrays, ok = [], _regex_tokens(analysis), [], False
    return ProgramModel(family, ok, line_count, functions, tokens[:MAX_TOKENS], features, techniques, arrays, warnings)


def _features(text: str) -> frozenset[str]:
    return frozenset(name for name, pattern in FEATURE_PATTERNS if re.search(pattern, text))


# --------------------------------------------------------------------------- C / C++

_CPP_LOOPS = {"for_statement", "while_statement", "do_statement", "for_range_loop"}
_CPP_STRINGS = {"string_literal", "char_literal", "raw_string_literal", "concatenated_string", "system_lib_string"}
_CPP_NAMES = {"identifier", "field_identifier", "type_identifier", "namespace_identifier"}


def _cpp_model(text: str, family: str):
    from tree_sitter import Language, Parser
    if family == "c":
        import tree_sitter_c as grammar
    else:
        import tree_sitter_cpp as grammar
    parser = Parser(Language(grammar.language()))
    data = text.encode("utf-8", errors="surrogatepass")
    root = parser.parse(data).root_node
    lines = text.splitlines()

    def node_text(node) -> str:
        return data[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def header(node) -> str:
        row = node.start_point[0]
        return (lines[row].strip() if row < len(lines) else "")[:120]

    def collect_loops(node) -> list[LoopNode]:
        found: list[LoopNode] = []
        for child in node.children:
            if child.type in _CPP_LOOPS:
                loop = LoopNode(child.type.replace("_statement", "").replace("_loop", ""),
                                child.start_point[0] + 1, child.end_point[0] + 1, header(child))
                loop.children = collect_loops(child)
                found.append(loop)
            elif child.type != "function_definition":
                found.extend(collect_loops(child))
        return found

    def function_name(node) -> str:
        stack = [node.child_by_field_name("declarator")]
        while stack:
            current = stack.pop()
            if current is None:
                continue
            if current.type == "function_declarator":
                inner = current.child_by_field_name("declarator")
                return node_text(inner).split("::")[-1] if inner is not None else "?"
            stack.extend(reversed(current.children))
        return "?"

    def calls(node) -> set[str]:
        names: set[str] = set()
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == "call_expression":
                target = current.child_by_field_name("function")
                if target is not None:
                    names.add(node_text(target).split("::")[-1].split(".")[-1])
            stack.extend(current.children)
        return names

    def recursive_lambda(node) -> bool:
        # function<int(int)> dfs = [&](int u) { ... dfs(v) ... };
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == "init_declarator":
                value = current.child_by_field_name("value")
                target = current.child_by_field_name("declarator")
                if value is not None and target is not None and value.type == "lambda_expression":
                    if node_text(target) in calls(value):
                        return True
            stack.extend(current.children)
        return False

    functions: list[FunctionModel] = []
    stack = [root]
    while stack:
        current = stack.pop()
        if current.type == "function_definition":
            name = function_name(current)
            body = current.child_by_field_name("body")
            model = FunctionModel(name, current.start_point[0] + 1, current.end_point[0] + 1,
                                  collect_loops(body) if body is not None else [],
                                  is_entry=(name == "main"))
            model.recursive = name in calls(current) or recursive_lambda(current)
            functions.append(model)
        stack.extend(reversed(current.children))
    functions.sort(key=lambda f: f.start_line)
    if functions and not any(f.is_entry for f in functions):
        functions[0].is_entry = True

    tokens: list[str] = []

    def emit(node) -> None:
        if len(tokens) >= MAX_TOKENS or node.type == "comment":
            return
        if node.type in _CPP_STRINGS:
            tokens.append("STR")
            return
        if node.child_count == 0:
            if node.type in _CPP_NAMES:
                value = node_text(node)
                tokens.append(value if value in KEEP_NAMES else "ID")
            elif node.type == "number_literal":
                tokens.append("NUM")
            elif node.is_named:
                tokens.append(node_text(node))
            else:
                tokens.append(node.type)
            return
        for child in node.children:
            emit(child)

    emit(root)

    arrays: list[StaticArray] = []
    stack = [root]
    while stack:
        current = stack.pop()
        if current.type == "array_declarator":
            size = current.child_by_field_name("size")
            inner = current.child_by_field_name("declarator")
            value = _literal_int(node_text(size)) if size is not None else None
            if value is not None and inner is not None and inner.type == "identifier":
                arrays.append(StaticArray(node_text(inner), value, current.start_point[0] + 1))
        stack.extend(current.children)
    has_error = any(node.type == "ERROR" for node in _walk(root))
    return functions, tokens, arrays, bool(functions) and not has_error


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(current.children)


def _literal_int(text: str) -> int | None:
    """Evaluate simple sizes such as 100005, 1e5+5 or 2*100000+7 (no names, no powers)."""
    try:
        tree = ast.parse(text.strip().replace("'", ""), mode="eval")
    except SyntaxError:
        return None

    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            left, right = value(node.left), value(node.right)
            if left is None or right is None:
                return None
            result = left + right if isinstance(node.op, ast.Add) else left - right if isinstance(node.op, ast.Sub) else left * right
            return result if abs(result) < 10**12 else None
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = value(node.operand)
            return -inner if inner is not None else None
        return None

    result = value(tree.body)
    return int(result) if result is not None and 0 < result < 10**12 else None


# --------------------------------------------------------------------------- Python

def _python_model(text: str):
    tree = ast.parse(text)

    def loops_of(nodes) -> list[LoopNode]:
        found: list[LoopNode] = []
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                loop = LoopNode("for" if not isinstance(node, ast.While) else "while",
                                node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno,
                                (ast.get_source_segment(text, node) or "").splitlines()[0][:120])
                loop.children = loops_of(list(ast.iter_child_nodes(node)))
                found.append(loop)
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                comp = LoopNode("comprehension", node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno,
                                (ast.get_source_segment(text, node) or "")[:120])
                for _ in node.generators[1:]:
                    comp = LoopNode("comprehension", comp.start_line, comp.end_line, comp.header, [comp])
                found.append(comp)
            else:
                found.extend(loops_of(list(ast.iter_child_nodes(node))))
        return found

    def called_names(node) -> set[str]:
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    names.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    names.add(child.func.attr)
        return names

    functions: list[FunctionModel] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            model = FunctionModel(node.name, node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno,
                                  loops_of(node.body), recursive=node.name in called_names(node),
                                  is_entry=node.name in ("main", "solve"))
            functions.append(model)
    top_level = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    module = FunctionModel("<module>", 1, len(text.splitlines()) or 1, loops_of(top_level), is_entry=True)
    if any(f.is_entry for f in functions) and not module.loops:
        module.is_entry = False
    functions = sorted(functions, key=lambda f: f.start_line)
    if module.is_entry or not functions:
        for function in functions:
            function.is_entry = False
        functions.insert(0, module)
    else:
        entries = [f for f in functions if f.is_entry]
        for function in entries[1:]:
            function.is_entry = False

    tokens: list[str] = []
    for item in tokenize.generate_tokens(io.StringIO(text).readline):
        if len(tokens) >= MAX_TOKENS:
            break
        if item.type == tokenize.NAME:
            import keyword
            tokens.append(item.string if keyword.iskeyword(item.string) or item.string in KEEP_NAMES else "ID")
        elif item.type == tokenize.NUMBER:
            tokens.append("NUM")
        elif item.type == tokenize.STRING:
            tokens.append("STR")
        elif item.type == tokenize.OP:
            tokens.append(item.string)
        elif item.type == tokenize.INDENT:
            tokens.append("INDENT")
        elif item.type == tokenize.DEDENT:
            tokens.append("DEDENT")
    return functions, tokens, [], True


# --------------------------------------------------------------------------- fallback

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\S")


def _regex_tokens(text: str) -> list[str]:
    out: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        value = match.group(0)
        if value[0].isdigit():
            out.append("NUM")
        elif value[0] in "\"'":
            out.append("STR")
        elif value[0].isalpha() or value[0] == "_":
            out.append(value if value in KEEP_NAMES else "ID")
        else:
            out.append(value)
        if len(out) >= MAX_TOKENS:
            break
    return out
