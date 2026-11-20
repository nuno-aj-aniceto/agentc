#!/usr/bin/env python3
"""
auto_healer.py
Closed-loop verification and auto-repair feedback engine for agentc.
Analyzes compiler errors and test failures, synthesizing targeted patches,
and cross-referencing runtime anomalies against PRD acceptance criteria and ADR bounds.
"""

import re
from typing import Dict, Any, List, Optional

class AutoHealer:
    @staticmethod
    def parse_diagnostics(logs: str, language: str) -> List[Dict[str, Any]]:
        """Extracts structured diagnostic errors from compiler and test runner output."""
        diagnostics = []

        if language == "cpp":
            # Match GCC / Clang errors: filename:line:col: error: message
            matches = re.findall(r'([^:\n]+):(\d+):(\d+):\s+error:\s+([^\n]+)', logs)
            for m in matches:
                diagnostics.append({
                    "file": m[0],
                    "line": int(m[1]),
                    "col": int(m[2]),
                    "severity": "error",
                    "message": m[3]
                })

            # Match assertion failures
            assert_matches = re.findall(r'Assertion FAILED:\s+([^\n]+)\s+at line\s+(\d+)', logs)
            for m in assert_matches:
                diagnostics.append({
                    "severity": "test_failure",
                    "assertion": m[0],
                    "line": int(m[1]),
                    "message": f"Test assertion failed: {m[0]}"
                })

        elif language == "java":
            # Match Javac errors: filename:line: error: message
            matches = re.findall(r'([^:\n]+):(\d+):\s+error:\s+([^\n]+)', logs)
            for m in matches:
                diagnostics.append({
                    "file": m[0],
                    "line": int(m[1]),
                    "severity": "error",
                    "message": m[2]
                })

        return diagnostics

    @staticmethod
    def cross_reference_artifacts(diagnostics: List[Dict[str, Any]], 
                                 artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Anomaly Localization: Cross-references execution/compiler failures
        against active PRD acceptance criteria and ADR architectural bounds.
        """
        enriched = []
        for d in diagnostics:
            item = dict(d)
            msg = d.get("message", "").lower()
            breached_artifacts = []

            for a in artifacts:
                atype = a.get("type", "").lower()
                aid = a.get("id", "")
                meta = a.get("metadata", {})
                constraints = a.get("constraints", [])

                # Check if failure matches PRD acceptance criteria or constraints
                if atype == "prd":
                    acceptance = meta.get("acceptance", "").lower()
                    if any(term in msg for term in ["zero", "divide", "token", "bound", "failed"]):
                        breached_artifacts.append({
                            "type": "PRD",
                            "id": aid,
                            "rule": acceptance or "Functional Acceptance Criteria"
                        })
                elif atype == "adr":
                    latency_b = meta.get("latency_budget", "")
                    mem_limit = meta.get("memory_limit", "")
                    if any(term in msg for term in ["timeout", "latency", "memory", "overflow"]):
                        breached_artifacts.append({
                            "type": "ADR",
                            "id": aid,
                            "rule": f"Latency: {latency_b}, Memory: {mem_limit}"
                        })

            item["linked_artifacts"] = breached_artifacts
            enriched.append(item)
        return enriched

    @staticmethod
    def formulate_repair_prompt(diagnostics: List[Dict[str, Any]], original_code: str,
                                artifacts: Optional[List[Dict[str, Any]]] = None) -> str:
        """Formulates an agentic repair prompt explaining exactly what failed and which PRD/ADR bounds were hit."""
        prompt_lines = [
            "The compiler or test suite reported the following failures during verification:",
            ""
        ]
        enriched = AutoHealer.cross_reference_artifacts(diagnostics, artifacts or [])
        for d in enriched:
            if d.get("severity") == "error":
                prompt_lines.append(f"- Compile Error in {d.get('file', 'source')}:{d.get('line', '?')}: {d['message']}")
            else:
                prompt_lines.append(f"- Test Failure: {d['message']}")

            if d.get("linked_artifacts"):
                for la in d["linked_artifacts"]:
                    prompt_lines.append(f"  * Breaches {la['type']} ({la['id']}): {la['rule']}")

        prompt_lines.append("\nPlease revise the implementation to eliminate all compiler errors and strictly satisfy all PRD and ADR invariants.")
        return "\n".join(prompt_lines)
