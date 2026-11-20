#!/usr/bin/env python3
"""
test_sema.py
Test suite for the AgentLang Semantic Analyzer (sema.py).
"""

import os
import sys
import unittest
import subprocess
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSER_BIN = os.path.join(REPO_ROOT, "bin", "agentc-parser")
sys.path.insert(0, REPO_ROOT)

from compiler.middleend.sema import SemanticAnalyzer

class TestSemanticAnalyzer(unittest.TestCase):
    def parse_and_analyze(self, code: str):
        res = subprocess.run([PARSER_BIN, "-"], input=code, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Parser error:\n{res.stderr}")
        ast = json.loads(res.stdout)
        analyzer = SemanticAnalyzer("<test>")
        return analyzer.analyze(ast)

    def test_e001_undefined_identifier(self):
        code = "module M; contract C { fn f(x: i64) -> i64 { pre: y > 0; } }"
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E001", codes)
        self.assertTrue(any("undefined identifier 'y'" in d.message.lower() for d in res.diagnostics))

    def test_e002_undefined_type(self):
        code = "module M; contract C { fn f(x: Nonexistent) -> Bogus; }"
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E002", codes)

    def test_e003_duplicate_function(self):
        code = "module M; contract C { fn f() -> i64; fn f() -> bool; }"
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E003", codes)

    def test_e004_result_in_precondition(self):
        code = "module M; contract C { fn f(x: i64) -> i64 { pre: result > 0; } }"
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E004", codes)

    def test_e006_type_mismatch(self):
        code = 'module M; contract C { fn f(s: string) -> i64 { pre: s + 1 > 0; } }'
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E006", codes)

    def test_e007_orphan_agent(self):
        code = 'module M; agent implementation for Ghost { intent: "x"; }'
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E007", codes)

    def test_e008_unsupported_target(self):
        code = "module M; target rust { toolchain: cargo; }"
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E008", codes)

    def test_w101_float_equality_warning(self):
        code = "module M; contract C { fn f(a: f64, b: f64) -> bool { post: result == (a == b); } }"
        res = self.parse_and_analyze(code)
        # Should succeed because warning is non-fatal
        self.assertTrue(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("W101", codes)

    def test_example_math_service_passes_sema(self):
        math_file = os.path.join(REPO_ROOT, "examples", "01_math_service.afl")
        res = subprocess.run([PARSER_BIN, math_file], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        ast = json.loads(res.stdout)
        analyzer = SemanticAnalyzer(math_file)
        result = analyzer.analyze(ast)
        self.assertTrue(result.success, f"MathService sema failed: {[d.message for d in result.diagnostics if d.severity == 'error']}")

    def test_example_token_service_passes_sema(self):
        token_file = os.path.join(REPO_ROOT, "examples", "02_token_service.afl")
        res = subprocess.run([PARSER_BIN, token_file], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        ast = json.loads(res.stdout)
        analyzer = SemanticAnalyzer(token_file)
        result = analyzer.analyze(ast)
        self.assertTrue(result.success, f"TokenService sema failed: {[d.message for d in result.diagnostics if d.severity == 'error']}")

if __name__ == "__main__":
    unittest.main()
