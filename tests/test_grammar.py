#!/usr/bin/env python3
"""
test_grammar.py
Comprehensive test suite verifying syntax defects, operator precedence,
canonical string round-tripping, locations, and error recovery in AgentLang.
"""

import os
import sys
import unittest
import subprocess
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSER_BIN = os.path.join(REPO_ROOT, "bin", "agentc-parser")

class TestAgentLangGrammar(unittest.TestCase):
    def run_parser(self, code: str):
        res = subprocess.run([PARSER_BIN, "-"], input=code, capture_output=True, text=True)
        ast = json.loads(res.stdout) if res.returncode == 0 and res.stdout.strip() else None
        return res.returncode, ast, res.stderr

    def test_s1_implies_precedence(self):
        """Verify S1: 'a and b implies c' binds as (a and b) implies c."""
        code = "module M; contract C { fn f(a: bool, b: bool, c: bool) -> bool { post: a and b implies c; } }"
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse failed: {err}")
        fn = ast["contracts"][0]["functions"][0]
        # Canonical string should reflect precedence
        self.assertIn("implies", fn["postconditions"][0])
        # AST should have root 'implies' with left 'and'
        post_ast = fn["postconditions_ast"][0]
        self.assertEqual(post_ast["kind"], "binary")
        self.assertEqual(post_ast["op"], "implies")
        self.assertEqual(post_ast["args"][0]["kind"], "binary")
        self.assertEqual(post_ast["args"][0]["op"], "and")
        self.assertEqual(post_ast["args"][1]["kind"], "ident")
        self.assertEqual(post_ast["args"][1]["value"], "c")

    def test_s2_chained_comparisons_rejected(self):
        """Verify S2: '0 < x < 10' is rejected with a syntax error."""
        code = "module M; contract C { fn f(x: i64) -> bool { pre: 0 < x < 10; } }"
        rc, ast, err = self.run_parser(code)
        self.assertNotEqual(rc, 0)
        self.assertIn("syntax error", err.lower())

    def test_s3_unary_minus(self):
        """Verify S3: Unary minus in 'pre: x > -1;' parses correctly."""
        code = "module M; contract C { fn f(x: i64) -> i64 { pre: x > -1; } }"
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse failed: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["preconditions"], ["x > -1"])
        pre_ast = fn["preconditions_ast"][0]
        self.assertEqual(pre_ast["op"], ">")
        right = pre_ast["args"][1]
        self.assertEqual(right["kind"], "unary")
        self.assertEqual(right["op"], "-")

    def test_s4_modulo_operator(self):
        """Verify S4: '%' modulo operator is supported."""
        code = "module M; contract C { fn f(x: i64) -> bool { pre: x % 2 == 0; } }"
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse failed: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["preconditions"], ["x % 2 == 0"])
        pre_ast = fn["preconditions_ast"][0]
        self.assertEqual(pre_ast["op"], "==")
        self.assertEqual(pre_ast["args"][0]["op"], "%")

    def test_s5_call_args_preserved(self):
        """Verify S5: Function call arguments in expressions are preserved."""
        code = "module M; contract C { fn f(x: i64) -> i64 { post: result == max(x, 0); } }"
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse failed: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["postconditions"], ["result == max(x, 0)"])
        call_ast = fn["postconditions_ast"][0]["args"][1]
        self.assertEqual(call_ast["kind"], "call")
        # callee + 2 arguments = 3 args
        self.assertEqual(len(call_ast["args"]), 3)
        self.assertEqual(call_ast["args"][0]["value"], "max")
        self.assertEqual(call_ast["args"][1]["value"], "x")
        self.assertEqual(call_ast["args"][2]["value"], "0")

    def test_s6_string_escape_roundtrip(self):
        """Verify S6: String literal escapes (e.g. \"a\\\"b\") are preserved."""
        code = 'module M; contract C { fn f(s: string) -> bool { pre: s != "a\\"b"; } }'
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse failed: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["preconditions"], ['s != "a\\"b"'])

    def test_s7_unterminated_comment(self):
        """Verify S7: Unterminated /* comment block at EOF is rejected."""
        code = "module M; contract C { fn f() -> i64; } /* never closed"
        rc, ast, err = self.run_parser(code)
        self.assertNotEqual(rc, 0)
        self.assertIn("unterminated comment block", err.lower())

    def test_s8_start_source_locations(self):
        """Verify S8: Source locations point to the start of definitions."""
        code = "module M;\n\ncontract C {\n   fn f(x: i64) -> i64 { pre: x > 0; }\n}"
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse failed: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["loc"]["line"], 4)
        self.assertEqual(fn["loc"]["column"], 4)

    def test_s9_error_recovery_multiple_diagnostics(self):
        """Verify S9: Error recovery reports multiple errors in a single pass."""
        code = "module M;\ncontract C {\n fn f( -> i64;\n fn g( -> i64;\n}"
        rc, ast, err = self.run_parser(code)
        self.assertNotEqual(rc, 0)
        self.assertTrue(":3:" in err, f"Expected line 3 error in: {err}")
        self.assertTrue(":4:" in err, f"Expected line 4 error in: {err}")
        self.assertIn("2 syntax error", err.lower())

    def test_s14_stdin_dash_support(self):
        """Verify S14: Parser accepts '-' as source file for stdin."""
        code = "module StdinMod; contract TestContract { fn test() -> void; }"
        res = subprocess.run([PARSER_BIN, "-"], input=code, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        ast = json.loads(res.stdout)
        self.assertEqual(ast["module_name"], "StdinMod")

    def test_lifecycle_name_preserved(self):
        """Verify lifecycle identifier (e.g. 'sdlc') is preserved in AST."""
        code = "module M; lifecycle sdlc { verify: [unit_tests]; }"
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0)
        self.assertEqual(ast["lifecycles"][0]["name"], "sdlc")

if __name__ == "__main__":
    unittest.main()
