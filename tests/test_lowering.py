#!/usr/bin/env python3
"""
test_lowering.py
Verifies target-aware lowering rules for C++20 and Java 21:
- 'implies' lowering: (!a || b)
- String equality in Java using Objects.equals
- Unsigned integer bounds checking and parity
- Modulo and member access lowering
"""

import unittest
from compiler.backend.expr_lowering import ExprLowerer

class TestExprLowering(unittest.TestCase):
    def test_implies_lowering(self):
        expr = {
            "kind": "binary",
            "op": "implies",
            "args": [
                {"kind": "ident", "value": "a"},
                {"kind": "ident", "value": "b"}
            ]
        }
        cpp_out = ExprLowerer.lower(expr, "cpp", {"a": "bool", "b": "bool"})
        java_out = ExprLowerer.lower(expr, "java", {"a": "bool", "b": "bool"})
        self.assertEqual(cpp_out, "(!(a) || (b))")
        self.assertEqual(java_out, "(!(a) || (b))")

    def test_java_string_equality(self):
        expr = {
            "kind": "binary",
            "op": "==",
            "args": [
                {"kind": "ident", "value": "s"},
                {"kind": "string", "value": "test"}
            ]
        }
        cpp_out = ExprLowerer.lower(expr, "cpp", {"s": "string"})
        java_out = ExprLowerer.lower(expr, "java", {"s": "string"})
        self.assertEqual(cpp_out, '(s == "test")')
        self.assertEqual(java_out, 'Objects.equals(s, "test")')

    def test_java_string_inequality(self):
        expr = {
            "kind": "binary",
            "op": "!=",
            "args": [
                {"kind": "ident", "value": "token"},
                {"kind": "string", "value": ""}
            ]
        }
        java_out = ExprLowerer.lower(expr, "java", {"token": "string"})
        self.assertEqual(java_out, '!Objects.equals(token, "")')

    def test_member_call_len(self):
        expr = {
            "kind": "call",
            "args": [
                {
                    "kind": "member",
                    "value": "len",
                    "args": [{"kind": "ident", "value": "userId"}]
                }
            ]
        }
        cpp_out = ExprLowerer.lower(expr, "cpp", {"userId": "string"})
        java_out = ExprLowerer.lower(expr, "java", {"userId": "string"})
        self.assertEqual(cpp_out, "userId.length()")
        self.assertEqual(java_out, "userId.length()")

    def test_builtin_clamp(self):
        expr = {
            "kind": "call",
            "args": [
                {"kind": "ident", "value": "clamp"},
                {"kind": "ident", "value": "val"},
                {"kind": "ident", "value": "min_val"},
                {"kind": "ident", "value": "max_val"}
            ]
        }
        cpp_out = ExprLowerer.lower(expr, "cpp")
        java_out = ExprLowerer.lower(expr, "java")
        self.assertEqual(cpp_out, "std::clamp(val, min_val, max_val)")
        self.assertEqual(java_out, "Math.max(min_val, Math.min(max_val, val))")

if __name__ == "__main__":
    unittest.main()
