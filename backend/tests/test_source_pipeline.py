import unittest
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.services.source_cleaner import prepare_source
from app.services.source_context import build_source_context
from app.services.auto_tag_service import AutoTagService
from app.schemas.ai import AutoTagResult
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
        from app.services.code_doctor_service import CodeDoctorService
        self.assertNotEqual(CodeDoctorService._cache_key(1), 'tmath:code_doctor:submission:1')


class MemoryUnitTests(unittest.TestCase):
    def test_judge_memory_in_kb_is_reported_in_mb(self):
        from app.services.code_doctor_service import kb_to_mb
        self.assertEqual(kb_to_mb(262144), "256")
        self.assertEqual(kb_to_mb(28000), "27.3")
        self.assertEqual(kb_to_mb(1024), "1")
