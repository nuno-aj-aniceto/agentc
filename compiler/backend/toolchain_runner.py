#!/usr/bin/env python3
"""
toolchain_runner.py
Native toolchain runner for CMake/Make (C++) and Maven/Make/Javac (Java).
Supports seamless builds with or without CMake/Maven and verifies test execution.
"""

import os
import subprocess
import time
from typing import Dict, Any, Tuple

class ToolchainRunner:
    def __init__(self, work_dir: str):
        self.work_dir = os.path.abspath(work_dir)

    def run_cpp(self, contract_name: str, use_cmake: bool = True) -> Dict[str, Any]:
        """Runs CMake configure, build, and test runner, or standalone Makefile."""
        start_time = time.time()
        logs = []

        if use_cmake and os.path.exists(os.path.join(self.work_dir, "CMakeLists.txt")):
            # 1. CMake configure
            cfg_cmd = ["cmake", "-B", "build", "-S", "."]
            cfg_res = subprocess.run(cfg_cmd, cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== CMake Configure ===\n{cfg_res.stdout}\n{cfg_res.stderr}")
            if cfg_res.returncode != 0:
                return {
                    "success": False,
                    "stage": "cmake_configure",
                    "returncode": cfg_res.returncode,
                    "logs": "\n".join(logs),
                    "duration_seconds": round(time.time() - start_time, 3)
                }

            # 2. CMake build
            build_cmd = ["cmake", "--build", "build", "-j4"]
            build_res = subprocess.run(build_cmd, cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== CMake Build ===\n{build_res.stdout}\n{build_res.stderr}")
            if build_res.returncode != 0:
                return {
                    "success": False,
                    "stage": "cmake_build",
                    "returncode": build_res.returncode,
                    "logs": "\n".join(logs),
                    "duration_seconds": round(time.time() - start_time, 3)
                }

            # 3. Test execution
            test_exe = os.path.join(self.work_dir, "build", f"{contract_name}_test")
            test_res = subprocess.run([test_exe], cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== Test Execution ===\n{test_res.stdout}\n{test_res.stderr}")

            return {
                "success": (test_res.returncode == 0),
                "stage": "test_execution",
                "returncode": test_res.returncode,
                "logs": "\n".join(logs),
                "test_output": test_res.stdout,
                "duration_seconds": round(time.time() - start_time, 3)
            }
        else:
            # Standalone Makefile build
            make_res = subprocess.run(["make", "all", "test"], cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== Make Build and Test ===\n{make_res.stdout}\n{make_res.stderr}")
            return {
                "success": (make_res.returncode == 0),
                "stage": "make_test",
                "returncode": make_res.returncode,
                "logs": "\n".join(logs),
                "test_output": make_res.stdout,
                "duration_seconds": round(time.time() - start_time, 3)
            }

    def run_java(self, contract_name: str, pkg: str, use_mvn: bool = False) -> Dict[str, Any]:
        """Runs Maven test or direct Javac compilation and CLI verification."""
        start_time = time.time()
        logs = []

        if use_mvn and os.path.exists(os.path.join(self.work_dir, "pom.xml")):
            mvn_cmd = ["mvn", "clean", "test"]
            res = subprocess.run(mvn_cmd, cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== Maven Clean Test ===\n{res.stdout}\n{res.stderr}")
            return {
                "success": (res.returncode == 0),
                "stage": "maven_test",
                "returncode": res.returncode,
                "logs": "\n".join(logs),
                "duration_seconds": round(time.time() - start_time, 3)
            }
        else:
            # Standalone Javac & Make compilation
            out_dir = os.path.join(self.work_dir, "target", "classes")
            os.makedirs(out_dir, exist_ok=True)
            
            pkg_path = pkg.replace(".", "/")
            src_file = os.path.join(self.work_dir, "src", "main", "java", pkg_path, f"{contract_name}.java")
            cli_file = os.path.join(self.work_dir, "src", "main", "java", pkg_path, f"{contract_name}Cli.java")
            
            srcs = [src_file]
            if os.path.exists(cli_file):
                srcs.append(cli_file)

            javac_cmd = ["javac", "-d", out_dir] + srcs
            javac_res = subprocess.run(javac_cmd, cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== Javac Compile ===\n{javac_res.stdout}\n{javac_res.stderr}")
            if javac_res.returncode != 0:
                return {
                    "success": False,
                    "stage": "javac_compile",
                    "returncode": javac_res.returncode,
                    "logs": "\n".join(logs),
                    "duration_seconds": round(time.time() - start_time, 3)
                }

            # Run CLI contract selftest
            cli_class = f"{pkg}.{contract_name}Cli"
            java_cmd = ["java", "-cp", out_dir, cli_class, "selftest"]
            java_res = subprocess.run(java_cmd, cwd=self.work_dir, capture_output=True, text=True)
            logs.append(f"=== CLI Contract Selftest ===\n{java_res.stdout}\n{java_res.stderr}")

            return {
                "success": (java_res.returncode == 0),
                "stage": "cli_selftest",
                "returncode": java_res.returncode,
                "logs": "\n".join(logs),
                "duration_seconds": round(time.time() - start_time, 3)
            }
