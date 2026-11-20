#!/usr/bin/env python3
"""
sema.py
Semantic Analysis Pass for AgentLang (agentc).
Performs name resolution, type inference, contract clause validation,
and cross-declaration verification.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

PRIMITIVE_TYPES = {
    "i32", "i64", "u32", "u64", "f32", "f64", "bool", "string", "void"
}

NUMERIC_TYPES = {
    "i32", "i64", "u32", "u64", "f32", "f64"
}

INTEGER_TYPES = {
    "i32", "i64", "u32", "u64"
}

UNSIGNED_TYPES = {
    "u32", "u64"
}

FLOAT_TYPES = {
    "f32", "f64"
}

@dataclass
class Diagnostic:
    severity: str # "error" or "warning"
    code: str     # E001, W101, etc.
    message: str
    loc: Dict[str, int] = field(default_factory=lambda: {"line": 1, "column": 1})

    def format(self, filename: str = "<stdin>") -> str:
        line = self.loc.get("line", 1)
        col = self.loc.get("column", 1)
        return f"{filename}:{line}:{col}: {self.severity}[{self.code}]: {self.message}"

@dataclass
class SemanticResult:
    success: bool
    diagnostics: List[Diagnostic]
    ast: Dict[str, Any]

class SemanticAnalyzer:
    def __init__(self, filename: str = "<stdin>"):
        self.filename = filename
        self.diagnostics: List[Diagnostic] = []
        self.contracts: Dict[str, Dict[str, Any]] = {}
        self.known_types: Dict[str, Dict[str, Any]] = {}
        self.type_aliases: Dict[str, str] = {}
        self.struct_types: Dict[str, Dict[str, str]] = {}
        self.enum_types: Dict[str, List[str]] = {}
        self.state_machines: Dict[str, Dict[str, Any]] = {}

    def add_error(self, code: str, msg: str, loc: Optional[Dict[str, int]] = None):
        self.diagnostics.append(Diagnostic("error", code, msg, loc or {"line": 1, "column": 1}))

    def add_warning(self, code: str, msg: str, loc: Optional[Dict[str, int]] = None):
        self.diagnostics.append(Diagnostic("warning", code, msg, loc or {"line": 1, "column": 1}))

    def analyze(self, ast: Dict[str, Any]) -> SemanticResult:
        self.diagnostics.clear()
        self.contracts.clear()
        self.known_types.clear()
        self.type_aliases.clear()
        self.struct_types.clear()
        self.enum_types.clear()
        self.state_machines.clear()

        # Collect artifacts for trace validation
        artifacts = ast.get("artifacts", [])
        artifact_ids = set()
        artifact_types = set()
        for a in artifacts:
            atype = a.get("type", a.get("artifact_type", "")).lower()
            aid = a.get("id", a.get("identifier", ""))
            if atype:
                artifact_types.add(atype)
            if aid:
                artifact_ids.add(aid)

        # 1. Check targets
        targets = ast.get("targets", [])
        seen_targets = set()
        for t in targets:
            tname = t.get("name", "").lower()
            tloc = t.get("loc", {})
            if tname not in ("cpp", "java"):
                self.add_error("E008", f"Unsupported target '{tname}'. Supported targets are 'cpp' and 'java'.", tloc)
            if tname in seen_targets:
                self.add_warning("W105", f"Duplicate target directive for '{tname}'.", tloc)
            seen_targets.add(tname)

        # 2. Collect contracts and declare types
        contracts = ast.get("contracts", [])
        for c in contracts:
            cname = c.get("name", "")
            cloc = c.get("loc", {})
            if cname in self.contracts:
                self.add_error("E003", f"Duplicate contract '{cname}'.", cloc)
            self.contracts[cname] = c

            # Check contract traces
            for tr in c.get("traces", []):
                self._check_trace(tr, artifact_ids, artifact_types, cloc)

            # Register state machines
            contract_sm_map = {}
            for sm in c.get("state_machines", []):
                sm_name = sm.get("name", "")
                sm_loc = sm.get("loc", {})
                init_st = sm.get("initial_state", "")
                if not self._is_state_declared(init_st, c):
                    self.add_error("E010", f"Initial state '{init_st}' in state machine '{sm_name}' is not declared in contract '{cname}'.", sm_loc)

                allowed_transitions = set()
                for tr in sm.get("transitions", []):
                    f_st = tr.get("from", "")
                    t_st = tr.get("to", "")
                    tr_loc = tr.get("loc", sm_loc)
                    if not self._is_state_declared(f_st, c):
                        self.add_error("E010", f"State '{f_st}' in state machine '{sm_name}' is not declared in contract '{cname}'.", tr_loc)
                    if not self._is_state_declared(t_st, c):
                        self.add_error("E010", f"State '{t_st}' in state machine '{sm_name}' is not declared in contract '{cname}'.", tr_loc)
                    allowed_transitions.add((f_st, t_st))

                contract_sm_map[sm_name] = {
                    "initial": init_st,
                    "transitions": allowed_transitions
                }
            self.state_machines[cname] = contract_sm_map

            # Register types
            seen_type_names = set()
            for ty in c.get("types", []):
                t_kind = ty.get("kind", "")
                t_name = ty.get("name", "")
                t_loc = ty.get("loc", {})

                if t_name in seen_type_names or t_name in PRIMITIVE_TYPES:
                    self.add_error("E003", f"Duplicate or reserved type name '{t_name}'.", t_loc)
                seen_type_names.add(t_name)

                if t_kind == "alias":
                    self.type_aliases[t_name] = ty.get("alias_target", "")
                elif t_kind == "struct":
                    fields_map = {}
                    seen_fields = set()
                    for f in ty.get("fields", []):
                        fname = f.get("name", "")
                        floc = f.get("loc", {})
                        if fname in seen_fields:
                            self.add_error("E003", f"Duplicate field '{fname}' in struct '{t_name}'.", floc)
                        seen_fields.add(fname)
                        fields_map[fname] = f.get("type", "")
                    self.struct_types[t_name] = fields_map
                elif t_kind == "enum":
                    variants = ty.get("variants", [])
                    seen_var = set()
                    for v in variants:
                        if v in seen_var:
                            self.add_error("E003", f"Duplicate enum variant '{v}' in enum '{t_name}'.", t_loc)
                        seen_var.add(v)
                    self.enum_types[t_name] = variants

        # 3. Resolve type aliases & check cycles
        for alias, target in list(self.type_aliases.items()):
            resolved = self._resolve_type(target, set())
            if not resolved:
                self.add_error("E002", f"Undefined target type '{target}' for type alias '{alias}'.")

        # 4. Check function signatures and clauses
        for c in contracts:
            cname = c.get("name", "")
            seen_functions = set()

            for fn in c.get("functions", []):
                fname = fn.get("name", "")
                floc = fn.get("loc", {})
                ret_type = fn.get("return_type", "void")

                if fname in seen_functions:
                    self.add_error("E003", f"Duplicate function '{fname}' in contract '{cname}'.", floc)
                seen_functions.add(fname)

                # Validate return type
                if not self._is_valid_type(ret_type):
                    self.add_error("E002", f"Undefined return type '{ret_type}' in function '{fname}'.", floc)

                # Check function traces
                for tr in fn.get("traces", []):
                    self._check_trace(tr, artifact_ids, artifact_types, floc)

                # Check function transition
                trans = fn.get("transition")
                if trans:
                    f_st = trans.get("from", "")
                    t_st = trans.get("to", "")
                    t_loc = trans.get("loc", floc)
                    valid = False
                    for sm_info in self.state_machines.get(cname, {}).values():
                        if (f_st, t_st) in sm_info["transitions"]:
                            valid = True
                            break
                    if not valid:
                        self.add_error("E011", f"Transition '{f_st} -> {t_st}' in function '{fname}' is not defined in any state machine of contract '{cname}'.", t_loc)

                # Validate parameters
                param_scope: Dict[str, str] = {}
                seen_params = set()
                for p in fn.get("parameters", []):
                    pname = p.get("name", "")
                    ptype = p.get("type", "")
                    ploc = p.get("loc", {})

                    if pname in seen_params:
                        self.add_error("E003", f"Duplicate parameter name '{pname}' in function '{fname}'.", ploc)
                    seen_params.add(pname)

                    if not self._is_valid_type(ptype):
                        self.add_error("E002", f"Undefined parameter type '{ptype}' for parameter '{pname}'.", ploc)

                    resolved_ptype = self._resolve_type(ptype, set()) or ptype
                    param_scope[pname] = resolved_ptype

                # Check preconditions
                pre_ast_list = fn.get("preconditions_ast", [])
                for i, expr in enumerate(pre_ast_list):
                    self._check_expression(expr, param_scope, is_postcondition=False, ret_type=ret_type)

                # Check postconditions
                post_scope = dict(param_scope)
                if ret_type != "void":
                    post_scope["result"] = self._resolve_type(ret_type, set()) or ret_type

                post_ast_list = fn.get("postconditions_ast", [])
                for i, expr in enumerate(post_ast_list):
                    self._check_expression(expr, post_scope, is_postcondition=True, ret_type=ret_type)

        # 5. Check agent implementations
        agent_impls = ast.get("agent_implementations", [])
        for a in agent_impls:
            aimpl_cname = a.get("contract_name", "")
            aloc = a.get("loc", {})
            if aimpl_cname not in self.contracts:
                self.add_error("E007", f"Agent implementation declares unknown contract '{aimpl_cname}'.", aloc)

        success = not any(d.severity == "error" for d in self.diagnostics)
        return SemanticResult(success=success, diagnostics=self.diagnostics, ast=ast)

    def _check_trace(self, trace_ref: str, artifact_ids: Set[str], artifact_types: Set[str], loc: Dict[str, int]):
        if not trace_ref or (not artifact_ids and not artifact_types):
            return
        base_ref = trace_ref.split(".")[0]
        base_lower = base_ref.lower()
        if (trace_ref not in artifact_ids and
            base_ref not in artifact_ids and
            base_lower not in artifact_types):
            self.add_error("E009", f"Invalid trace reference '{trace_ref}': no matching artifact in module.", loc)

    def _is_state_declared(self, state: str, contract: Dict[str, Any]) -> bool:
        if not state:
            return False
        for ty in contract.get("types", []):
            if ty.get("kind") == "enum":
                if state in ty.get("variants", []):
                    return True
        for ename, variants in self.enum_types.items():
            if state in variants:
                return True
        return False

    def _is_valid_type(self, ty: str) -> bool:
        base = ty.split("<")[0].strip()
        if base in PRIMITIVE_TYPES:
            return True
        if base in self.type_aliases or base in self.struct_types or base in self.enum_types:
            return True
        if base in ("list", "map", "set", "option", "Result"):
            return True
        return False

    def _resolve_type(self, ty: str, visited: Set[str]) -> Optional[str]:
        base = ty.split("<")[0].strip()
        if base in visited:
            self.add_error("E002", f"Cyclic type alias definition detected for '{base}'.")
            return None
        if base in PRIMITIVE_TYPES:
            return base
        if base in self.type_aliases:
            visited.add(base)
            return self._resolve_type(self.type_aliases[base], visited)
        if base in self.struct_types or base in self.enum_types:
            return base
        if base in ("list", "map", "set", "option"):
            return base
        return None

    def _check_expression(self, expr: Dict[str, Any], scope: Dict[str, str], is_postcondition: bool, ret_type: str) -> str:
        """Type checks an expression node recursively and returns inferred type string."""
        if not expr:
            return "unknown"

        kind = expr.get("kind", "")
        op = expr.get("op", "")
        val = expr.get("value", "")
        loc = expr.get("loc", {"line": 1, "column": 1})
        args = expr.get("args", [])

        if kind == "ident":
            if val == "result":
                if not is_postcondition:
                    self.add_error("E004", "'result' is not accessible in preconditions.", loc)
                    return "unknown"
                if ret_type == "void":
                    self.add_error("E004", "'result' cannot be used in postcondition of void function.", loc)
                    return "void"
                return scope.get("result", "unknown")

            if val not in scope:
                # Check enum variant: e.g. Active or TokenStatus.Active
                if val in self.enum_types:
                    return val
                for ename, variants in self.enum_types.items():
                    if val in variants:
                        return ename
                self.add_error("E001", f"Undefined identifier '{val}'.", loc)
                return "unknown"
            return scope[val]

        elif kind == "int":
            return "i64"

        elif kind == "float":
            return "f64"

        elif kind == "string":
            return "string"

        elif kind == "bool":
            return "bool"

        elif kind == "unit":
            unit = expr.get("unit", "")
            if unit in ("ns", "us", "ms", "s", "m", "h"):
                return "duration"
            elif unit in ("B", "KB", "MB", "GB", "TB"):
                return "bytes"
            return "u64"

        elif kind == "member":
            # Member access: args[0].val
            target_type = self._check_expression(args[0], scope, is_postcondition, ret_type) if args else "unknown"
            if target_type == "string" and val == "len":
                return "u64"
            if target_type in self.struct_types:
                fields = self.struct_types[target_type]
                if val in fields:
                    return self._resolve_type(fields[val], set()) or fields[val]
                self.add_error("E001", f"Unknown field '{val}' on struct '{target_type}'.", loc)
                return "unknown"
            if target_type in self.enum_types:
                variants = self.enum_types[target_type]
                if val in variants:
                    return target_type
                self.add_error("E001", f"Unknown variant '{val}' on enum '{target_type}'.", loc)
                return target_type
            return "unknown"

        elif kind == "call":
            # Function call: args[0] is callee, args[1:] are parameters
            callee_kind = args[0].get("kind") if args else ""
            callee_val = args[0].get("value") if args else ""

            # Check builtins like max, min, clamp, len
            if callee_kind == "member":
                # e.g. s.len()
                mem_type = self._check_expression(args[0], scope, is_postcondition, ret_type)
                return mem_type

            if callee_val == "old":
                if not is_postcondition:
                    self.add_error("E012", "'old()' expressions are only permitted inside postconditions.", loc)
                if len(args) < 2:
                    self.add_error("E012", "'old()' expects an expression argument.", loc)
                    return "unknown"
                return self._check_expression(args[1], scope, is_postcondition, ret_type)

            if callee_val in ("max", "min", "clamp"):
                if len(args) < 2:
                    self.add_error("E006", f"Function '{callee_val}' expects arguments.", loc)
                    return "i64"
                first_arg_type = self._check_expression(args[1], scope, is_postcondition, ret_type)
                for a in args[2:]:
                    self._check_expression(a, scope, is_postcondition, ret_type)
                return first_arg_type

            # Check general identifier call
            for a in args[1:]:
                self._check_expression(a, scope, is_postcondition, ret_type)
            return "unknown"

        elif kind == "unary":
            sub_type = self._check_expression(args[0], scope, is_postcondition, ret_type) if args else "unknown"
            if op == "not":
                if sub_type not in ("bool", "unknown"):
                    self.add_error("E006", f"Logical 'not' expects bool operand, got '{sub_type}'.", loc)
                return "bool"
            elif op == "-":
                if sub_type not in NUMERIC_TYPES and sub_type != "unknown":
                    self.add_error("E006", f"Unary '-' expects numeric operand, got '{sub_type}'.", loc)
                return sub_type
            return sub_type

        elif kind == "binary":
            left_type = self._check_expression(args[0], scope, is_postcondition, ret_type) if len(args) > 0 else "unknown"
            right_type = self._check_expression(args[1], scope, is_postcondition, ret_type) if len(args) > 1 else "unknown"

            # 1. Logical operators
            if op in ("and", "or", "implies"):
                if left_type not in ("bool", "unknown"):
                    self.add_error("E006", f"Operator '{op}' expects bool on left side, got '{left_type}'.", loc)
                if right_type not in ("bool", "unknown"):
                    self.add_error("E006", f"Operator '{op}' expects bool on right side, got '{right_type}'.", loc)
                return "bool"

            # 2. Relational operators
            if op in ("<", "<=", ">", ">="):
                if left_type not in ("unknown") and right_type not in ("unknown"):
                    compatible_numeric = NUMERIC_TYPES | {"duration", "bytes"}
                    if (left_type in compatible_numeric and right_type not in compatible_numeric) or \
                       (left_type == "string" and right_type != "string"):
                        self.add_error("E006", f"Cannot compare '{left_type}' with '{right_type}' using '{op}'.", loc)
                return "bool"

            # 3. Equality operators
            if op in ("==", "!="):
                if left_type in FLOAT_TYPES or right_type in FLOAT_TYPES:
                    self.add_warning("W101", f"Exact floating-point comparison with '{op}' may fail due to precision limits.", loc)
                if left_type not in ("unknown") and right_type not in ("unknown"):
                    compatible_numeric = NUMERIC_TYPES | {"duration", "bytes"}
                    if left_type != right_type and not (left_type in compatible_numeric and right_type in compatible_numeric):
                        self.add_error("E006", f"Type mismatch in equality comparison: '{left_type}' vs '{right_type}'.", loc)
                return "bool"

            # 4. Arithmetic operators
            if op in ("+", "-", "*", "/", "%"):
                if op == "%":
                    if left_type in FLOAT_TYPES or right_type in FLOAT_TYPES:
                        self.add_error("E006", "Modulo operator '%' is only valid for integer types.", loc)
                if left_type not in ("unknown") and right_type not in ("unknown"):
                    compatible_numeric = NUMERIC_TYPES | {"duration", "bytes"}
                    if left_type not in compatible_numeric or right_type not in compatible_numeric:
                        self.add_error("E006", f"Arithmetic operator '{op}' cannot be applied to '{left_type}' and '{right_type}'.", loc)
                return left_type if left_type in NUMERIC_TYPES else "i64"

        return "unknown"
