#!/usr/bin/env python3
"""
test_parser.py
Automated test suite verifying the native Flex/Bison parser for AgentLang (.afl).
"""

import os
import sys
import unittest
import subprocess
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSER_BIN = os.path.join(REPO_ROOT, "bin", "agentc-parser")

class TestAgentcParser(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(PARSER_BIN), f"Parser binary must exist at {PARSER_BIN}")

    def test_parse_math_service(self):
        afl_path = os.path.join(REPO_ROOT, "examples", "01_math_service.afl")
        res = subprocess.run([PARSER_BIN, afl_path], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Parser failed: {res.stderr}")
        
        ast = json.loads(res.stdout)
        self.assertEqual(ast["module_name"], "Examples.MathService")
        self.assertEqual(len(ast["contracts"]), 1)
        
        contract = ast["contracts"][0]
        self.assertEqual(contract["name"], "MathOperations")
        
        fn_names = [f["name"] for f in contract["functions"]]
        self.assertIn("add", fn_names)
        self.assertIn("divide", fn_names)
        self.assertIn("clamp", fn_names)
        self.assertIn("factorial", fn_names)

        # Check pre/post conditions
        divide_fn = next(f for f in contract["functions"] if f["name"] == "divide")
        self.assertEqual(divide_fn["preconditions"], ["denominator != 0"])
        self.assertEqual(divide_fn["postconditions"], ["result * denominator == numerator"])

    def test_parse_token_service(self):
        afl_path = os.path.join(REPO_ROOT, "examples", "02_token_service.afl")
        res = subprocess.run([PARSER_BIN, afl_path], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Parser failed: {res.stderr}")
        
        ast = json.loads(res.stdout)
        self.assertEqual(ast["module_name"], "Security.TokenManager")
        contract = ast["contracts"][0]
        self.assertEqual(contract["name"], "TokenStore")
        
        # Verify enum and struct types
        types = {t["name"]: t for t in contract["types"]}
        self.assertIn("TokenStatus", types)
        self.assertEqual(types["TokenStatus"]["kind"], "enum")
        self.assertEqual(types["TokenStatus"]["variants"], ["Active", "Revoked", "Expired"])

        self.assertIn("TokenMetadata", types)
        self.assertEqual(types["TokenMetadata"]["kind"], "struct")
        field_names = [f["name"] for f in types["TokenMetadata"]["fields"]]
        self.assertIn("userId", field_names)
        self.assertIn("status", field_names)

    def test_parse_artifacts(self):
        afl_path = os.path.join(REPO_ROOT, "examples", "01_math_service.afl")
        res = subprocess.run([PARSER_BIN, afl_path], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        ast = json.loads(res.stdout)
        
        artifacts = {a["type"]: a for a in ast.get("artifacts", [])}
        self.assertIn("prd", artifacts)
        self.assertEqual(artifacts["prd"]["id"], "PRD-MATH-001")
        self.assertIn("Divide by zero must throw", artifacts["prd"]["constraints"][0])

        self.assertIn("adr", artifacts)
        self.assertEqual(artifacts["adr"]["id"], "ADR-0014")
        self.assertEqual(artifacts["adr"]["metadata"]["latency_budget"], "< 1ms")

        self.assertIn("hld", artifacts)
        self.assertEqual(artifacts["hld"]["id"], "HLD-CORE-MATH")

        self.assertIn("lld", artifacts)
        self.assertEqual(artifacts["lld"]["id"], "LLD-ALU-OPS")

    def test_syntax_error_reporting(self):
        # Malformed afl with missing semicolon
        bad_code = "module Broken;\ncontract Foo { fn bar( -> int; }"
        res = subprocess.run([PARSER_BIN, "-"], input=bad_code, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("syntax error", res.stderr.lower())
        self.assertIn("<stdin>:2:", res.stderr)

if __name__ == "__main__":
    unittest.main()
