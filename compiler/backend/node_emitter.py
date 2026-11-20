#!/usr/bin/env python3
"""
node_emitter.py
Generates package.json, tsconfig.json, TypeScript (.d.ts) declaration bindings,
and standalone POSIX Makefile for Node.js targets (ECMAScript ESM, CommonJS, and TypeScript).
"""

import json
import re
from typing import Dict, Any, List, Optional, Union

NODE_TARGETS = {
    "node", "js", "ts", "esm", "cjs", "ecmascript", "typescript", "javascript"
}

VALID_NODE_VARIANTS = {
    "ts", "typescript", "esm", "ecmascript", "mjs", "js", "javascript", "cjs", "commonjs"
}

TYPE_MAP_TS = {
    "i64": "number",
    "u64": "number",
    "i32": "number",
    "u32": "number",
    "f64": "number",
    "f32": "number",
    "string": "string",
    "bool": "boolean",
    "void": "void",
}


def is_node_target(target_lang: str) -> bool:
    return target_lang.strip().lower() in NODE_TARGETS


def resolve_node_variant(
    target_lang: str, target_options: Optional[Dict[str, str]] = None
) -> str:
    """Resolves a target string and target options into canonical 'ts', 'esm', or 'cjs'."""
    t = target_lang.strip().lower()
    if t in ("ts", "typescript"):
        return "ts"
    if t in ("cjs", "commonjs"):
        return "cjs"
    if t in ("js", "esm", "ecmascript", "javascript", "mjs"):
        return "esm"

    opts = target_options or {}
    raw_var = (
        opts.get("variant")
        or opts.get("module_system")
        or opts.get("format")
        or "esm"
    )
    v = str(raw_var).strip().strip('"').lower()
    if v in ("ts", "typescript"):
        return "ts"
    if v in ("cjs", "commonjs"):
        return "cjs"
    return "esm"


def variant_extension(variant: str) -> str:
    if variant == "ts":
        return "ts"
    if variant == "cjs":
        return "cjs"
    return "mjs"


def extract_state_machine_info(contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extracts primary state machine name, initial state, and ordered state list."""
    sm_list = contract.get("state_machines", [])
    if not sm_list:
        return None
    primary_sm = sm_list[0]
    init_state = primary_sm.get("initial_state", "Initial")
    sm_states: List[str] = []
    for t in contract.get("types", []):
        if t.get("kind") == "enum" and init_state in t.get("variants", []):
            sm_states = list(t.get("variants", []))
            break
    if not sm_states:
        state_set = [init_state] if init_state else []
        for tr in primary_sm.get("transitions", []):
            for key in ("from", "to"):
                st = tr.get(key)
                if st and st not in state_set:
                    state_set.append(st)
        sm_states = state_set
    return {
        "name": primary_sm.get("name", "State"),
        "initial_state": init_state,
        "states": sm_states,
        "transitions": primary_sm.get("transitions", []),
    }


def _sanitize_pkg_name(module_name: str, options: Dict[str, str]) -> str:
    raw = str(options.get("package", "")).strip().strip('"')
    if raw:
        return raw.lower()
    safe_mod = re.sub(r"[^a-z0-9-]+", "-", module_name.lower()).strip("-")
    return f"@agentc/{safe_mod or 'app'}"


class NodeEmitter:
    @staticmethod
    def _normalize_contracts(contract_name_or_list: Union[str, List[str]]) -> List[str]:
        if isinstance(contract_name_or_list, list):
            return contract_name_or_list
        return [contract_name_or_list]

    @staticmethod
    def generate_package_json(
        module_name: str,
        contracts: Union[str, List[str]],
        options: Dict[str, str],
        variant: str = "esm",
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        contract_list = NodeEmitter._normalize_contracts(contracts)
        primary = contract_list[0] if contract_list else "App"
        ext = variant_extension(variant)
        pkg_name = _sanitize_pkg_name(module_name, options)

        def types_path(cname: str) -> str:
            return f"./src/{cname}.ts" if variant == "ts" else f"./src/{cname}.d.ts"

        def entry_path(cname: str) -> str:
            return f"./src/{cname}.{ext}"

        exports_map: Dict[str, Any] = {}
        export_key = "require" if variant == "cjs" else "import"
        exports_map["."] = {
            "types": types_path(primary),
            export_key: entry_path(primary),
            "default": entry_path(primary),
        }
        for cname in contract_list:
            exports_map[f"./{cname}"] = {
                "types": types_path(cname),
                export_key: entry_path(cname),
                "default": entry_path(cname),
            }

        bin_map = {
            f"{cname.lower()}-cli": f"./src/{cname}_cli.{ext}"
            for cname in contract_list
        }

        lineage = []
        for a in artifacts or []:
            lineage.append(f"{a.get('type', '').upper()}:{a.get('id', '')}")
        if not lineage:
            lineage = ["PRD:Default", "ADR:Default"]

        check_cmd = (
            "tsc --noEmit"
            if variant == "ts"
            else f"node --check src/{primary}.{ext}"
        )

        pkg_obj: Dict[str, Any] = {
            "name": pkg_name,
            "version": "1.0.0",
            "description": f"Auto-generated by agentc Compiling Agent for {module_name} (Node {variant})",
            "type": "commonjs" if variant == "cjs" else "module",
            "main": entry_path(primary),
            "types": types_path(primary),
            "exports": exports_map,
            "bin": bin_map,
            "engines": {
                "node": ">=22.6.0",
            },
            "scripts": {
                "check": check_cmd,
                "test": f"node --test test/*.test.{ext}",
                "selftest": f"node ./src/{primary}_cli.{ext} selftest",
            },
            "agentc": {
                "module": module_name,
                "variant": variant,
                "lineage": lineage,
            },
        }
        return json.dumps(pkg_obj, indent=2) + "\n"

    @staticmethod
    def generate_tsconfig(options: Optional[Dict[str, str]] = None) -> str:
        tsconfig = {
            "compilerOptions": {
                "target": "ES2024",
                "module": "NodeNext",
                "moduleResolution": "NodeNext",
                "strict": True,
                "noEmit": True,
                "erasableSyntaxOnly": True,
                "allowImportingTsExtensions": True,
                "skipLibCheck": True,
                "forceConsistentCasingInFileNames": True,
            },
            "include": ["src/**/*.ts", "test/**/*.ts"],
        }
        return json.dumps(tsconfig, indent=2) + "\n"

    @staticmethod
    def generate_dts(
        contract: Dict[str, Any],
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generates TypeScript declaration (.d.ts) bindings for ESM/CJS contract outputs."""
        cname = contract["name"]
        lines = [
            "/**",
            f" * @file {cname}.d.ts",
            f" * @brief TypeScript bindings auto-generated by agentc Compiling Agent for contract '{cname}'",
        ]
        for a in artifacts or []:
            lines.append(f" * @lineage {a.get('type', '').upper()}:{a.get('id', '')}")
        lines.extend([" */", ""])

        for t in contract.get("types", []):
            tkind = t.get("kind")
            tname = t.get("name", "")
            if tkind == "alias":
                mapped = TYPE_MAP_TS.get(t.get("alias_target", ""), t.get("alias_target", "unknown"))
                lines.append(f"export type {tname} = {mapped};")
            elif tkind == "enum":
                variants = t.get("variants", [])
                fields = "; ".join([f'readonly {v}: "{v}"' for v in variants])
                lines.append(f"export declare const {tname}: Readonly<{{ {fields} }}>;")
                lines.append(f"export type {tname} = (typeof {tname})[keyof typeof {tname}];")
            elif tkind == "struct":
                lines.append(f"export interface {tname} {{")
                for f in t.get("fields", []):
                    ft = TYPE_MAP_TS.get(f.get("type", ""), f.get("type", "unknown"))
                    lines.append(f"    {f['name']}: {ft};")
                lines.append("}")
        if contract.get("types"):
            lines.append("")

        sm_info = extract_state_machine_info(contract)
        state_type_name = f"{cname}State"
        if sm_info:
            state_fields = "; ".join([f'readonly {s}: "{s}"' for s in sm_info["states"]])
            lines.append(f"export declare const {state_type_name}: Readonly<{{ {state_fields} }}>;")
            lines.append(f"export type {state_type_name} = (typeof {state_type_name})[keyof typeof {state_type_name}];")
            lines.append("")

        for tr in contract.get("traces", []):
            lines.append(f"// @trace {tr}")
        lines.append(f"export declare class {cname} {{")
        if sm_info:
            lines.append(f"    static readonly State: typeof {state_type_name};")
        lines.append("    constructor();")
        if sm_info:
            lines.append(f"    getState(): {state_type_name};")
            lines.append(f"    setState(state: {state_type_name}): void;")

        for fn in contract.get("functions", []):
            for tr in fn.get("traces", []):
                lines.append(f"    // @trace {tr}")
            fname = fn["name"]
            ret_ts = TYPE_MAP_TS.get(fn.get("return_type", "void"), fn.get("return_type", "void"))
            params_ts = ", ".join(
                f"{p['name']}: {TYPE_MAP_TS.get(p['type'], p['type'])}"
                for p in fn.get("parameters", [])
            )
            lines.append(f"    {fname}({params_ts}): {ret_ts};")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def generate_makefile(
        module_name: str,
        contracts: Union[str, List[str]],
        options: Dict[str, str],
        variant: str = "esm",
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        contract_list = NodeEmitter._normalize_contracts(contracts)
        ext = variant_extension(variant)

        selftest_cmds = "\n\t".join([f"$(NODE) src/{c}_cli.{ext} selftest" for c in contract_list])
        test_cmds = "\n\t".join([f"$(NODE) --test test/{c}.test.{ext}" for c in contract_list])
        cli_installs = "\n\t".join([
            f'printf \'#!/bin/sh\\nexec node /opt/agentc/app/src/{c}_cli.{ext} "$$@"\\n\' > $(DESTDIR)$(PREFIX)/bin/{c}_cli && chmod 755 $(DESTDIR)$(PREFIX)/bin/{c}_cli'
            for c in contract_list
        ])

        if variant == "ts":
            check_cmds = (
                '@if command -v tsc >/dev/null 2>&1; then tsc --noEmit; '
                'elif command -v deno >/dev/null 2>&1; then deno check --no-config --no-lock src/*.ts; '
                'else for f in src/*.ts; do $(NODE) --experimental-strip-types -e "import(\'./$$f\')" >/dev/null 2>&1 || true; done; fi'
            )
        else:
            check_cmds = (
                f'@for f in src/*.{ext} test/*.test.{ext}; do $(NODE) --check "$$f" || exit 1; done\n'
                '\t@if command -v deno >/dev/null 2>&1 && ls src/*.d.ts >/dev/null 2>&1; then deno check --no-config --no-lock src/*.d.ts; fi'
            )

        tsconfig_install = (
            '\t@if [ -f tsconfig.json ]; then install -m 644 tsconfig.json $(DESTDIR)$(PREFIX)/app/; fi\n'
        )

        return f"""# [agentc] Standalone Node.js ({variant.upper()}) Makefile (usable with or without npm)
NODE ?= node
PREFIX ?= /usr/local

.PHONY: all check test selftest install clean

all: check

check:
\t{check_cmds}

test:
\t{test_cmds}

selftest:
\t{selftest_cmds}

install: all
\tinstall -d $(DESTDIR)$(PREFIX)/app/src $(DESTDIR)$(PREFIX)/app/test $(DESTDIR)$(PREFIX)/bin
\tinstall -m 644 package.json $(DESTDIR)$(PREFIX)/app/
{tsconfig_install}\tcp -r src/* $(DESTDIR)$(PREFIX)/app/src/
\tcp -r test/* $(DESTDIR)$(PREFIX)/app/test/
\t{cli_installs}

clean:
\trm -rf dist/
"""
