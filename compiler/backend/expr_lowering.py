#!/usr/bin/env python3
"""
expr_lowering.py
Target-aware Expression Lowerer for AgentLang (agentc).
Lowers typed Expr AST into idiomatic, semantically correct C++20 and Java 21 expressions.
"""

from typing import Dict, Any, Optional
from compiler.backend.node_emitter import NODE_TARGETS

class ExprLowerer:
    @staticmethod
    def lower(expr: Dict[str, Any], target: str, scope: Optional[Dict[str, str]] = None) -> str:
        """Lowers an Expr AST node into target language expression string."""
        lowerer = ExprLowerer(target=target.lower(), scope=scope or {})
        return lowerer._lower_node(expr)

    def __init__(self, target: str, scope: Dict[str, str]):
        self.target = target
        self.scope = scope

    def _lower_node(self, node: Dict[str, Any]) -> str:
        if not node:
            return ""

        kind = node.get("kind", "")
        op = node.get("op", "")
        val = node.get("value", "")
        args = node.get("args", [])

        if kind == "ident":
            return val

        elif kind == "int":
            return val

        elif kind == "float":
            # Ensure float literal has decimal or is double
            if "." not in val:
                return f"{val}.0"
            return val

        elif kind == "string":
            # String literal in target
            escaped = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
            return f'"{escaped}"'

        elif kind == "bool":
            return "true" if val.lower() == "true" else "false"

        elif kind == "unit":
            unit = node.get("unit", "")
            if unit == "ms":
                return val
            elif unit == "s":
                return f"({val} * 1000)"
            elif unit == "m":
                return f"({val} * 60000)"
            elif unit == "h":
                return f"({val} * 3600000)"
            elif unit == "us":
                return f"({val} / 1000)"
            elif unit == "ns":
                return f"({val} / 1000000)"
            elif unit == "B":
                return val
            elif unit == "KB":
                if self.target in NODE_TARGETS:
                    return f"({val} * 1024)"
                return f"({val} * 1024L)" if self.target == "java" else f"({val} * 1024ULL)"
            elif unit == "MB":
                if self.target in NODE_TARGETS:
                    return f"({val} * 1024 * 1024)"
                return f"({val} * 1024L * 1024L)" if self.target == "java" else f"({val} * 1024 * 1024ULL)"
            elif unit == "GB":
                if self.target in NODE_TARGETS:
                    return f"({val} * 1024 * 1024 * 1024)"
                return f"({val} * 1024L * 1024L * 1024L)" if self.target == "java" else f"({val} * 1024 * 1024 * 1024ULL)"
            elif unit == "TB":
                if self.target in NODE_TARGETS:
                    return f"({val} * 1024 * 1024 * 1024 * 1024)"
                return f"({val} * 1024L * 1024L * 1024L * 1024L)" if self.target == "java" else f"({val} * 1024ULL * 1024 * 1024 * 1024)"
            return val

        elif kind == "unary":
            sub = self._lower_node(args[0]) if args else ""
            if op == "not":
                return f"!({sub})"
            elif op == "-":
                return f"-({sub})"
            return f"{op}({sub})"

        elif kind == "member":
            obj = self._lower_node(args[0]) if args else ""
            return f"{obj}.{val}"

        elif kind == "call":
            callee_node = args[0] if args else {}
            callee_kind = callee_node.get("kind", "")
            callee_val = callee_node.get("value", "")

            # old(expr) postcondition evaluation snapshot
            if callee_val == "old":
                inner_node = args[1] if len(args) > 1 else {}
                safe_name = self._safe_var_name(inner_node)
                return f"_old_{safe_name}"

            # Member call like obj.len()
            if callee_kind == "member":
                obj = self._lower_node(callee_node.get("args", [{}])[0])
                mem_name = callee_node.get("value", "")
                if mem_name == "len":
                    if self.target in NODE_TARGETS:
                        return f"{obj}.length"
                    return f"{obj}.length()"
                # general member call
                passed_args = [self._lower_node(a) for a in args[1:]]
                return f"{obj}.{mem_name}({', '.join(passed_args)})"

            # Builtin functions
            if callee_val in ("max", "min", "clamp"):
                passed_args = [self._lower_node(a) for a in args[1:]]
                if self.target == "cpp":
                    return f"std::{callee_val}({', '.join(passed_args)})"
                else:
                    if callee_val == "clamp":
                        # Java / Node clamp: Math.max(min, Math.min(max, val))
                        if len(passed_args) == 3:
                            v, mi, ma = passed_args[0], passed_args[1], passed_args[2]
                            return f"Math.max({mi}, Math.min({ma}, {v}))"
                    return f"Math.{callee_val}({', '.join(passed_args)})"

            # Generic call
            callee_str = self._lower_node(callee_node)
            passed_args = [self._lower_node(a) for a in args[1:]]
            return f"{callee_str}({', '.join(passed_args)})"

        elif kind == "binary":
            left = self._lower_node(args[0]) if len(args) > 0 else ""
            right = self._lower_node(args[1]) if len(args) > 1 else ""

            # 1. Implication: a implies b => (!a || b)
            if op == "implies":
                return f"(!({left}) || ({right}))"

            # 2. Logical operators
            if op == "and":
                return f"({left} && {right})"
            if op == "or":
                return f"({left} || {right})"

            # 3. Equality operators
            if op in ("==", "!="):
                if self.target in NODE_TARGETS:
                    strict_op = "===" if op == "==" else "!=="
                    return f"({left} {strict_op} {right})"
                is_string_comparison = self._is_string_expr(args[0]) or self._is_string_expr(args[1])
                if is_string_comparison and self.target == "java":
                    if op == "==":
                        return f"Objects.equals({left}, {right})"
                    else:
                        return f"!Objects.equals({left}, {right})"
                return f"({left} {op} {right})"

            # 4. Relational & arithmetic
            return f"({left} {op} {right})"

        return val

    def _is_string_expr(self, node: Dict[str, Any]) -> bool:
        if not node:
            return False
        if node.get("kind") == "string":
            return True
        if node.get("kind") == "ident":
            ident = node.get("value", "")
            return self.scope.get(ident) == "string"
        return False

    def _safe_var_name(self, node: Dict[str, Any]) -> str:
        if not node:
            return "val"
        kind = node.get("kind", "")
        if kind == "ident":
            return node.get("value", "val")
        elif kind == "member":
            obj = self._safe_var_name(node.get("args", [{}])[0])
            return f"{obj}_{node.get('value', '')}"
        return "val"
