"""Code Doctor v2: teacher-facing review of AC and failed submissions.

Pipeline (see docs/CODE_DOCTOR.md):
1. read the submission, problem and test results through Source API;
2. build a Clara-style program model and deterministic static facts;
3. match the submission against the solution bank (clusters of AC programs);
4. ask the model for a structured report grounded in those facts;
5. validate the report, store it in tmath_dashboard and cache it.
When the model is unavailable the report is still produced from steps 2-3.
"""

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from typing import List

from fastapi import HTTPException

from app.core.config import settings
from app.core.job_manager import job_manager
from app.core.llm_adapter import doctor_profile, llm_adapter  # noqa: F401  (llm_adapter patched in tests)
from app.core.redis import cache_delete, cache_get, cache_set
from app.core.time import utc_now
from app.schemas.ai import CodeDoctorDiagnosis, CodeDoctorResponse
from app.schemas.code_doctor import (
    DoctorApproachInfo, DoctorApproachItem, DoctorApproachUpdate, DoctorFeedbackRequest, DoctorFinding,
    DoctorReportData, DoctorStaticFact, DoctorTestSummary,
)
from app.schemas.jobs import JobCreateResponse, JobStatus, JobType
from app.schemas.student import FailedSubmissionItem, SubmissionDetailResponse, TestCaseDetailItem
from app.services.code_doctor import analyzer
from app.services.code_doctor.analyzer import AnalysisInput, AnalysisUnavailable, ReferenceContext
from app.services.code_doctor.matching import Candidate, best_known, direction, rank
from app.services.code_doctor.program_model import build_program_model
from app.services.code_doctor.solution_bank import BankView, SolutionBank
from app.services.code_doctor.static_facts import collect_facts, extract_constraints
from app.services.code_doctor.store import DoctorStore, SqlDoctorStore
from app.services.code_doctor.validator import apply_model_output, clean_text
from app.services.source_cleaner import SOURCE_POLICY_VERSION, prepare_source
from app.services.source_gateway import SourceGateway, get_source_gateway_client

logger = logging.getLogger(__name__)
MEMORY_CACHE_MAX_ITEMS = 256
POLICY_VERSION = "doctor-v2.0"
PENDING_STATUSES = {"QU", "P", "G"}
DIAGNOSABLE = {"AC", "WA", "TLE", "RTE", "IR", "CE", "MLE", "OLE"}
DEFAULT_MEMORY_LIMIT_KB = 262144
CATEGORY = {
    "AC": "ACCEPTED", "WA": "WRONG_ANSWER", "TLE": "TIME_LIMIT_EXCEEDED", "RTE": "RUNTIME_ERROR",
    "IR": "RUNTIME_ERROR", "CE": "COMPILE_ERROR", "MLE": "MEMORY_LIMIT_EXCEEDED", "OLE": "OUTPUT_LIMIT_EXCEEDED",
}
DIRECTION_TEXT = {
    "on_track": "Bài nộp cùng cấu trúc vòng lặp và kỹ thuật với hướng giải \"{name}\"; lỗi nhiều khả năng nằm ở chi tiết cài đặt.",
    "partially": "Bài nộp có điểm chung với hướng giải \"{name}\" nhưng khác cấu trúc vòng lặp hoặc kỹ thuật chính.",
    "off_track": "Cách làm khác các lời giải đúng đã biết; gần nhất là \"{name}\".",
}


def kb_to_mb(value_kb) -> str:
    """The judge reports memory in KB; prompts and advice speak in MB."""
    if value_kb is None:
        return "?"
    megabytes = float(value_kb) / 1024
    return f"{megabytes:.0f}" if megabytes >= 100 or megabytes.is_integer() else f"{megabytes:.1f}"


def _verdict_of(submission) -> str:
    return (submission.result or "").strip().upper()


class CodeDoctorService:
    def __init__(self, store: DoctorStore | None = None):
        # Bounded LRU fallback; Redis remains the durable short-lived cache.
        self._memory_cache: OrderedDict[str, CodeDoctorResponse] = OrderedDict()
        self.store: DoctorStore = store or SqlDoctorStore()
        self.bank = SolutionBank(self.store)
        self._card_tasks: dict[int, asyncio.Task] = {}

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _verdict_response(submission_id: int, submission, problem) -> CodeDoctorResponse | None:
        verdict = _verdict_of(submission)
        status = (submission.status or "").strip().upper()
        if status in PENDING_STATUSES or not verdict:
            category = "PENDING"
            advice = "Bài nộp chưa có kết quả chấm cuối cùng. Hãy đợi hệ thống chấm xong rồi yêu cầu Code Doctor."
        elif status == "IE":
            category = "IE"
            advice = "Trạng thái chấm của bài nộp là IE. Code Doctor chưa thể kết luận từ kết quả này; hãy kiểm tra lại trạng thái chấm."
        elif not submission.source_code or not submission.source_code.strip():
            category = verdict
            advice = "Bài nộp chưa có mã nguồn để phân tích. Hãy xem kết quả chấm và phản hồi testcase hiện có."
        elif verdict not in DIAGNOSABLE:
            category = verdict
            advice = f"Bài nộp được chấm {verdict}. Code Doctor chưa hỗ trợ phân tích tự động cho kết quả này; hãy xem phản hồi chấm của bài nộp."
        else:
            return None
        problem_name = problem.title or problem.name or "Bài toán"
        return CodeDoctorResponse(
            submission_id=submission_id, user_id=submission.profile_id, problem_name=problem_name,
            diagnosis=CodeDoctorDiagnosis(error_category=category, advice=advice, summary=advice, origin="verdict"),
        )

    @staticmethod
    def _cache_key(submission_id: int, input_fingerprint: str = "") -> str:
        profile = doctor_profile()
        policy = f"{POLICY_VERSION}:{SOURCE_POLICY_VERSION}:{analyzer.PROMPT_MARGIN_TOKENS}:{profile.model}:{profile.context_window}"
        namespace = hashlib.sha256(policy.encode()).hexdigest()[:16]
        return f"tmath:code_doctor:{namespace}:submission:{submission_id}:{input_fingerprint}"

    @staticmethod
    def _input_fingerprint(submission, problem) -> str:
        """Hash all provider inputs that can change a diagnosis; never persist their contents."""
        def iso(value):
            return value.isoformat() if value else None
        language = getattr(submission, "language", None)
        payload = {
            "submission": {
                "version": getattr(submission, "version", None),
                "updated_at": iso(getattr(submission, "updated_at", None)),
                "result": getattr(submission, "result", None),
                "status": getattr(submission, "status", None),
                "points": getattr(submission, "points", None),
                "time": getattr(submission, "time", None),
                "memory": getattr(submission, "memory", None),
                "submitted_at": iso(getattr(submission, "submitted_at", None)),
                "language": {k: getattr(language, k, None) for k in ("id", "key", "name", "common_name")},
                "source_code": getattr(submission, "source_code", None),
                "testcases": [tc.model_dump(mode="json") for tc in getattr(submission, "testcases", [])],
            },
            "problem": {k: getattr(problem, k, None) for k in
                        ("version", "title", "name", "code", "description", "time_limit", "memory_limit", "points")},
        }
        payload["problem"]["updated_at"] = iso(getattr(problem, "updated_at", None))
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _store_memory_cache(self, key: str, response: CodeDoctorResponse) -> None:
        self._memory_cache.pop(key, None)
        self._memory_cache[key] = response
        while len(self._memory_cache) > MEMORY_CACHE_MAX_ITEMS:
            self._memory_cache.popitem(last=False)

    def _get_memory_cache(self, key: str) -> CodeDoctorResponse | None:
        response = self._memory_cache.get(key)
        if response is not None:
            self._memory_cache.move_to_end(key)
        return response

    @staticmethod
    def _tests(submission) -> tuple[DoctorTestSummary, str]:
        cases = list(getattr(submission, "testcases", []) or [])
        if not cases:
            return DoctorTestSummary(), "- Không có chi tiết từng test."
        passed = sum(1 for tc in cases if tc.status == "AC")
        failed = [tc for tc in cases if tc.status != "AC"]
        lines = [f"- Đạt {passed}/{len(cases)} test."]
        for tc in failed[:3]:
            details = []
            if tc.time is not None:
                details.append(f"thời gian {tc.time:.2f}s")
            if tc.memory is not None:
                details.append(f"bộ nhớ {kb_to_mb(tc.memory)}MB")
            if tc.feedback:
                details.append(f"phản hồi: {tc.feedback[:120]}")
            if tc.output:
                details.append("in ra: '" + tc.output.strip().replace("\n", " ")[:60] + "'")
            lines.append(f"  + Test #{tc.case} [{tc.status}]: {', '.join(details) or 'không có chi tiết'}")
        summary = DoctorTestSummary(passed=passed, total=len(cases),
                                    failed_cases=[tc.case for tc in failed if tc.case is not None][:50])
        return summary, "\n".join(lines)

    @staticmethod
    def _approach_info(entry, result=None) -> DoctorApproachInfo:
        record = entry.record
        return DoctorApproachInfo(
            approach_id=record.id, name=record.name, status=record.status, summary=record.summary,
            time_complexity=record.time_complexity, member_count=record.member_count,
            same_control_flow=result.same_control_flow if result else None,
            repair_cost=result.cost if result else None,
        )

    # ------------------------------------------------------------------ pipeline

    async def _diagnose_submission_core(
        self, submission_id: int, source: SourceGateway, actor_profile_id: int, submission=None,
    ) -> CodeDoctorResponse:
        # Source code and testcase access are checked by the provider on every request.
        submission = submission or await source.get_submission(
            submission_id, actor_profile_id=actor_profile_id, include_source=True, include_testcases=True,
        )
        problem = await source.get_problem(submission.problem_id, actor_profile_id=actor_profile_id)
        verdict_response = self._verdict_response(submission_id, submission, problem)
        if verdict_response is not None:
            return verdict_response
        fingerprint = self._input_fingerprint(submission, problem)
        redis_key = self._cache_key(submission_id, fingerprint)
        report = await self._build_report(submission, problem, source, actor_profile_id)

        try:
            await self.store.save_report(
                submission_id, fingerprint, submission.problem_id,
                report.nearest_approach.approach_id if report.nearest_approach else None,
                report.verdict, report.origin, report.model, POLICY_VERSION, report.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.warning("Code Doctor: report not stored: %s: %s", type(exc).__name__, exc)

        response = self._response(submission_id, submission, problem, report)
        fallback = report.origin != "ai"
        # A temporary model failure must not lock in a fallback report for a week.
        await cache_set(redis_key, response.model_dump_json(), expire=300 if fallback else 7 * 86400)
        if fallback:
            self._memory_cache.pop(redis_key, None)
        else:
            self._store_memory_cache(redis_key, response)
        return response

    def _response(self, submission_id, submission, problem, report: DoctorReportData) -> CodeDoctorResponse:
        return CodeDoctorResponse(
            submission_id=submission_id, user_id=submission.profile_id,
            problem_name=problem.title or problem.name or "Bài toán",
            diagnosis=CodeDoctorDiagnosis(
                error_category=CATEGORY.get(report.verdict, report.verdict), advice=report.overview,
                summary=report.overview, origin=report.origin, fallback_reason=report.fallback_reason,
            ),
            report=report,
        )

    async def _build_report(self, submission, problem, source, actor_profile_id) -> DoctorReportData:
        verdict = _verdict_of(submission)
        code = submission.source_code
        language_key = submission.language.key if submission.language else None
        language_name = (submission.language.name or submission.language.common_name or "C++") if submission.language else "C++"
        prepared = await asyncio.to_thread(prepare_source, code, language_key or "unknown")
        model = await asyncio.to_thread(build_program_model, code, language_key)
        constraints = extract_constraints(problem.description or "")
        facts = collect_facts(model, constraints, problem.time_limit)
        tests, tests_text = self._tests(submission)
        limitations = list(model.warnings)

        try:
            view = await self.bank.view(submission.problem_id, source, actor_profile_id)
        except Exception as exc:
            logger.warning("Code Doctor: solution bank unavailable: %s: %s", type(exc).__name__, exc)
            view = BankView(limitations=["Không đọc được ngân hàng lời giải."])
        limitations += view.limitations
        active = view.active
        candidates = [Candidate(i, e.model, e.record.language, e.record.status, e.record.is_canonical,
                                e.record.member_count) for i, e in enumerate(active)]
        ranked = rank(model, candidates)
        nearest_result = ranked[0] if ranked else None
        nearest = active[nearest_result.key] if nearest_result else None
        best_candidate = best_known(candidates)
        best = active[best_candidate.key] if best_candidate else None
        best_result = next((r for r in ranked if best_candidate and r.key == best_candidate.key), None)

        # Reference code: for AC compare with the best approach when it is faster,
        # otherwise with the nearest one; never with the submission itself.
        own = submission.submission_id
        reference, reference_label = None, ""
        student_rank = model.complexity()[0]
        if verdict == "AC" and best and best.record.representative_submission_id != own \
                and best.model and best.model.complexity()[0] < student_rank:
            reference, reference_label = best, "hướng giải tốt nhất"
        elif nearest and nearest.record.representative_submission_id != own:
            reference, reference_label = nearest, "hướng giải gần nhất"
        elif best and best.record.representative_submission_id != own:
            reference, reference_label = best, "hướng giải tốt nhất"

        report = DoctorReportData(
            verdict=verdict, origin="fallback", overview="",
            direction=direction(nearest_result) if verdict != "AC" else ("on_track" if nearest else "unknown"),
            estimated_complexity=model.complexity()[1], expected_complexity=constraints.expectation,
            nearest_approach=self._approach_info(nearest, nearest_result) if nearest else None,
            best_approach=self._approach_info(best, best_result) if best else None,
            static_facts=[DoctorStaticFact(**f.as_dict()) for f in facts],
            tests=tests, limitations=limitations, generated_at=utc_now().isoformat() + "Z",
        )
        if verdict == "TLE" and report.direction == "off_track" and tests.passed:
            # Correct on small tests but slow: the idea works, the approach is too slow.
            report.direction = "partially"
        self._fill_fallback(report, facts, nearest)

        data = AnalysisInput(
            verdict=verdict, problem_title=problem.title or problem.name or "Bài toán",
            problem_code=problem.code or f"P{submission.problem_id}", statement=problem.description or "",
            time_limit=problem.time_limit or 1.0,
            memory_limit_mb=kb_to_mb(problem.memory_limit or DEFAULT_MEMORY_LIMIT_KB),
            constraints=constraints, tests_text=tests_text, student=prepared, student_model=model, facts=facts,
            nearest=self._reference_context(nearest, nearest_result), best=self._reference_context(best, best_result),
            language_name=language_name,
            reference_code=reference.prepared if reference else None, reference_label=reference_label,
        )
        try:
            output, prompt_limitations, model_name = await analyzer.analyze(data)
            report.origin = "ai"
            report.model = model_name
            report.limitations += prompt_limitations
            risk_lines = {line for f in facts if f.kind == "risk" for line in f.lines}
            apply_model_output(report, output, model.line_count, risk_lines)
        except AnalysisUnavailable as exc:
            report.fallback_reason = str(exc)
            logger.info("Code Doctor fallback submission=%s reason=%s", submission.submission_id, exc)

        if report.origin == "ai" and nearest is not None:
            self._describe_later(nearest, problem.description or "")
        if verdict == "AC":
            try:
                await self.bank.absorb(submission.problem_id, own, code, language_key, view)
            except Exception as exc:
                logger.warning("Code Doctor: AC submission not added to bank: %s", exc)
        return report

    def _describe_later(self, entry, statement: str) -> None:
        """Write a model-made card for an approach that only has a static name.

        Runs after the report so the teacher never waits for it; later reports
        use the card's summary as the description of that approach.
        """
        record = entry.record
        if record.id is None or record.card_origin != "static" or entry.prepared is None or entry.model is None:
            return
        running = self._card_tasks.get(record.id)
        if running is not None and not running.done():
            return

        async def describe():
            try:
                card = await analyzer.approach_card(statement, entry.prepared, entry.model)
                await self.store.update_approach(
                    record.id, name=clean_text(card.name)[:120] or record.name, summary=clean_text(card.summary),
                    key_ideas=[clean_text(i) for i in card.key_ideas][:6],
                    pitfalls=[clean_text(i) for i in card.pitfalls][:6],
                    time_complexity=clean_text(card.time_complexity)[:64] or record.time_complexity,
                    card_origin="ai",
                )
            except Exception as exc:
                logger.info("Code Doctor: approach card not written for %s: %s", record.id, exc)
            finally:
                self._card_tasks.pop(record.id, None)

        self._card_tasks[record.id] = asyncio.create_task(describe())

    @staticmethod
    def _reference_context(entry, result) -> ReferenceContext | None:
        if entry is None:
            return None
        record = entry.record
        return ReferenceContext(record.name, record.summary, record.time_complexity, record.status,
                                result.same_control_flow if result else None, result.cost if result else None)

    @staticmethod
    def _fill_fallback(report: DoctorReportData, facts, nearest) -> None:
        """Deterministic report used until (or instead of) the model's analysis."""
        tests = report.tests
        parts = []
        if report.verdict == "AC":
            parts.append("Bài đạt toàn bộ test." if tests.total is None else f"Bài đạt {tests.passed}/{tests.total} test.")
            parts.append(f"Ước lượng tĩnh {report.estimated_complexity}.")
            if report.best_approach and report.best_approach.time_complexity:
                parts.append(f"Hướng giải tốt nhất đã biết: {report.best_approach.name}.")
            report.strengths = [DoctorFinding(point="Chương trình cho kết quả đúng trên toàn bộ bộ test.")]
        else:
            if tests.total:
                parts.append(f"Bài {report.verdict}, đạt {tests.passed}/{tests.total} test.")
            else:
                parts.append(f"Bài được chấm {report.verdict}.")
            if nearest is not None and report.direction in DIRECTION_TEXT:
                parts.append(DIRECTION_TEXT[report.direction].format(name=nearest.record.name))
            elif nearest is None:
                parts.append("Chưa có lời giải AC để so sánh.")
            if tests.passed:
                report.strengths = [DoctorFinding(point=f"Đạt {tests.passed}/{tests.total} test, phần xử lý chính có thể đã đúng.")]
        risks = [f for f in facts if f.kind == "risk"]
        report.weaknesses = [DoctorFinding(point=f.text, lines=f.lines,
                                           severity="high" if report.verdict in ("TLE", "MLE", "RTE") else "medium")
                             for f in risks]
        if risks:
            parts.append(f"Phân tích tĩnh thấy {len(risks)} rủi ro.")
        report.overview = clean_text(" ".join(parts))
        report.confidence = "low"
        report.limitations.append("Nội dung dựa trên phân tích tĩnh và so khớp cấu trúc; AI chưa đọc mã.")

    # ------------------------------------------------------------------ entry points

    async def _execute_diagnose(self, submission_id: int, actor_profile_id: int) -> dict:
        """Background executor run by LLMJobManager inside concurrency Semaphore."""
        res = await self._diagnose_submission_core(submission_id, get_source_gateway_client(), actor_profile_id)
        return res.model_dump(mode="json")

    async def _cached(self, redis_key: str, submission_id: int, fingerprint: str):
        cached_json = await cache_get(redis_key)
        if cached_json:
            try:
                return json.loads(cached_json)
            except Exception as exc:
                logger.warning("Failed to parse cached JSON for '%s': %s", redis_key, exc)
        memory_result = self._get_memory_cache(redis_key)
        if memory_result is not None:
            return memory_result.model_dump(mode="json")
        return None

    async def diagnose_submission_async(
        self, submission_id: int, source: SourceGateway, actor_profile_id: int, force_refresh: bool = False,
    ) -> JobCreateResponse:
        """Returns a cached result or a job id; access is checked before any cache read."""
        submission = await source.get_submission(
            submission_id, actor_profile_id=actor_profile_id, include_source=True, include_testcases=True,
        )
        problem = await source.get_problem(submission.problem_id, actor_profile_id=actor_profile_id)
        verdict_response = self._verdict_response(submission_id, submission, problem)
        if verdict_response is not None:
            return JobCreateResponse(job_id=f"verdict_{submission_id}", status=JobStatus.COMPLETED,
                                     message="Đã có kết quả chấm của bài nộp.", result=verdict_response.model_dump(mode="json"))
        fingerprint = self._input_fingerprint(submission, problem)
        redis_key = self._cache_key(submission_id, fingerprint)
        if force_refresh:
            await cache_delete(redis_key)
            self._memory_cache.pop(redis_key, None)
        else:
            cached = await self._cached(redis_key, submission_id, fingerprint)
            if cached is not None:
                return JobCreateResponse(job_id=f"cached_{submission_id}", status=JobStatus.COMPLETED,
                                         message="Kết quả chẩn đoán đã sẵn sàng từ bộ nhớ đệm.", result=cached)
            stored = await self._stored_report(submission_id, fingerprint, submission, problem)
            if stored is not None:
                return JobCreateResponse(job_id=f"stored_{submission_id}", status=JobStatus.COMPLETED,
                                         message="Kết quả chẩn đoán đã lưu.", result=stored.model_dump(mode="json"))

        job_id, is_new = await job_manager.enqueue_job(
            JobType.CODE_DOCTOR, self._execute_diagnose, submission_id, actor_profile_id,
            entity_key=redis_key, timeout_seconds=int(settings.DOCTOR_LLM_TIMEOUT_SECONDS + 90),
            metadata={"submission_id": submission_id},
        )
        return JobCreateResponse(job_id=job_id, status=JobStatus.PENDING if is_new else JobStatus.PROCESSING,
                                 message="Tác vụ chẩn đoán bài nộp đang được xử lý ngầm.")

    async def _stored_report(self, submission_id, fingerprint, submission, problem) -> CodeDoctorResponse | None:
        """Reports produced by the model survive Redis expiry in tmath_dashboard."""
        try:
            data = await self.store.get_report(submission_id, fingerprint)
        except Exception as exc:
            logger.info("Code Doctor: stored report unavailable: %s", exc)
            return None
        if not data or data.get("origin") != "ai":
            return None
        try:
            return self._response(submission_id, submission, problem, DoctorReportData.model_validate(data))
        except Exception:
            return None

    async def diagnose_submission(
        self, submission_id: int, source: SourceGateway, actor_profile_id: int, force_refresh: bool = False,
    ) -> CodeDoctorResponse:
        """Synchronous helper preserving backward compatibility."""
        submission = await source.get_submission(
            submission_id, actor_profile_id=actor_profile_id, include_source=True, include_testcases=True,
        )
        problem = await source.get_problem(submission.problem_id, actor_profile_id=actor_profile_id)
        verdict_response = self._verdict_response(submission_id, submission, problem)
        if verdict_response is not None:
            return verdict_response
        if not force_refresh:
            fingerprint = self._input_fingerprint(submission, problem)
            cached = await self._cached(self._cache_key(submission_id, fingerprint), submission_id, fingerprint)
            if cached is not None:
                return CodeDoctorResponse.model_validate(cached)
        return await self._diagnose_submission_core(submission_id, source, actor_profile_id, submission)

    # ------------------------------------------------------------------ teacher review

    async def list_approaches(self, problem_id: int, source: SourceGateway, actor_profile_id: int) -> List[DoctorApproachItem]:
        await source.get_problem(problem_id, actor_profile_id=actor_profile_id)
        return [self._approach_item(record) for record in await self.store.list_approaches(problem_id)]

    async def update_approach(self, approach_id: int, patch: DoctorApproachUpdate, source: SourceGateway,
                              actor_profile_id: int) -> DoctorApproachItem:
        record = await self.store.get_approach(approach_id)
        if record is None:
            raise HTTPException(404, "Không tìm thấy hướng giải")
        await source.get_problem(record.problem_id, actor_profile_id=actor_profile_id)
        fields = patch.model_dump(exclude_none=True)
        if "name" in fields or "summary" in fields:
            fields["card_origin"] = "teacher"
        if patch.is_canonical:
            fields["status"] = fields.get("status", "approved")
            await self.store.clear_canonical(record.problem_id, approach_id)
        if fields.get("status") == "rejected":
            fields["is_canonical"] = False
        fields["reviewed_by"] = actor_profile_id
        updated = await self.store.update_approach(approach_id, **fields)
        return self._approach_item(updated)

    async def submit_feedback(self, submission_id: int, body: DoctorFeedbackRequest, source: SourceGateway,
                              actor_profile_id: int) -> dict:
        submission = await source.get_submission(
            submission_id, actor_profile_id=actor_profile_id, include_source=True, include_testcases=True,
        )
        problem = await source.get_problem(submission.problem_id, actor_profile_id=actor_profile_id)
        fingerprint = self._input_fingerprint(submission, problem)
        await self.store.add_feedback(submission_id, fingerprint, actor_profile_id, body.rating,
                                      clean_text(body.note) if body.note else None)
        return {"submission_id": submission_id, "rating": body.rating}

    @staticmethod
    def _approach_item(record) -> DoctorApproachItem:
        return DoctorApproachItem(
            approach_id=record.id, problem_id=record.problem_id, language=record.language, name=record.name,
            summary=record.summary, key_ideas=record.key_ideas, pitfalls=record.pitfalls,
            time_complexity=record.time_complexity, control_flow=record.control_flow, techniques=record.techniques,
            member_count=record.member_count, representative_submission_id=record.representative_submission_id,
            status=record.status, is_canonical=record.is_canonical, card_origin=record.card_origin,
        )

    # ------------------------------------------------------------------ unchanged read helpers

    @staticmethod
    async def get_failed_submissions(
        user_id: int, source: SourceGateway, actor_profile_id: int, limit: int = 10,
    ) -> List[FailedSubmissionItem]:
        """List recent failures; provider filters both verdict and source availability before paging."""
        page = await source.list_student_submissions(
            user_id, actor_profile_id=actor_profile_id, exclude_result="AC",
            only_with_source=True, limit=limit, sort="desc",
        )
        return [FailedSubmissionItem(
            submission_id=item.submission_id, problem_id=item.problem_id,
            problem_code=item.problem_code or f"P{item.problem_id}",
            problem_name=item.problem_title or f"Bài {item.problem_id}",
            result=item.result or item.status or "FAILED", status=item.status,
            date=item.submitted_at.strftime("%d/%m/%Y %H:%M") if item.submitted_at else None,
            points=item.points or 0.0, language_id=item.language_id,
        ) for item in page.items]

    @staticmethod
    async def get_submission_detail(
        submission_id: int, source: SourceGateway, actor_profile_id: int,
    ) -> SubmissionDetailResponse:
        """Lấy chi tiết đầy đủ của bài nộp: đề bài, mã nguồn, thông tin test cases."""
        submission = await source.get_submission(
            submission_id, actor_profile_id=actor_profile_id, include_source=True, include_testcases=True,
        )
        problem = await source.get_problem(submission.problem_id, actor_profile_id=actor_profile_id)
        testcase_items = [
            TestCaseDetailItem(case=tc.case, status=tc.status, time=tc.time, memory=tc.memory, points=tc.points,
                               total=tc.total, feedback=tc.feedback, output=tc.output)
            for tc in submission.testcases
        ]
        return SubmissionDetailResponse(
            submission_id=submission_id, user_id=submission.profile_id, problem_id=submission.problem_id,
            problem_code=problem.code or f"P{submission.problem_id}",
            problem_name=problem.title or problem.name or "Bài toán",
            problem_description=problem.description or "", time_limit=problem.time_limit or 1.0,
            memory_limit=problem.memory_limit or 256, problem_points=problem.points or 100.0,
            result=submission.result or "FAILED", status=submission.status,
            date=submission.submitted_at.strftime("%d/%m/%Y %H:%M:%S") if submission.submitted_at else None,
            time=submission.time, memory=submission.memory, points=submission.points or 0.0,
            language_name=(submission.language.name or submission.language.common_name or "C++")
                if submission.language else "C++",
            source_code=submission.source_code or "// Không có mã nguồn lưu trữ",
            testcases=testcase_items,
        )


code_doctor_service = CodeDoctorService()
