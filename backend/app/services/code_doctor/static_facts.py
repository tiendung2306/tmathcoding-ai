"""Deterministic observations about a submission, given to the model as evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.code_doctor.program_model import ProgramModel
from app.services.feature_extractor import feature_extractor

OPERATIONS_PER_SECOND = 3 * 10**8


@dataclass
class Constraints:
    n_max: int | None
    n_text: str | None
    expectation: str
    value_max_exponent: int | None  # largest 10^k seen in the statement

    def as_dict(self) -> dict:
        return {"n_max": self.n_max, "n_text": self.n_text, "expected_complexity": self.expectation,
                "largest_value_power_of_ten": self.value_max_exponent}


@dataclass
class Fact:
    kind: str  # "info" | "risk"
    text: str
    lines: list[int] = field(default_factory=list)

    def __post_init__(self):
        self.lines = sorted(set(self.lines))

    def as_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text, "lines": self.lines}


_N_BOUND = re.compile(r"\b[nN]\s*(?:\\le|\\leq|<=|≤)\s*\$?\s*([0-9]+(?:\s*\^\s*\{?[0-9]+\}?)?)")


def _to_int(raw: str) -> int | None:
    raw = raw.replace(" ", "").replace("{", "").replace("}", "")
    try:
        if "^" in raw:
            base, exp = raw.split("^", 1)
            return int(base) ** min(int(exp), 30)
        return int(raw)
    except ValueError:
        return None


def extract_constraints(description: str) -> Constraints:
    """Prefer the bound on n itself; the generic extractor also counts K or M bounds."""
    parsed = feature_extractor.extract_constraints(description or "")
    normalized = feature_extractor._normalize_number_notation(description or "")
    n_values = [(v, raw) for raw in _N_BOUND.findall(normalized) if (v := _to_int(raw))]
    if n_values:
        n_max, n_text = max(n_values)
        parsed["complexity_expectation"] = feature_extractor.extract_constraints(f"N <= {n_max}").get("complexity_expectation")
    else:
        n_max, n_text = parsed.get("n_max_val"), parsed.get("n_limit_str")
    exponents = [int(e) for e in re.findall(r"10\s*\^\s*\{?\s*(\d{1,2})", normalized)]
    exponents += [len(n) - 1 for n in re.findall(r"(?<![\d.])([1-9]\d{8,18})(?![\d.])", normalized)]
    return Constraints(n_max, n_text, parsed.get("complexity_expectation") or "Chưa xác định",
                       max(exponents) if exponents else None)


def collect_facts(model: ProgramModel, constraints: Constraints, time_limit: float | None) -> list[Fact]:
    facts: list[Fact] = []
    rank, label = model.complexity()
    depth = model.max_loop_depth
    if model.parse_ok:
        facts.append(Fact("info", f"Ước lượng tĩnh độ phức tạp: {label}; vòng lặp lồng sâu nhất {depth} tầng.",
                          model.deepest_loop_lines()))
    else:
        facts.append(Fact("info", "Không phân tích được cấu trúc vòng lặp; chỉ so sánh theo từ khóa."))

    n = constraints.n_max
    budget = OPERATIONS_PER_SECOND * float(time_limit or 1.0)
    if n and depth >= 2 and n ** depth > budget:
        facts.append(Fact("risk", f"Với n ≤ {constraints.n_text or n}, {depth} vòng lặp lồng nhau cần khoảng "
                                  f"n^{depth} phép tính, vượt giới hạn {time_limit or 1}s.", model.deepest_loop_lines()))
    if n and depth == 1 and rank >= 1.5 and n * 20 > budget:
        facts.append(Fact("risk", f"n ≤ {constraints.n_text or n} lớn; O(n log n) có thể sát giới hạn thời gian."))

    big_values = constraints.value_max_exponent is not None and constraints.value_max_exponent >= 9
    if model.language in ("cpp", "c") and big_values and "type:64bit" not in model.features:
        facts.append(Fact("risk", f"Đề có giá trị tới 10^{constraints.value_max_exponent} nhưng mã không dùng kiểu 64-bit "
                                  "(long long); tổng hoặc tích có thể tràn số."))
    if model.language == "cpp" and "io:cin" in model.features and "io:fast" not in model.features and n and n >= 200000:
        facts.append(Fact("risk", "Đọc dữ liệu lớn bằng cin nhưng chưa tắt đồng bộ (ios::sync_with_stdio(false))."))
    if model.language == "python" and "io:input" in model.features and "io:fast" not in model.features and n and n >= 200000:
        facts.append(Fact("risk", "Dùng input() cho dữ liệu lớn; sys.stdin.readline nhanh hơn đáng kể."))
    if model.recursive and n and n >= 10**5:
        recursive_lines = [f.start_line for f in model.functions if f.recursive]
        if model.language == "python" and "py:recursionlimit" not in model.features:
            facts.append(Fact("risk", "Đệ quy với n lớn trong Python sẽ vượt giới hạn đệ quy mặc định (1000).", recursive_lines))
        elif model.language in ("cpp", "c"):
            facts.append(Fact("risk", f"Đệ quy có thể sâu tới {constraints.n_text or n} tầng; cần kiểm tra bộ nhớ stack.",
                              recursive_lines))
    if n and n <= 10**7:
        for array in model.static_arrays:
            if array.size < n:
                facts.append(Fact("risk", f"Mảng {array.name}[{array.size}] nhỏ hơn giới hạn n ≤ {constraints.n_text or n}.",
                                  [array.line]))
    return facts
