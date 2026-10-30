import unittest
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.services.source_cleaner import prepare_source
from app.services.source_context import build_source_context
from app.services.code_doctor_service import CodeDoctorService, MEMORY_CACHE_MAX_ITEMS
from app.services.auto_tag_service import AutoTagService
from app.schemas.ai import AutoTagResult, CodeDoctorDiagnosis, CodeDoctorResponse
from app.services.competency_evaluator import analyze_source_code
from app.services.tag_ai_service import TagAIService
from app.schemas.analytics import AICommentaryResponse, Recent7DaysSummary
from app.api.v1.endpoints.student import get_student_ai_commentary
from app.services.source_gateway import SourceProblem, SourceAcceptedSample, SourceAcceptedSamplesResponse, SourceTestcase


class ContextTests(unittest.TestCase):
    def test_full_source_keeps_tail_and_original_lines(self):
        prepared = prepare_source('/*' + 'art' * 2000 + '*/\nint main(){return 42;}\n', 'CPP17')
        result = build_source_context(prepared, 'system', 'base', 8192, 450)
        self.assertTrue(result.is_complete)
        self.assertIn('L2: int main(){return 42;}', result.text)
        self.assertNotIn('artart', result.text)

    def test_budget_omits_whole_units_and_labels_partial(self):
        source = 'void helper(){\n' + 'int x=0;\n' * 1000 + '}\nint main(){return 0;}\n'
        result = build_source_context(prepare_source(source, 'CPP17'), '', '', 1500, 100)
        self.assertFalse(result.is_complete)
        self.assertIn('int main()', result.text)
        self.assertNotIn('void helper()', result.text)
        self.assertLessEqual(result.estimated_tokens + 100 + 512, 1500)

    def test_unknown_language_pass_through(self):
        result = build_source_context(prepare_source('hello // literal', 'unknown'), '', '', 8192, 450)
        self.assertIn('hello // literal', result.text)

    def test_comment_cannot_add_competency_bonus(self):
        code = '/* sync_with_stdio vector<int> void solve(){} */\nint main(){return 0;}\n'
        self.assertGreater(analyze_source_code(code)[0], 0)
        self.assertEqual(analyze_source_code(prepare_source(code, 'CPP17').analysis_source)[0], 0)

    def test_literal_with_unterminated_quote_is_passed_through(self):
        code = 'const char *s = "// text\nint main(){}\n'
        prepared = prepare_source(code, 'CPP17')
        self.assertEqual(prepared.analysis_source, code)
        self.assertTrue(prepared.warnings)

    def test_unicode_separators_inside_literal_are_not_code_lines(self):
        literal = 'a\u2028' * 10
        prepared = prepare_source('const char *s = "' + literal + '";\nint main(){}\n', 'CPP17')
        self.assertEqual(prepared.line_map, (1, 2))
        self.assertIn(literal, build_source_context(prepared, '', '', 8192, 450).text)

    def test_no_unit_fits_does_not_send_empty_code_excerpt(self):
        code = 'int main(){\n' + 'int x=0;\n' * 1000 + '}\n'
        context = build_source_context(prepare_source(code, 'CPP17'), '', '', 1500, 100)
        self.assertFalse(context.is_complete)
        self.assertEqual(context.text, '')

    def test_decorator_stays_with_python_unit(self):
        code = '@decorate(\n    "parameter"\n)\ndef main():\n    return 7\n'
        prepared = prepare_source(code, 'PY3')
        self.assertEqual(prepared.units[0].start_line, 1)
        self.assertEqual(prepared.units[0].end_line, 5)


class DoctorGateway:
    def __init__(self, source_code='int main(){return 7;}'):
        self.source_code = source_code
        self.submission = SimpleNamespace(
            submission_id=1, profile_id=2, problem_id=3, language_id=4,
            result='WA', status='D', points=0, time=0, memory=0,
            submitted_at=None, updated_at=None, version='1', source_code=source_code,
            language=SimpleNamespace(name='C++17', common_name='C++', key='CPP17'),
            testcases=[],
        )
        self.allowed = True

    async def get_submission(self, submission_id, *, actor_profile_id, include_source, include_testcases):
        if not self.allowed:
            raise HTTPException(403, "scope denied")
        return self.submission

    async def get_problem(self, problem_id, *, actor_profile_id):
        return SimpleNamespace(
            problem_id=3, name='P', title='P', code='p', description='',
            time_limit=1, memory_limit=256, points=100, version=1, updated_at=None,
        )


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_commentary_cache_read_does_not_generate(self):
        service = TagAIService()
        cached = AICommentaryResponse(
            commentary='Đã lưu.',
            recent_7days_summary=Recent7DaysSummary(),
            recommended_tags=[],
            generated_at='2026-10-10T00:00:00Z',
        )
        with patch('app.services.tag_ai_service.cache_get', new=AsyncMock(return_value=cached.model_dump_json())):
            result = await service.get_cached_daily_ai_commentary(12)
        self.assertEqual(result, cached)

    async def test_ai_commentary_endpoint_generates_only_when_requested(self):
        source = SimpleNamespace(get_student=AsyncMock())
        actor = SimpleNamespace(profile_id=9)
        with patch('app.api.v1.endpoints.student.tag_ai_service.get_cached_daily_ai_commentary', new=AsyncMock(return_value=None)) as read_cache, patch('app.api.v1.endpoints.student.tag_ai_service.get_daily_ai_commentary', new=AsyncMock()) as generate:
            await get_student_ai_commentary(user_id=12, time_range='all', force_refresh=False,
                                           source=source, actor=actor)
        read_cache.assert_awaited_once_with(12, time_range='all')
        generate.assert_not_awaited()
        source.get_student.assert_awaited_once_with(12, actor_profile_id=9)

    async def test_code_doctor_checks_source_and_testcase_scope_before_cache(self):
        source = SimpleNamespace(get_submission=AsyncMock(side_effect=HTTPException(403, "scope denied")))
        service = CodeDoctorService()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value='{}')) as cache:
            with self.assertRaises(HTTPException) as caught:
                await service.diagnose_submission_async(41, source, 9)
        self.assertEqual(caught.exception.status_code, 403)
        cache.assert_not_awaited()
        source.get_submission.assert_awaited_once_with(
            41, actor_profile_id=9, include_source=True, include_testcases=True,
        )

    async def test_code_doctor_worker_uses_shared_gateway_client(self):
        service = CodeDoctorService()
        source = DoctorGateway()
        expected = SimpleNamespace(model_dump=lambda: {"ok": True})
        with patch("app.services.code_doctor_service.get_source_gateway_client", return_value=source), \
                patch.object(service, "_diagnose_submission_core", new=AsyncMock(return_value=expected)) as diagnose:
            result = await service._execute_diagnose(41, 9)
        self.assertEqual(result, {"ok": True})
        diagnose.assert_awaited_once_with(41, source, 9)

    async def test_code_doctor_worker_rechecks_scope_after_enqueue_without_source_payload(self):
        service = CodeDoctorService()
        source = DoctorGateway()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value=None)), \
                patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock(return_value=("job1", True))) as enqueue, \
                patch("app.services.code_doctor_service.get_source_gateway_client", return_value=source):
            response = await service.diagnose_submission_async(1, source, 9)
            self.assertEqual(response.job_id, "job1")
            args = enqueue.await_args.args
            self.assertEqual(args[2:], (1, 9))
            source.allowed = False
            with self.assertRaises(HTTPException) as caught:
                await args[1](*args[2:])
        self.assertEqual(caught.exception.status_code, 403)

    async def test_code_doctor_cache_key_changes_when_submission_inputs_change(self):
        service = CodeDoctorService()
        source = DoctorGateway()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock(return_value=None)), \
                patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock(side_effect=[("job1", True), ("job2", True)])) as enqueue:
            await service.diagnose_submission_async(1, source, 9)
            first_key = enqueue.await_args_list[0].kwargs["entity_key"]
            source.submission.result = "TLE"
            source.submission.source_code = "int main(){return 9;}"
            await service.diagnose_submission_async(1, source, 9)
        second_key = enqueue.await_args_list[1].kwargs["entity_key"]
        self.assertNotEqual(first_key, second_key)
        self.assertNotIn(source.submission.source_code, second_key)

    async def test_accepted_submission_returns_verdict_without_model_or_cache(self):
        source = DoctorGateway()
        source.submission.result = "AC"
        service = CodeDoctorService()
        with patch("app.services.code_doctor_service.cache_get", new=AsyncMock()) as cache, \
                patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock()) as enqueue, \
                patch("app.services.code_doctor_service.llm_adapter.generate_text", new=AsyncMock()) as llm:
            response = await service.diagnose_submission_async(1, source, 2, force_refresh=True)
            direct = await service._diagnose_submission_core(1, source, 2)
        self.assertEqual(response.status.value, "COMPLETED")
        self.assertEqual(response.result["diagnosis"]["origin"], "verdict")
        self.assertEqual(response.result["diagnosis"]["error_category"], "AC")
        self.assertIn("đã đạt AC", response.result["diagnosis"]["advice"])
        self.assertEqual(direct.diagnosis.origin, "verdict")
        cache.assert_not_awaited()
        enqueue.assert_not_awaited()
        llm.assert_not_awaited()

    async def test_non_diagnosable_verdicts_do_not_call_model(self):
        for result, status, category in (("SC", "D", "SC"), ("WA", "P", "PENDING"),
                                         ("WA", "IE", "IE"), (None, "D", "PENDING")):
            with self.subTest(result=result, status=status):
                source = DoctorGateway()
                source.submission.result = result
                source.submission.status = status
                with patch("app.services.code_doctor_service.job_manager.enqueue_job", new=AsyncMock()) as enqueue:
                    response = await CodeDoctorService().diagnose_submission_async(1, source, 2)
                self.assertEqual(response.result["diagnosis"]["origin"], "verdict")
                self.assertEqual(response.result["diagnosis"]["error_category"], category)
                enqueue.assert_not_awaited()

    async def test_code_doctor_memory_fallback_is_bounded_lru(self):
        service = CodeDoctorService()
        response = CodeDoctorResponse(
            submission_id=1, user_id=2, problem_name="P",
            diagnosis=CodeDoctorDiagnosis(error_category="WA", advice="Lỗi đáp án."),
        )
        for index in range(MEMORY_CACHE_MAX_ITEMS):
            service._store_memory_cache(f"key-{index}", response)
        service._get_memory_cache("key-0")  # retain the oldest entry by touching it
        service._store_memory_cache("new-key", response)
        self.assertEqual(len(service._memory_cache), MEMORY_CACHE_MAX_ITEMS)
        self.assertIn("key-0", service._memory_cache)
        self.assertNotIn("key-1", service._memory_cache)
        self.assertIn("new-key", service._memory_cache)

    async def test_fallback_is_short_lived_and_not_kept_in_memory(self):
        service = CodeDoctorService()
        source = DoctorGateway()
        problem = await source.get_problem(3, actor_profile_id=2)
        cache_key = service._cache_key(1, service._input_fingerprint(source.submission, problem))
        service._memory_cache[cache_key] = 'stale result'
        with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(side_effect=TimeoutError)), patch('app.services.code_doctor_service.cache_set', new=AsyncMock()) as cache:
            response = await service._diagnose_submission_core(1, source, 2)
        self.assertEqual(cache.call_args.kwargs['expire'], 300)
        self.assertNotIn(cache_key, service._memory_cache)
        self.assertEqual(response.diagnosis.origin, 'fallback')
        self.assertIn('Chưa xác định', response.diagnosis.advice)

    async def test_cancelled_diagnosis_does_not_write_cache(self):
        with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(side_effect=asyncio.CancelledError)), patch('app.services.code_doctor_service.cache_set', new=AsyncMock()) as cache:
            with self.assertRaises(asyncio.CancelledError):
                await CodeDoctorService()._diagnose_submission_core(1, DoctorGateway(), 2)
        cache.assert_not_awaited()

    async def test_success_has_long_cache(self):
        service = CodeDoctorService()
        source = DoctorGateway()
        problem = await source.get_problem(3, actor_profile_id=2)
        cache_key = service._cache_key(1, service._input_fingerprint(source.submission, problem))
        with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(return_value='Hàm main trả về 7 nên kết quả không đúng với đề bài.')), patch('app.services.code_doctor_service.cache_set', new=AsyncMock()) as cache:
            response = await service._diagnose_submission_core(1, source, 2)
        self.assertEqual(cache.call_args.kwargs['expire'], 7 * 86400)
        self.assertIn(cache_key, service._memory_cache)
        self.assertEqual(response.diagnosis.origin, 'ai')

    async def test_verdict_specific_prompt_reaches_model(self):
        for verdict, expected_focus in (("WA", "Đối chiếu logic"), ("TLE", "độ phức tạp"),
                                        ("RTE", "vị trí có thể gây lỗi"), ("CE", "thông báo biên dịch"),
                                        ("MLE", "cấp phát bộ nhớ"), ("OLE", "quá nhiều đầu ra")):
            with self.subTest(verdict=verdict):
                source = DoctorGateway()
                source.submission.result = verdict
                with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(return_value='Mã nguồn cần kiểm tra ở hàm main theo phản hồi chấm.')) as llm, \
                        patch('app.services.code_doctor_service.cache_set', new=AsyncMock()):
                    response = await CodeDoctorService()._diagnose_submission_core(1, source, 2)
                self.assertIn(expected_focus, llm.call_args.kwargs['prompt'])
                self.assertEqual(response.diagnosis.origin, 'ai')

    async def test_doctor_includes_failure_after_first_fifteen_cases(self):
        source = DoctorGateway()
        source.submission.testcases = [SourceTestcase(case=index, status='AC') for index in range(1, 17)]
        source.submission.testcases.append(SourceTestcase(case=17, status='WA', feedback='Sai kết quả'))
        with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(return_value='Cần kiểm tra nhánh trả về trong hàm main.')) as llm, \
                patch('app.services.code_doctor_service.cache_set', new=AsyncMock()):
            await CodeDoctorService()._diagnose_submission_core(1, source, 2)
        prompt = llm.call_args.kwargs['prompt']
        self.assertIn('16/17', prompt)
        self.assertIn('Test #17 [WA]', prompt)

    async def test_code_doctor_disables_local_ollama_thinking(self):
        with patch('app.services.code_doctor_service.settings.LLM_BASE_URL', 'http://ollama:11434/v1'), \
                patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(return_value='Hàm main trả về 7 nên kết quả không đúng với đề bài.')) as llm, \
                patch('app.services.code_doctor_service.cache_set', new=AsyncMock()):
            await CodeDoctorService()._diagnose_submission_core(1, DoctorGateway(), 2)
        self.assertEqual(llm.call_args.kwargs['reasoning_effort'], 'none')
        self.assertGreater(llm.call_args.kwargs['timeout_seconds'], 90)
    async def test_doctor_sends_clean_tail_and_does_not_modify_source(self):
        raw = '/*' + 'DECORATION' * 700 + '*/\nint main(){return 7;}\n'
        source = DoctorGateway(raw)
        with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(return_value='Hàm main trả về 7 nên kết quả không đúng với đề bài.')) as llm, patch('app.services.code_doctor_service.cache_set', new=AsyncMock()):
            response = await CodeDoctorService()._diagnose_submission_core(1, source, 2)
        prompt = llm.call_args.kwargs['prompt']
        self.assertIn('return 7', prompt)
        self.assertNotIn('DECORATION', prompt)
        self.assertIn('DECORATION', raw)
        self.assertEqual(response.submission_id, 1)

    async def test_auto_tag_uses_clean_source_and_true_language(self):
        raw = '# DECORATION\nprint(123)\n'
        class AcceptedGateway:
            async def get_problem_accepted_samples(self, problem_id, *, actor_profile_id, limit):
                self.request = (problem_id, actor_profile_id, limit)
                return SourceAcceptedSamplesResponse(items=[SourceAcceptedSample(
                    submission_id=10, language_key='PY3', source_code=raw, submitted_at=datetime.now(timezone.utc),
                )], as_of=datetime.now(timezone.utc))
        gateway = AcceptedGateway()
        problem = SourceProblem(problem_id=1, title=None, code='p', description='', time_limit=1, memory_limit=256000)
        tag = AutoTagResult(problem_id=1, primary_tag_id=1, secondary_tag_ids=[], bloom_group_id=4, reasoning='test')
        with patch('app.services.auto_tag_service.llm_adapter.generate_structured', new=AsyncMock(return_value=tag)) as llm:
            await AutoTagService().tag_problem(problem, gateway, actor_profile_id=2)
        prompt = llm.call_args.kwargs['prompt']
        self.assertIn('Python 3', prompt)
        self.assertIn('print(123)', prompt)
        self.assertNotIn('DECORATION', prompt)
        self.assertEqual(gateway.request, (1, 2, 1))

    def test_cache_policy_does_not_reuse_legacy_key(self):
        self.assertNotEqual(CodeDoctorService._cache_key(1), 'tmath:code_doctor:submission:1')
