#!/usr/bin/env python3
"""
test_wave2_features.py
Comprehensive test suite verifying Wave 2 AgentLang specifications:
1. Explicit Traceability Directives (traces: [...])
2. Stateful Contracts & State Machines (state machine / transition: S1 -> S2)
3. Temporal Invariants & old() Postcondition Expressions
4. Dimensioned Unit Literals (500ms, 64MB)
"""

import os
import sys
import unittest
import subprocess
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSER_BIN = os.path.join(REPO_ROOT, "bin", "agentc-parser")
AGENTC_BIN = os.path.join(REPO_ROOT, "bin", "agentc")
sys.path.insert(0, REPO_ROOT)

from compiler.middleend.sema import SemanticAnalyzer
from compiler.backend.expr_lowering import ExprLowerer

class TestWave2Grammar(unittest.TestCase):
    def run_parser(self, code: str):
        res = subprocess.run([PARSER_BIN, "-"], input=code, capture_output=True, text=True)
        ast = json.loads(res.stdout) if res.returncode == 0 and res.stdout.strip() else None
        return res.returncode, ast, res.stderr

    def test_trace_directives_parsing(self):
        code = """
        module M;
        artifact prd "PRD-001" { feature: "F"; acceptance: "A"; }
        contract C {
            traces: [PRD-001, PRD-001.SUB, "SEC-AUDIT-99"];
            fn run() -> bool {
                traces: [PRD-001.SUB];
                post: result == true;
            }
        }
        """
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse error: {err}")
        contract = ast["contracts"][0]
        self.assertEqual(contract["traces"], ["PRD-001", "PRD-001.SUB", "SEC-AUDIT-99"])
        fn = contract["functions"][0]
        self.assertEqual(fn["traces"], ["PRD-001.SUB"])

    def test_state_machine_and_transitions_parsing(self):
        code = """
        module M;
        contract Lifecycle {
            state machine StatusFlow {
                initial: Pending;
                transitions: [
                    Pending -> Active,
                    Active -> Closed
                ];
            }
            fn activate() -> bool {
                transition: Pending -> Active;
                post: result == true;
            }
        }
        """
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse error: {err}")
        contract = ast["contracts"][0]
        self.assertEqual(len(contract["state_machines"]), 1)
        sm = contract["state_machines"][0]
        self.assertEqual(sm["name"], "StatusFlow")
        self.assertEqual(sm["initial_state"], "Pending")
        self.assertEqual(len(sm["transitions"]), 2)
        self.assertEqual(sm["transitions"][0]["from"], "Pending")
        self.assertEqual(sm["transitions"][0]["to"], "Active")
        self.assertEqual(sm["transitions"][1]["from"], "Active")
        self.assertEqual(sm["transitions"][1]["to"], "Closed")

        fn = contract["functions"][0]
        self.assertEqual(fn["transition"]["from"], "Pending")
        self.assertEqual(fn["transition"]["to"], "Active")

    def test_unit_literals_parsing(self):
        code = """
        module M;
        contract ResourceGuard {
            fn check_limits(latency: u64, ram: u64) -> bool {
                pre: latency < 500ms;
                pre: ram <= 64MB;
                post: result == true;
            }
        }
        """
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse error: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["preconditions"], ["latency < 500ms", "ram <= 64MB"])
        pre1 = fn["preconditions_ast"][0]["args"][1]
        self.assertEqual(pre1["kind"], "unit")
        self.assertEqual(pre1["value"], "500")
        self.assertEqual(pre1["unit"], "ms")

        pre2 = fn["preconditions_ast"][1]["args"][1]
        self.assertEqual(pre2["kind"], "unit")
        self.assertEqual(pre2["value"], "64")
        self.assertEqual(pre2["unit"], "MB")

    def test_old_expression_parsing(self):
        code = """
        module M;
        contract Bank {
            fn withdraw(balance: u64, amount: u64) -> u64 {
                pre: balance >= amount;
                post: result == old(balance) - amount;
            }
        }
        """
        rc, ast, err = self.run_parser(code)
        self.assertEqual(rc, 0, f"Parse error: {err}")
        fn = ast["contracts"][0]["functions"][0]
        self.assertEqual(fn["postconditions"], ["result == old(balance) - amount"])
        post_ast = fn["postconditions_ast"][0]
        old_node = post_ast["args"][1]["args"][0]
        self.assertEqual(old_node["kind"], "call")
        self.assertEqual(old_node["args"][0]["value"], "old")
        self.assertEqual(old_node["args"][1]["value"], "balance")


class TestWave2Sema(unittest.TestCase):
    def parse_and_analyze(self, code: str):
        res = subprocess.run([PARSER_BIN, "-"], input=code, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Parser error:\n{res.stderr}")
        ast = json.loads(res.stdout)
        analyzer = SemanticAnalyzer("<test>")
        return analyzer.analyze(ast)

    def test_e009_invalid_trace_reference(self):
        code = """
        module M;
        artifact prd "PRD-REAL" { feature: "F"; acceptance: "A"; }
        contract C {
            traces: [PRD-UNKNOWN];
        }
        """
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E009", codes)

    def test_e010_undeclared_state_in_state_machine(self):
        code = """
        module M;
        contract C {
            enum State { S1, S2 };
            state machine Flow {
                initial: UnknownState;
                transitions: [ S1 -> S2 ];
            }
        }
        """
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E010", codes)

    def test_e011_function_transition_not_in_contract_state_machine(self):
        code = """
        module M;
        contract C {
            enum State { S1, S2, S3 };
            state machine Flow {
                initial: S1;
                transitions: [ S1 -> S2 ];
            }
            fn jump() -> bool {
                transition: S1 -> S3;
                post: result == true;
            }
        }
        """
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E011", codes)

    def test_e012_old_expression_in_precondition(self):
        code = """
        module M;
        contract C {
            fn step(x: i64) -> i64 {
                pre: old(x) > 0;
            }
        }
        """
        res = self.parse_and_analyze(code)
        self.assertFalse(res.success)
        codes = [d.code for d in res.diagnostics]
        self.assertIn("E012", codes)


class TestWave2Lowering(unittest.TestCase):
    def test_unit_literal_lowering_cpp_and_java(self):
        expr_time = {"kind": "unit", "value": "500", "unit": "ms"}
        expr_bytes = {"kind": "unit", "value": "64", "unit": "MB"}

        cpp_time = ExprLowerer.lower(expr_time, "cpp")
        java_time = ExprLowerer.lower(expr_time, "java")
        self.assertEqual(cpp_time, "500")
        self.assertEqual(java_time, "500")

        cpp_bytes = ExprLowerer.lower(expr_bytes, "cpp")
        java_bytes = ExprLowerer.lower(expr_bytes, "java")
        self.assertEqual(cpp_bytes, "(64 * 1024 * 1024ULL)")
        self.assertEqual(java_bytes, "(64 * 1024L * 1024L)")

    def test_old_expression_lowering(self):
        expr_old = {
            "kind": "call",
            "args": [
                {"kind": "ident", "value": "old"},
                {"kind": "ident", "value": "balance"}
            ]
        }
        cpp_out = ExprLowerer.lower(expr_old, "cpp", {"balance": "u64"})
        java_out = ExprLowerer.lower(expr_old, "java", {"balance": "u64"})
        self.assertEqual(cpp_out, "_old_balance")
        self.assertEqual(java_out, "_old_balance")


class TestWave2EndToEnd(unittest.TestCase):
    def setUp(self):
        self.order_afl = os.path.join(REPO_ROOT, "examples", "03_order_service.afl")

    def test_cpp_order_service_build(self):
        cmd = [AGENTC_BIN, "build", self.order_afl, "--target", "cpp", "--build-system", "make", "--force"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"C++ build failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("Verification PASSED for 'OrderService'", res.stdout)

    def test_java_order_service_build(self):
        cmd = [AGENTC_BIN, "build", self.order_afl, "--target", "java", "--force"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Java build failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("Verification PASSED for 'OrderService'", res.stdout)

    def test_cpp_order_service_runtime_state_and_timeout(self):
        cli_bin = os.path.join(REPO_ROOT, ".agentc", "build", "cpp", "OrderService_cli")
        self.assertTrue(os.path.exists(cli_bin), "OrderService_cli binary not found")

        # Selftest
        res = subprocess.run([cli_bin, "selftest"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Selftest failed:\n{res.stdout}\n{res.stderr}")

        # Invalid state transition: Created -> Fulfilled should throw error
        res_trans = subprocess.run([cli_bin, "fulfillOrder", "ord_fail", "100"], capture_output=True, text=True)
        self.assertNotEqual(res_trans.returncode, 0)
        self.assertIn("Invalid state transition", res_trans.stderr)

        # Timeout check: 400ms is < 500ms -> passes
        res_timeout_ok = subprocess.run([cli_bin, "checkTimeout", "400"], capture_output=True, text=True)
        self.assertEqual(res_timeout_ok.returncode, 0)
        self.assertIn('"result": true', res_timeout_ok.stdout)

        # Timeout check: 600ms violates pre: elapsed < 500ms
        res_timeout_fail = subprocess.run([cli_bin, "checkTimeout", "600"], capture_output=True, text=True)
        self.assertNotEqual(res_timeout_fail.returncode, 0)
        self.assertIn("Precondition failed", res_timeout_fail.stderr)

    def test_java_order_service_runtime_state_and_timeout(self):
        classes_dir = os.path.join(REPO_ROOT, ".agentc", "build", "java", "target", "classes")
        self.assertTrue(os.path.exists(classes_dir), "Java classes directory not found")

        # Selftest
        cmd_selftest = ["java", "-cp", classes_dir, "com.examples.order.OrderServiceCli", "selftest"]
        res = subprocess.run(cmd_selftest, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Java selftest failed:\n{res.stdout}\n{res.stderr}")

        # Invalid state transition: Created -> Fulfilled
        cmd_trans = ["java", "-cp", classes_dir, "com.examples.order.OrderServiceCli", "fulfillOrder", "ord_fail", "100"]
        res_trans = subprocess.run(cmd_trans, capture_output=True, text=True)
        self.assertNotEqual(res_trans.returncode, 0)
        self.assertIn("Invalid state transition", res_trans.stderr)

        # Timeout check: 400ms is < 500ms -> passes
        cmd_timeout_ok = ["java", "-cp", classes_dir, "com.examples.order.OrderServiceCli", "checkTimeout", "400"]
        res_timeout_ok = subprocess.run(cmd_timeout_ok, capture_output=True, text=True)
        self.assertEqual(res_timeout_ok.returncode, 0)
        self.assertIn('"result": true', res_timeout_ok.stdout)

        # Timeout check: 600ms violates pre: elapsed < 500ms
        cmd_timeout_fail = ["java", "-cp", classes_dir, "com.examples.order.OrderServiceCli", "checkTimeout", "600"]
        res_timeout_fail = subprocess.run(cmd_timeout_fail, capture_output=True, text=True)
        self.assertNotEqual(res_timeout_fail.returncode, 0)
        self.assertIn("Precondition failed", res_timeout_fail.stderr)

if __name__ == "__main__":
    unittest.main()
