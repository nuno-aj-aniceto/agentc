#!/usr/bin/env python3
"""
test_build_systems.py
Verifies standalone Makefile and CMake compilation workflows.
Ensures agentc can build and test with or without CMake.
"""

import os
import unittest
import subprocess
from compiler.backend.cpp_emitter import CppEmitter
from compiler.backend.java_emitter import JavaEmitter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class TestBuildSystems(unittest.TestCase):
    def test_root_makefile_builds_parser_directly(self):
        """Verifies root Makefile builds bin/agentc-parser with GNU Make directly."""
        res = subprocess.run(["make", "BUILD_SYSTEM=make", "parser-make"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"make parser-make failed:\n{res.stderr}")
        parser_bin = os.path.join(REPO_ROOT, "bin", "agentc-parser")
        self.assertTrue(os.path.exists(parser_bin))

    def test_generated_cpp_makefile_structure(self):
        """Verifies generated C++ Makefile includes all required targets."""
        makefile = CppEmitter.generate_makefile(
            "Demo.Module", ["ContractA", "ContractB"], {"standard": "c++20"}
        )
        self.assertIn("all: libContractA.a libContractB.a ContractA_test ContractB_test ContractA_cli ContractB_cli", makefile)
        self.assertIn("lib: libContractA.a libContractB.a", makefile)
        self.assertIn("tests: ContractA_test ContractB_test", makefile)
        self.assertIn("cli: ContractA_cli ContractB_cli", makefile)
        self.assertIn("test: ContractA_test ContractB_test", makefile)
        self.assertIn("install: all", makefile)
        self.assertIn("clean:", makefile)

    def test_generated_java_makefile_structure(self):
        """Verifies generated Java Makefile builds without Maven."""
        makefile = JavaEmitter.generate_makefile(
            "Demo.Module", ["ContractA"], {"package": "com.demo"}
        )
        self.assertIn("all: jar", makefile)
        self.assertIn("classes:", makefile)
        self.assertIn("$(JAVAC)", makefile)
        self.assertIn("$(JAR) --create", makefile)
        self.assertIn("test: classes", makefile)
        self.assertIn("clean:", makefile)

if __name__ == "__main__":
    unittest.main()
