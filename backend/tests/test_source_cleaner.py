import unittest

from app.services.source_cleaner import SOURCE_POLICY_VERSION, prepare_source


class SourceCleanerTests(unittest.TestCase):
    def test_cpp_masks_comments_without_joining_tokens_and_keeps_literals(self):
        source = '''#include <string> // header note
int/* gap */value = 1; // trailing
const char *url = "https://example.test/a/*b*/";
const char *raw = R"tag(/* literal */ // text)tag";
char quote = 'x'; /* block
comment */
int main() { return value; }
'''
        prepared = prepare_source(source, "cpp17")
        self.assertEqual(prepared.analysis_source.count("\n"), source.count("\n"))
        self.assertIn("int         value", prepared.analysis_source)
        self.assertIn('"https://example.test/a/*b*/"', prepared.analysis_source)
        self.assertIn('R"tag(/* literal */ // text)tag"', prepared.analysis_source)
        self.assertEqual(prepared.removed_comment_count, 4)
        self.assertIn("int main()", prepared.prompt_source)
        self.assertNotIn("header note", prepared.prompt_source)
        self.assertEqual(prepared.policy_version, SOURCE_POLICY_VERSION)
        self.assertTrue(any(unit.is_entry for unit in prepared.units))

    def test_cpp_preserves_multiline_macro_and_spliced_input_is_conservative(self):
        macro = "#define SUM(a, b) \\\n  ((a) + /* retained */ \\\n   (b))\nint main(){return SUM(1, 2);}\n"
        prepared = prepare_source(macro, "c++")
        self.assertIn("/* retained */", prepared.analysis_source)
        self.assertIn("/* retained */", prepared.prompt_source)
        self.assertEqual(prepared.removed_comment_count, 0)

        spliced = "int x; \\\n// continuation\n"
        passed = prepare_source(spliced, "c")
        self.assertEqual(passed.analysis_source, spliced)
        self.assertTrue(passed.warnings)

    def test_python_comments_removed_with_line_map_and_literals_kept(self):
        source = '"""module\n\ntext # literal\n"""\n# drawing\n\ndef f():\n    url = "https://x/#y"  # note\n    return url\n'
        prepared = prepare_source(source, "python3")
        self.assertIn('text # literal', prepared.analysis_source)
        self.assertIn('"https://x/#y"', prepared.analysis_source)
        self.assertNotIn("drawing", prepared.prompt_source)
        self.assertNotIn("note", prepared.prompt_source)
        self.assertIn("\n\ntext # literal\n", prepared.prompt_source)
        self.assertEqual(prepared.line_map, (1, 2, 3, 4, 7, 8, 9))
        self.assertTrue(any(unit.start_line == 7 and unit.is_entry is False for unit in prepared.units))

    def test_python_preserves_indent_and_invalid_source(self):
        source = "def f():\n    # comment\n    return 2\n"
        result = prepare_source(source, "py3")
        self.assertIn("    return 2", result.analysis_source)
        self.assertEqual(result.analysis_source.count("\n"), 3)
        malformed = "def f(:\n    # keep with syntax error\n"
        failed = prepare_source(malformed, "python3")
        self.assertEqual(failed.analysis_source, malformed)
        self.assertTrue(failed.warnings)

    def test_unicode_crlf_and_missing_final_newline_keep_offsets(self):
        source = "x = 1\r\n# ghi chú 🎯\r\ny = x + 1"
        result = prepare_source(source, "python3")
        self.assertEqual(result.analysis_source, "x = 1\r\n           \r\ny = x + 1")
        self.assertEqual(result.prompt_source, "x = 1\r\ny = x + 1")
        self.assertEqual(result.line_map, (1, 3))

    def test_pascal_directives_survive_ordinary_comments_are_masked(self):
        source = "{$mode objfpc}\n{ ordinary note }\nprogram Demo;\nbegin\n  writeln('x'); // trailing\nend.\n"
        result = prepare_source(source, "pascal")
        self.assertIn("{$mode objfpc}", result.analysis_source)
        self.assertNotIn("ordinary note", result.analysis_source)
        self.assertNotIn("trailing", result.prompt_source)
        malformed = "program P; { unfinished\nbegin end.\n"
        passed = prepare_source(malformed, "pascal")
        self.assertEqual(passed.analysis_source, malformed)
        self.assertTrue(passed.warnings)

    def test_python2_lexer_preserves_multiline_string_and_line_map(self):
        source = 's = """first\n\nthird""" # note\n'
        result = prepare_source(source, "python2")
        self.assertIn("\n\nthird", result.prompt_source)
        self.assertNotIn("note", result.prompt_source)
        self.assertEqual(result.line_map, (1, 2, 3))

    def test_unknown_and_oversize_are_pass_through(self):
        source = "x // do not guess\n"
        unknown = prepare_source(source, "rust")
        self.assertEqual(unknown.analysis_source, source)
        self.assertEqual(unknown.line_map, (1,))
        self.assertTrue(unknown.warnings)
        large = prepare_source("x" * (1024 * 1024 + 1), "cpp")
        self.assertEqual(large.analysis_source, "x" * (1024 * 1024 + 1))
        self.assertTrue(any("1 MiB" in warning for warning in large.warnings))

    def test_malformed_c_comment_is_not_erased(self):
        source = "int main() { /* unfinished\n"
        result = prepare_source(source, "c")
        self.assertEqual(result.analysis_source, source)
        self.assertTrue(result.warnings)

    def test_many_comments_keep_unicode_byte_offsets_and_lines(self):
        source = 'int x; // ghi chú\n' * 3000
        result = prepare_source(source, 'CPP17')
        self.assertEqual(result.removed_comment_count, 3000)
        self.assertEqual(result.line_map, tuple(range(1, 3001)))
        self.assertEqual(result.prompt_source, 'int x;\n' * 3000)


if __name__ == "__main__":
    unittest.main()
