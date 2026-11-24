"""Clara-style matching, clustering and reference selection.

Clara clusters correct solutions by an equivalence relation (same loop
structure plus matching variable traces) and repairs an incorrect attempt
against every cluster with the same control flow, keeping the cheapest repair
(cost = tree edit distance). Without execution traces we approximate:

* equivalence  -> same loop structure and same algorithmic technique set;
* repair cost  -> edit distance between identifier-abstracted token streams,
                  plus penalties when the loop structure or techniques differ.

Clara gives up when no cluster shares the control flow; here we still pick the
closest cluster but mark the match as structural mismatch so the report says
the student took a different route.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

from app.services.code_doctor.program_model import ProgramModel

# Clara's user study replaced repairs above cost 100 with a generic strategy
# hint. Our cost uses a 0-100 syntactic scale plus penalties; above this limit
# the report treats the attempt as a different approach rather than a small fix.
REPAIR_COST_LIMIT = 70
CONTROL_FLOW_PENALTY = 40
TECHNIQUE_PENALTY = 30


@dataclass(frozen=True)
class Candidate:
    """One stored approach seen through its representative program."""
    key: int
    model: ProgramModel
    language: str
    status: str = "auto"
    is_canonical: bool = False
    member_count: int = 1


@dataclass(frozen=True)
class MatchResult:
    key: int
    same_control_flow: bool
    technique_overlap: float
    distance: float
    cost: int

    @property
    def small_repair(self) -> bool:
        return self.same_control_flow and self.cost <= REPAIR_COST_LIMIT


def syntactic_distance(a: ProgramModel, b: ProgramModel) -> float:
    if not a.tokens and not b.tokens:
        return 0.0
    ratio = SequenceMatcher(None, a.tokens, b.tokens, autojunk=False).ratio()
    return round(1.0 - ratio, 4)


def technique_overlap(a: ProgramModel, b: ProgramModel) -> float:
    left, right = a.technique_key, b.technique_key
    if not left and not right:
        return 1.0
    return round(len(left & right) / len(left | right), 4)


def same_control_flow(a: ProgramModel, b: ProgramModel) -> bool:
    return a.parse_ok and b.parse_ok and a.cf_signature == b.cf_signature


def same_approach(a: ProgramModel, b: ProgramModel) -> bool:
    """Static stand-in for Clara's matching relation between two correct programs."""
    return same_control_flow(a, b) and a.technique_key == b.technique_key


def match(student: ProgramModel, reference: ProgramModel, key: int = 0) -> MatchResult:
    flow = same_control_flow(student, reference)
    overlap = technique_overlap(student, reference)
    if student.language == reference.language:
        distance = syntactic_distance(student, reference)
    else:
        distance = 0.5  # token streams of different languages are not comparable
    cost = round(distance * 100) + (0 if flow else CONTROL_FLOW_PENALTY) + round((1 - overlap) * TECHNIQUE_PENALTY)
    return MatchResult(key, flow, overlap, distance, cost)


def cluster(models: Sequence[ProgramModel]) -> list[list[int]]:
    """Group correct programs into approaches; the first member represents its cluster."""
    clusters: list[list[int]] = []
    for index, model in enumerate(models):
        for group in clusters:
            if same_approach(models[group[0]], model):
                group.append(index)
                break
        else:
            clusters.append([index])
    return clusters


def rank(student: ProgramModel, candidates: Sequence[Candidate]) -> list[MatchResult]:
    """Cheapest repair first; ties prefer the same language, approved and larger clusters."""
    status_order = {"approved": 0, "auto": 1, "pending": 2}
    scored = [(match(student, candidate.model, candidate.key), candidate) for candidate in candidates
              if candidate.status != "rejected"]
    scored.sort(key=lambda item: (
        item[0].cost,
        item[1].language != student.language,
        status_order.get(item[1].status, 3),
        -item[1].member_count,
    ))
    return [result for result, _ in scored]


def best_known(candidates: Sequence[Candidate]) -> Candidate | None:
    """The approach a teacher marked canonical, else the lowest estimated complexity."""
    usable = [c for c in candidates if c.status != "rejected"]
    if not usable:
        return None
    canonical = [c for c in usable if c.is_canonical]
    if canonical:
        return canonical[0]
    return min(usable, key=lambda c: (c.model.complexity()[0], c.status != "approved", -c.member_count))


def direction(result: MatchResult | None) -> str:
    """Deterministic prior for 'đúng hướng hay chưa' before the model is consulted."""
    if result is None:
        return "unknown"
    if result.same_control_flow and result.technique_overlap >= 0.5 and result.cost <= REPAIR_COST_LIMIT:
        return "on_track"
    if result.same_control_flow or result.technique_overlap >= 0.5:
        return "partially"
    return "off_track"
