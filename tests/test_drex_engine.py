#!/usr/bin/env python3
"""
test_drex_engine.py
Unit tests for the Drex Non-Generative Micro-Decision Engine.
Verifies single-pass option scoring, ADR constraint rejection, and latency benchmarks.
"""

import unittest
import time
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from compiler.middleend.drex_engine import DrexDecisionEngine, CompilerState, TypedOption

class TestDrexEngine(unittest.TestCase):
    def setUp(self):
        self.drex = DrexDecisionEngine(offline_mode=True)
        self.state = CompilerState(
            module_name="Security.TokenStore",
            target_lang="cpp",
            adr_constraints={"latency_budget": "< 5ms", "memory_limit": "< 32MB"},
            latency_budget_ms=5.0,
            memory_limit_mb=32.0,
            optimization_goal="speed"
        )

    def test_single_pass_scoring(self):
        options = [
            TypedOption("opt_speed", "opt_level", ["-O3", "-march=native"], 0.7, 16.0),
            TypedOption("opt_size", "opt_level", ["-Os"], 1.5, 4.0),
            TypedOption("opt_balanced", "opt_level", ["-O2"], 0.9, 8.0)
        ]
        res = self.drex.evaluate(self.state, options)
        self.assertTrue(res.adr_compliant)
        self.assertEqual(res.selected_option.option_id, "opt_speed")
        self.assertGreater(res.confidence, 0.3)
        self.assertIn("opt_speed", res.score_distribution)
        self.assertLess(res.decision_latency_ms, 5.0) # Sub-5ms single pass latency

    def test_adr_boundary_enforcement(self):
        # Option exceeding 32MB ADR memory limit
        options = [
            TypedOption("opt_heavy", "opt_level", ["-O3", "-fprofile-generate"], 0.5, 64.0), # 64MB > 32MB limit
            TypedOption("opt_compliant", "opt_level", ["-O2"], 0.9, 12.0)
        ]
        res = self.drex.evaluate(self.state, options)
        self.assertTrue(res.adr_compliant)
        # Must NOT select opt_heavy because it breaches ADR memory bounds!
        self.assertEqual(res.selected_option.option_id, "opt_compliant")
        self.assertNotIn("opt_heavy", res.score_distribution)

    def test_throughput_benchmark(self):
        # Benchmark ~25 decisions/second requirement from spec
        options = [
            TypedOption("opt_1", "test", ["-f1"], 0.8, 10.0),
            TypedOption("opt_2", "test", ["-f2"], 1.0, 5.0)
        ]
        n_iterations = 100
        t0 = time.perf_counter()
        for _ in range(n_iterations):
            self.drex.evaluate(self.state, options)
        elapsed = time.perf_counter() - t0
        decisions_per_sec = n_iterations / elapsed
        self.assertGreater(decisions_per_sec, 25.0, f"Drex should achieve >25 decisions/s, got {decisions_per_sec:.1f}")

if __name__ == "__main__":
    unittest.main()
