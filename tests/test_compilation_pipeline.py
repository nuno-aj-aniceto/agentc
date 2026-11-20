#!/usr/bin/env python3
"""
test_compilation_pipeline.py
End-to-end integration tests for the agentc compilation pipeline across C++ and Java.
"""

import os
import sys
import unittest
import subprocess
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGENTC_BIN = os.path.join(REPO_ROOT, "bin", "agentc")

class TestCompilationPipeline(unittest.TestCase):
    def setUp(self):
        self.math_afl = os.path.join(REPO_ROOT, "examples", "01_math_service.afl")
        self.token_afl = os.path.join(REPO_ROOT, "examples", "02_token_service.afl")

    def test_cpp_compilation_math(self):
        cmd = [AGENTC_BIN, "build", self.math_afl, "--target", "cpp", "--force"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"C++ math build failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        self.assertIn("Verification PASSED for 'MathOperations'", res.stdout)

    def test_java_compilation_math(self):
        cmd = [AGENTC_BIN, "build", self.math_afl, "--target", "java", "--force"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Java math build failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        self.assertIn("Verification PASSED for 'MathOperations'", res.stdout)

    def test_cpp_compilation_token(self):
        cmd = [AGENTC_BIN, "build", self.token_afl, "--target", "cpp", "--force"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"C++ token build failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        self.assertIn("Verification PASSED for 'TokenStore'", res.stdout)

    def test_java_compilation_token(self):
        cmd = [AGENTC_BIN, "build", self.token_afl, "--target", "java", "--force"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Java token build failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        self.assertIn("Verification PASSED for 'TokenStore'", res.stdout)

if __name__ == "__main__":
    unittest.main()
