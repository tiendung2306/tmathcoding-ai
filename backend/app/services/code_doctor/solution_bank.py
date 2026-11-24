"""Solution bank: correct submissions grouped into approaches (Clara clusters).

The bank starts from the accepted samples the Source API returns for a
problem (one is enough) and grows every time Code Doctor sees another AC
submission: a program that matches an existing cluster joins it, otherwise it
opens a new approach for a teacher to review.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field

from app.services.code_doctor.matching import match, same_approach
from app.services.code_doctor.program_model import ProgramModel, build_program_model
from app.services.code_doctor.store import ApproachRecord, DoctorStore, MemberRecord
from app.services.source_cleaner import PreparedSource, prepare_source

logger = logging.getLogger(__name__)

SAMPLE_LIMIT = 3
TECHNIQUE_NAMES = {
    "algo:prefix-sum": "Mảng cộng dồn",
    "algo:two-pointers": "Hai con trỏ",
    "algo:binary-search": "Tìm kiếm nhị phân",
    "algo:sort": "Sắp xếp",
    "algo:memo-dp": "Quy hoạch động",
    "algo:bitmask": "Bitmask",
    "algo:gcd": "Ước chung lớn nhất",
    "ds:heap": "Hàng đợi ưu tiên",
    "ds:map": "Map",
    "ds:set": "Set",
    "ds:queue": "Hàng đợi",
    "ds:stack": "Ngăn xếp",
    "ds:2d-array": "Mảng 2 chiều",
}
LANGUAGE_NAMES = {"cpp": "C++", "c": "C", "python": "Python", "other": "khác"}


@dataclass
class BankEntry:
    record: ApproachRecord
    model: ProgramModel | None = None
    prepared: PreparedSource | None = None


@dataclass
class BankView:
    entries: list[BankEntry] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    @property
    def active(self) -> list[BankEntry]:
        return [e for e in self.entries if e.record.status != "rejected" and e.model is not None]


def static_name(model: ProgramModel) -> str:
    parts = [TECHNIQUE_NAMES[key] for key in sorted(model.technique_key) if key in TECHNIQUE_NAMES]
    rank_label = model.complexity()[1]
    head = " + ".join(parts[:3]) if parts else ("Đệ quy" if model.recursive else "Duyệt trực tiếp")
    return f"{head} ({rank_label}, {LANGUAGE_NAMES.get(model.language, model.language)})"[:255]


def source_hash(source: str) -> str:
    return hashlib.sha256((source or "").encode("utf-8", errors="surrogatepass")).hexdigest()


class SolutionBank:
    def __init__(self, store: DoctorStore):
        self.store = store
        self._locks: OrderedDict[int, asyncio.Lock] = OrderedDict()

    def _lock(self, problem_id: int) -> asyncio.Lock:
        lock = self._locks.pop(problem_id, None) or asyncio.Lock()
        self._locks[problem_id] = lock
        while len(self._locks) > 256:
            self._locks.popitem(last=False)
        return lock

    async def view(self, problem_id: int, source, actor_profile_id: int) -> BankView:
        """Load approaches with their representative programs and absorb new samples."""
        async with self._lock(problem_id):
            return await self._view(problem_id, source, actor_profile_id)

    async def _view(self, problem_id: int, source, actor_profile_id: int) -> BankView:
        view = BankView()
        samples = []
        try:
            page = await source.get_problem_accepted_samples(problem_id, actor_profile_id=actor_profile_id,
                                                             limit=SAMPLE_LIMIT)
            samples = list(page.items)
        except Exception as exc:  # 403 without source scope, provider errors
            logger.info("Code Doctor: accepted samples unavailable for problem %s: %s", problem_id, exc)
            view.limitations.append("Không lấy được bài AC mẫu từ hệ thống nguồn.")
        by_id = {sample.submission_id: sample for sample in samples}

        records = await self.store.list_approaches(problem_id)
        for record in records:
            entry = BankEntry(record)
            sample = by_id.get(record.representative_submission_id)
            code, language_key = (sample.source_code, sample.language_key) if sample else (None, None)
            if code is None:
                try:
                    rep = await source.get_submission(record.representative_submission_id,
                                                      actor_profile_id=actor_profile_id,
                                                      include_source=True, include_testcases=False)
                    code = rep.source_code
                    language_key = rep.language.key if rep.language else None
                except Exception as exc:
                    logger.info("Code Doctor: representative %s unavailable: %s",
                                record.representative_submission_id, exc)
            if code:
                entry.model, entry.prepared = await _model(code, language_key)
            view.entries.append(entry)

        known = await self.store.member_ids(problem_id)
        for sample in samples:
            if sample.submission_id not in known:
                await self._absorb(problem_id, sample.submission_id, sample.source_code, sample.language_key, view)
        if records and not view.active:
            view.limitations.append("Không đọc được mã của các hướng giải đã lưu.")
        return view

    async def absorb(self, problem_id: int, submission_id: int, code: str, language_key: str | None,
                     view: BankView) -> ApproachRecord | None:
        """Add one more accepted submission to the bank (Clara: wisdom of the crowd)."""
        async with self._lock(problem_id):
            if submission_id in await self.store.member_ids(problem_id):
                return None
            return await self._absorb(problem_id, submission_id, code, language_key, view)

    async def _absorb(self, problem_id, submission_id, code, language_key, view: BankView):
        if not code or not code.strip():
            return None
        model, prepared = await _model(code, language_key)
        member = MemberRecord(0, submission_id, problem_id, (language_key or "")[:32] or None, source_hash(code))
        for entry in view.entries:
            if entry.model is not None and entry.record.language == model.language and same_approach(entry.model, model):
                member.approach_id = entry.record.id
                member.cost = match(model, entry.model).cost
                await self.store.add_member(member)
                entry.record.member_count += 1
                return entry.record
        record = ApproachRecord(
            id=None, problem_id=problem_id, language=model.language, name=static_name(model),
            control_flow=model.cf_signature, techniques=sorted(model.technique_key),
            complexity_rank=model.complexity()[0], representative_submission_id=submission_id,
            time_complexity=model.complexity()[1],
        )
        created = await self.store.create_approach(record, member)
        view.entries.append(BankEntry(created, model, prepared))
        return created


async def _model(code: str, language_key: str | None):
    model = await asyncio.to_thread(build_program_model, code, language_key)
    prepared = await asyncio.to_thread(prepare_source, code, language_key or "unknown")
    return model, prepared
