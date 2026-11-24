import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.core.llm_adapter import doctor_profile, strip_reasoning
from app.schemas.ai import CodeDoctorDiagnosis, CodeDoctorResponse
from app.schemas.code_doctor import (
    DoctorApproachUpdate, DoctorFeedbackRequest, DoctorLLMOutput, DoctorReportData, LLMFinding, LLMLogicError,
)
from app.services.code_doctor.matching import Candidate, best_known, cluster, direction, match, rank, same_approach
from app.services.code_doctor.program_model import build_program_model
from app.services.code_doctor.static_facts import collect_facts, extract_constraints
from app.services.code_doctor.store import MemoryDoctorStore
from app.services.code_doctor.validator import apply_model_output
from app.services.code_doctor_service import CodeDoctorService, MEMORY_CACHE_MAX_ITEMS
from app.services.source_gateway import SourceAcceptedSample, SourceAcceptedSamplesResponse, SourceTestcase

PREFIX_AC = """#include <bits/stdc++.h>
using namespace std;
long long a[200005], pre[200005];
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int n, q; cin >> n >> q;
    for (int i = 1; i <= n; i++) { cin >> a[i]; pre[i] = pre[i - 1] + a[i]; }
    while (q--) { int l, r; cin >> l >> r; cout << pre[r] - pre[l - 1] << '\\n'; }
}
"""
PREFIX_WA = """#include <bits/stdc++.h>
using namespace std;
long long a[200005], s[200005];
int main() {
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int n, q; cin >> n >> q;
    for (int i = 1; i <= n; i++) { cin >> a[i]; s[i] = s[i - 1] + a[i]; }
    while (q--) { int l, r; cin >> l >> r; cout << s[r] - s[l] << '\\n'; }
}
"""
BRUTE_TLE = """#include <bits/stdc++.h>
using namespace std;
int a[200005];
int main() {
    int n, q; cin >> n >> q;
    for (int i = 1; i <= n; i++) cin >> a[i];
    while (q--) { int l, r; cin >> l >> r; int t = 0; for (int i = l; i <= r; i++) t += a[i]; cout << t << '\\n'; }
}
"""
STATEMENT = "Cho dãy n số (1 ≤ n ≤ 2*10^5), |a_i| ≤ 10^9 và q truy vấn tính tổng đoạn [l, r]."


def output(**overrides):
    base = dict(
        overview="Bài dùng mảng cộng dồn nhưng trừ sai chỉ số đầu đoạn.", direction="on_track",
        time_complexity="O(n + q)",
        strengths=[LLMFinding(point="Đọc nhanh và dùng long long", lines=[5, 3])],
        weaknesses=[],
        logic_errors=[LLMLogicError(lines=[8], what="s[r] - s[l]", why="Mất phần tử a[l]", fix="Dùng s[r] - s[l - 1]"),
                      LLMLogicError(lines=[999], what="không tồn tại", why="", fix="")],
        student_hints=["Xem lại công thức tổng đoạn", "Dòng 8", "Trừ s[l - 1]"], confidence="high",
    )
    base.update(overrides)
    return DoctorLLMOutput(**base)


class Gateway:
    """Source API double: one submission, one problem, configurable AC samples."""

    def __init__(self, code=PREFIX_WA, result="WA", samples=((101, PREFIX_AC),)):
        self.submission = SimpleNamespace(
            submission_id=1, profile_id=2, problem_id=3, language_id=4, result=result, status="D", points=0,
            time=0.1, memory=1024, submitted_at=None, updated_at=None, version="1", source_code=code,
            language=SimpleNamespace(name="C++17", common_name="C++", key="CPP17"),
            testcases=[SourceTestcase(case=1, status="AC"), SourceTestcase(case=2, status="WA", feedback="Sai")],
        )
        self.samples = list(samples)
        self.allowed = True
        self.sample_calls = 0

    async def get_submission(self, submission_id, *, actor_profile_id, include_source, include_testcases):
        if not self.allowed:
            raise HTTPException(403, "scope denied")
        if submission_id == self.submission.submission_id:
            return self.submission
        for sid, code in self.samples:
            if sid == submission_id:
                return SimpleNamespace(source_code=code, language=SimpleNamespace(key="CPP17"))
        raise HTTPException(404, "not found")

    async def get_problem(self, problem_id, *, actor_profile_id):
        return SimpleNamespace(problem_id=3, name="Tổng đoạn", title="Tổng đoạn", code="sum", description=STATEMENT,
                               time_limit=1, memory_limit=262144, points=100, version=1, updated_at=None)

    async def get_problem_accepted_samples(self, problem_id, *, actor_profile_id, limit):
        self.sample_calls += 1
        now = datetime.now(timezone.utc)
        return SourceAcceptedSamplesResponse(items=[
            SourceAcceptedSample(submission_id=sid, language_key="CPP17", source_code=code, submitted_at=now)
            for sid, code in self.samples[:limit]], as_of=now)


def service():
    return CodeDoctorService(store=MemoryDoctorStore())


def analysis_call(llm):
    """The report call; a background approach-card call may come after it."""
    return next(call for call in llm.call_args_list if call.kwargs["response_model"] is DoctorLLMOutput).kwargs


class ProgramModelTests(unittest.TestCase):
    def test_clara_control_flow_keeps_only_loops(self):
        ac, wa, brute = (build_program_model(c, "CPP17") for c in (PREFIX_AC, PREFIX_WA, BRUTE_TLE))
        self.assertEqual(ac.cf_signature, "E[L()L()]")
        self.assertEqual(ac.cf_signature, wa.cf_signature)
        self.assertEqual(brute.cf_signature, "E[L()L(L())]")
        self.assertEqual(brute.complexity()[1], "O(n^2)")
        self.assertIn("algo:prefix-sum", ac.features)

    def test_identifier_renaming_does_not_change_tokens(self):
        renamed = PREFIX_AC.replace("pre", "sum_prefix").replace("a[", "arr[").replace("long long arr", "long long arr")
        self.assertEqual(build_program_model(renamed, "CPP17").tokens, build_program_model(PREFIX_AC, "CPP17").tokens)

    def test_python_model_and_recursion(self):
        code = "import sys\ndef go(n):\n    return 0 if n == 0 else go(n - 1)\nfor i in range(3):\n    for j in range(3):\n        print(go(i))\n"
        model = build_program_model(code, "PY3")
        self.assertTrue(model.parse_ok)
        self.assertTrue(model.recursive)
        self.assertEqual(model.max_loop_depth, 2)

    def test_unknown_language_still_returns_model(self):
        model = build_program_model("begin writeln(1) end.", "PAS")
        self.assertFalse(model.parse_ok)
        self.assertEqual(model.cf_signature, "?")


class MatchingTests(unittest.TestCase):
    def test_clustering_groups_equivalent_correct_programs(self):
        renamed = PREFIX_AC.replace("pre", "ps")
        models = [build_program_model(c, "CPP17") for c in (PREFIX_AC, BRUTE_TLE, renamed)]
        self.assertEqual(cluster(models), [[0, 2], [1]])
        self.assertTrue(same_approach(models[0], models[2]))

    def test_rank_prefers_cheapest_repair_with_same_control_flow(self):
        wa = build_program_model(PREFIX_WA, "CPP17")
        candidates = [Candidate(0, build_program_model(BRUTE_TLE, "CPP17"), "cpp"),
                      Candidate(1, build_program_model(PREFIX_AC, "CPP17"), "cpp")]
        ranked = rank(wa, candidates)
        self.assertEqual(ranked[0].key, 1)
        self.assertTrue(ranked[0].same_control_flow)
        self.assertLess(ranked[0].cost, ranked[1].cost)
        self.assertEqual(direction(ranked[0]), "on_track")
        self.assertEqual(best_known(candidates).key, 1)

    def test_rejected_approach_is_ignored_and_canonical_wins(self):
        brute, prefix = build_program_model(BRUTE_TLE, "CPP17"), build_program_model(PREFIX_AC, "CPP17")
        candidates = [Candidate(0, prefix, "cpp", status="rejected"), Candidate(1, brute, "cpp", is_canonical=True)]
        self.assertEqual([r.key for r in rank(prefix, candidates)], [1])
        self.assertEqual(best_known(candidates).key, 1)

    def test_static_facts_flag_quadratic_loop_and_overflow(self):
        constraints = extract_constraints(STATEMENT)
        self.assertEqual(constraints.n_max, 200000)
        texts = " ".join(f.text for f in collect_facts(build_program_model(BRUTE_TLE, "CPP17"), constraints, 1))
        self.assertIn("n^2", texts)
        self.assertIn("64-bit", texts)
        self.assertIn("sync_with_stdio", texts)
        safe = " ".join(f.text for f in collect_facts(build_program_model(PREFIX_AC, "CPP17"), constraints, 1))
        self.assertNotIn("64-bit", safe)


class ValidatorTests(unittest.TestCase):
    def report(self, verdict="WA"):
        return DoctorReportData(verdict=verdict, origin="ai", overview="")

    def test_logic_error_without_real_line_is_dropped(self):
        report = apply_model_output(self.report(), output(), line_count=9, risk_lines=set())
        self.assertEqual([e.lines for e in report.logic_errors], [[8]])
        self.assertEqual(report.strengths[0].lines, [3, 5])
        self.assertTrue(any("Đã bỏ 1" in item for item in report.limitations))
        self.assertEqual(report.confidence, "medium")  # no nearest approach caps confidence

    def test_ac_logic_errors_become_untested_risks(self):
        report = apply_model_output(self.report("AC"), output(), line_count=9, risk_lines=set())
        self.assertEqual(report.logic_errors, [])
        self.assertIn("Rủi ro chưa bị test phát hiện", report.weaknesses[0].point)

    def test_failed_submission_without_located_error_is_low_confidence(self):
        report = apply_model_output(self.report(), output(logic_errors=[]), line_count=9, risk_lines=set())
        self.assertEqual(report.confidence, "low")


class LLMProfileTests(unittest.TestCase):
    def test_doctor_settings_inherit_and_override(self):
        with patch.object(settings, "DOCTOR_LLM_MODEL", ""), patch.object(settings, "LLM_MODEL", "base-model"):
            self.assertEqual(doctor_profile().model, "base-model")
        with patch.object(settings, "DOCTOR_LLM_MODEL", "strong-model"), \
                patch.object(settings, "DOCTOR_LLM_CONTEXT_WINDOW", 32768):
            profile = doctor_profile()
        self.assertEqual((profile.model, profile.context_window), ("strong-model", 32768))

    def test_inline_reasoning_is_removed(self):
        self.assertEqual(strip_reasoning("<think>a { b }</think>\n{\"x\": 1}"), '{"x": 1}')
        self.assertEqual(strip_reasoning("<think>never closed"), "")


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_scope_is_checked_before_cache(self):
        source = SimpleNamespace(get_submission=AsyncMock(side_effect=HTTPException(403, "scope denied")))
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value="{}")) as cache:
            with self.assertRaises(HTTPException):
                await service().diagnose_submission_async(41, source, 9)
        cache.assert_not_awaited()
        source.get_submission.assert_awaited_once_with(41, actor_profile_id=9, include_source=True, include_testcases=True)

    async def test_worker_uses_shared_gateway_client(self):
        doctor = service()
        expected = SimpleNamespace(model_dump=lambda mode=None: {"ok": True})
        with patch("app.services.code_doctor_service.get_source_gateway_client", return_value=Gateway()), \
                patch.object(doctor, "_diagnose_submission_core", new=AsyncMock(return_value=expected)) as diagnose:
            self.assertEqual(await doctor._execute_diagnose(41, 9), {"ok": True})
        self.assertEqual(diagnose.await_args.args[0], 41)

    async def test_worker_rechecks_scope_after_enqueue(self):
        doctor, source = service(), Gateway()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value=None)), \
                patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock(return_value=("job1", True))) as enqueue, \
                patch("app.services.code_doctor_service.get_source_gateway_client", return_value=source):
            response = await doctor.diagnose_submission_async(1, source, 9)
            self.assertEqual(response.job_id, "job1")
            args = enqueue.await_args.args
            self.assertEqual(args[2:], (1, 9))
            source.allowed = False
            with self.assertRaises(HTTPException):
                await args[1](*args[2:])

    async def test_cache_key_changes_with_inputs_and_hides_source(self):
        doctor, source = service(), Gateway()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value=None)), \
                patch("app.services.code_doctor_service.job_manager.enqueue_job",
                      new=AsyncMock(side_effect=[("job1", True), ("job2", True)])) as enqueue:
            await doctor.diagnose_submission_async(1, source, 9)
            source.submission.source_code = PREFIX_AC
            await doctor.diagnose_submission_async(1, source, 9)
        first, second = (call.kwargs["entity_key"] for call in enqueue.await_args_list)
        self.assertNotEqual(first, second)
        self.assertNotIn("pre[", second)

    async def test_accepted_submission_is_analysed_not_short_circuited(self):
        source = Gateway(code=PREFIX_AC, result="AC", samples=((101, BRUTE_TLE),))
        with patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock(return_value=("j", True))) as enqueue, \
                patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value=None)):
            response = await service().diagnose_submission_async(1, source, 2)
        self.assertEqual(response.status.value, "PENDING")
        enqueue.assert_awaited_once()

    async def test_non_diagnosable_verdicts_do_not_enqueue(self):
        for result, status, category in (("SC", "D", "SC"), ("WA", "P", "PENDING"), ("WA", "IE", "IE"), (None, "D", "PENDING")):
            with self.subTest(result=result, status=status):
                source = Gateway()
                source.submission.result, source.submission.status = result, status
                with patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock()) as enqueue:
                    response = await service().diagnose_submission_async(1, source, 2)
                self.assertEqual(response.result["diagnosis"]["origin"], "verdict")
                self.assertEqual(response.result["diagnosis"]["error_category"], category)
                enqueue.assert_not_awaited()

    async def test_memory_cache_is_bounded_lru(self):
        doctor = service()
        response = CodeDoctorResponse(submission_id=1, user_id=2, problem_name="P",
                                      diagnosis=CodeDoctorDiagnosis(error_category="WA", advice="x"))
        for index in range(MEMORY_CACHE_MAX_ITEMS):
            doctor._store_memory_cache(f"key-{index}", response)
        doctor._get_memory_cache("key-0")
        doctor._store_memory_cache("new-key", response)
        self.assertEqual(len(doctor._memory_cache), MEMORY_CACHE_MAX_ITEMS)
        self.assertIn("key-0", doctor._memory_cache)
        self.assertNotIn("key-1", doctor._memory_cache)

    async def test_wa_report_uses_reference_and_validated_model_output(self):
        doctor, source = service(), Gateway()
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(return_value=output())) as llm, \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()) as cache:
            response = await doctor._diagnose_submission_core(1, source, 2)
        prompt = analysis_call(llm)["prompt"]
        self.assertIn("MÃ THAM CHIẾU AC, hướng giải gần nhất", prompt)
        self.assertIn("pre[r] - pre[l - 1]", prompt)
        self.assertIn("s[r] - s[l]", prompt)
        self.assertIn("Đạt 1/2 test", prompt)
        self.assertIn("TRỌNG TÂM: Bài sai kết quả", prompt)
        report = response.report
        self.assertEqual(report.origin, "ai")
        self.assertEqual(report.nearest_approach.name.split(" (")[0], "Mảng cộng dồn")
        self.assertTrue(report.nearest_approach.same_control_flow)
        self.assertEqual([e.lines for e in report.logic_errors], [[8]])
        self.assertEqual(report.logic_errors[0].evidence, "reference_diff")
        self.assertEqual(cache.call_args.kwargs["expire"], 7 * 86400)
        self.assertEqual(response.diagnosis.advice, report.overview)
        stored = doctor.store.reports[1]
        self.assertEqual(stored["origin"], "ai")
        self.assertNotIn("pre[r]", str(await doctor.store.list_approaches(3)))

    async def test_model_failure_gives_static_report_with_reason(self):
        doctor, source = service(), Gateway(code=BRUTE_TLE, result="TLE")
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(side_effect=TimeoutError)), \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()) as cache:
            response = await doctor._diagnose_submission_core(1, source, 2)
        report = response.report
        self.assertEqual(report.origin, "fallback")
        self.assertIn("giây", report.fallback_reason)
        self.assertEqual(response.diagnosis.fallback_reason, report.fallback_reason)
        self.assertEqual(cache.call_args.kwargs["expire"], 300)
        self.assertTrue(any("n^2" in w.point for w in report.weaknesses))
        self.assertEqual(report.direction, "partially")  # different loop structure from the prefix-sum AC

    async def test_cancelled_diagnosis_does_not_write_cache(self):
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(side_effect=asyncio.CancelledError)), \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()) as cache:
            with self.assertRaises(asyncio.CancelledError):
                await service()._diagnose_submission_core(1, Gateway(), 2)
        cache.assert_not_awaited()

    async def test_ac_compares_with_faster_approach_and_joins_bank(self):
        doctor = service()
        source = Gateway(code=BRUTE_TLE, result="AC", samples=((101, PREFIX_AC),))
        source.submission.testcases = [SourceTestcase(case=1, status="AC")]
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured",
                   new=AsyncMock(return_value=output(logic_errors=[], direction="partially"))) as llm, \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()):
            response = await doctor._diagnose_submission_core(1, source, 2)
        self.assertIn("hướng giải tốt nhất", analysis_call(llm)["prompt"])
        self.assertIn("TRỌNG TÂM: Bài đã AC", analysis_call(llm)["prompt"])
        self.assertEqual(response.report.best_approach.time_complexity, "O(n)")
        approaches = await doctor.store.list_approaches(3)
        self.assertEqual(len(approaches), 2)  # the brute-force AC opened a second approach
        self.assertIn(1, await doctor.store.member_ids(3))

    async def test_approach_card_is_written_after_ai_report(self):
        from app.schemas.code_doctor import ApproachCard
        doctor, source = service(), Gateway()
        card = ApproachCard(name="Mảng cộng dồn", summary="Tính trước tổng tiền tố rồi trả lời mỗi truy vấn O(1).",
                            key_ideas=["pre[i] = pre[i-1] + a[i]"], time_complexity="O(n + q)", pitfalls=["Trừ pre[l]"])

        async def fake(response_model, **kwargs):
            return card if response_model is ApproachCard else output()

        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(side_effect=fake)), \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()):
            await doctor._diagnose_submission_core(1, source, 2)
            await asyncio.gather(*doctor._card_tasks.values())
        (approach,) = await doctor.store.list_approaches(3)
        self.assertEqual((approach.card_origin, approach.time_complexity), ("ai", "O(n + q)"))
        self.assertIn("tổng tiền tố", approach.summary)

    async def test_equivalent_samples_share_one_approach(self):
        doctor = service()
        source = Gateway(samples=((101, PREFIX_AC), (102, PREFIX_AC.replace("pre", "ps"))))
        view = await doctor.bank.view(3, source, 2)
        self.assertEqual(len(view.entries), 1)
        self.assertEqual(view.entries[0].record.member_count, 2)
        again = await doctor.bank.view(3, source, 2)
        self.assertEqual(again.entries[0].record.member_count, 2)

    async def test_no_samples_is_reported_as_limitation(self):
        doctor, source = service(), Gateway(samples=())
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(return_value=output())) as llm, \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()):
            response = await doctor._diagnose_submission_core(1, source, 2)
        self.assertIn("CHƯA CÓ LỜI GIẢI AC THAM CHIẾU", analysis_call(llm)["prompt"])
        self.assertIsNone(response.report.nearest_approach)
        self.assertEqual(response.report.logic_errors[0].evidence, "model")

    async def test_local_ollama_thinking_disabled_with_doctor_profile(self):
        with patch.object(settings, "LLM_BASE_URL", "http://ollama:11434/v1"), \
                patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(return_value=output())) as llm, \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()):
            await service()._diagnose_submission_core(1, Gateway(), 2)
        kwargs = analysis_call(llm)
        self.assertEqual(kwargs["reasoning_effort"], "none")
        self.assertEqual(kwargs["max_tokens"], settings.DOCTOR_LLM_MAX_TOKENS)
        self.assertEqual(kwargs["profile"].base_url, "http://ollama:11434/v1")

    async def test_comments_are_not_sent_and_source_is_unchanged(self):
        raw = "/*" + "DECORATION" * 300 + "*/\n" + PREFIX_WA
        source = Gateway(code=raw)
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(return_value=output())) as llm, \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()):
            await service()._diagnose_submission_core(1, source, 2)
        self.assertNotIn("DECORATION", analysis_call(llm)["prompt"])
        self.assertIn("DECORATION", source.submission.source_code)

    async def test_stored_ai_report_is_served_after_cache_expiry(self):
        doctor, source = service(), Gateway()
        with patch("app.services.code_doctor_service.llm_adapter.generate_structured", new=AsyncMock(return_value=output())), \
                patch("app.services.code_doctor_service.cache_set", new=AsyncMock()):
            await doctor._diagnose_submission_core(1, source, 2)
        doctor._memory_cache.clear()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value=None)), \
                patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock()) as enqueue:
            response = await doctor.diagnose_submission_async(1, source, 2)
        enqueue.assert_not_awaited()
        self.assertEqual(response.result["report"]["origin"], "ai")

    async def test_teacher_review_and_feedback(self):
        doctor, source = service(), Gateway(samples=((101, PREFIX_AC), (102, BRUTE_TLE)))
        await doctor.bank.view(3, source, 2)
        first, second = await doctor.list_approaches(3, source, 2)
        await doctor.update_approach(first.approach_id, DoctorApproachUpdate(is_canonical=True), source, 7)
        updated = await doctor.update_approach(second.approach_id,
                                               DoctorApproachUpdate(is_canonical=True, name="Duyệt trâu"), source, 7)
        items = {item.approach_id: item for item in await doctor.list_approaches(3, source, 2)}
        self.assertFalse(items[first.approach_id].is_canonical)
        self.assertTrue(updated.is_canonical)
        self.assertEqual((updated.status, updated.card_origin, updated.name), ("approved", "teacher", "Duyệt trâu"))
        with self.assertRaises(HTTPException):
            await doctor.update_approach(999, DoctorApproachUpdate(status="rejected"), source, 7)
        await doctor.submit_feedback(1, DoctorFeedbackRequest(rating="partial", note="Đúng dòng, sai lý do"), source, 7)
        self.assertEqual(doctor.store.feedback[0]["rating"], "partial")


try:
    import aiosqlite  # noqa: F401
except ImportError:  # optional test dependency
    aiosqlite = None


@unittest.skipIf(aiosqlite is None, "aiosqlite is not installed")
class SqlStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_sql_store_round_trip(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from app.core.dashboard_database import DashboardBase
        import app.models.dashboard  # noqa: F401
        from app.services.code_doctor.store import ApproachRecord, MemberRecord, SqlDoctorStore
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as connection:
            await connection.run_sync(DashboardBase.metadata.create_all)
        store = SqlDoctorStore(async_sessionmaker(engine, expire_on_commit=False))
        record = await store.create_approach(
            ApproachRecord(None, 3, "cpp", "Mảng cộng dồn", "E[L()L()]", ["algo:prefix-sum"], 1.0, 101),
            MemberRecord(0, 101, 3, "CPP17", "h"))
        await store.add_member(MemberRecord(record.id, 102, 3, "CPP17", "h2", 4))
        await store.add_member(MemberRecord(record.id, 102, 3, "CPP17", "h2", 4))
        self.assertEqual((await store.get_approach(record.id)).member_count, 2)
        self.assertEqual(await store.member_ids(3), {101, 102})
        await store.save_report(1, "fp", 3, record.id, "WA", "ai", "m", "v", {"origin": "ai"})
        await store.save_report(1, "fp2", 3, record.id, "WA", "ai", "m", "v", {"origin": "ai", "x": 1})
        self.assertIsNone(await store.get_report(1, "fp"))
        self.assertEqual((await store.get_report(1, "fp2"))["x"], 1)
        await store.add_feedback(1, "fp2", 7, "correct", None)
        await engine.dispose()
