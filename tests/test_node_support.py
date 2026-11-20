#!/usr/bin/env python3
"""
test_node_support.py
Comprehensive test suite for Wave 3 Node.js Ecosystem Support:
- ECMAScript Modules (.mjs + .d.ts)
- CommonJS (.cjs + .d.ts)
- Native Erasable TypeScript (.ts + tsconfig.json)
- Semantic checks, lowering, Drex scoring, emitters, Containerfiles
- End-to-end builds & real external TypeScript/ESM/CJS consumer applications
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSER_BIN = os.path.join(REPO_ROOT, "bin", "agentc-parser")
AGENTC_BIN = os.path.join(REPO_ROOT, "bin", "agentc")
sys.path.insert(0, REPO_ROOT)

from compiler.backend.container_emitter import ContainerEmitter
from compiler.backend.expr_lowering import ExprLowerer
from compiler.backend.node_emitter import (
    NodeEmitter,
    is_node_target,
    resolve_node_variant,
)
from compiler.middleend.drex_engine import CompilerState, DrexDecisionEngine
from compiler.middleend.sema import SemanticAnalyzer
from compiler.repair.auto_healer import AutoHealer


class TestNodeGrammarAndSema(unittest.TestCase):
    def parse_and_analyze(self, code: str):
        res = subprocess.run([PARSER_BIN, "-"], input=code, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Parser error:\n{res.stderr}")
        ast = json.loads(res.stdout)
        analyzer = SemanticAnalyzer("<test>")
        return analyzer.analyze(ast), ast

    def test_target_node_with_unquoted_boolean_option(self):
        code = """
        module Demo.Node;
        target node {
            variant: ts;
            strict: true;
            esm: false;
            package: "@demo/node-pkg";
        }
        contract C {
            fn ping(msg: string) -> bool {
                pre: msg.len() > 0;
                post: result == true;
            }
        }
        """
        sema_res, ast = self.parse_and_analyze(code)
        self.assertTrue(sema_res.success, [d.message for d in sema_res.diagnostics])
        opts = ast["targets"][0]["options"]
        self.assertEqual(opts["variant"], "ts")
        self.assertEqual(opts["strict"], "true")
        self.assertEqual(opts["esm"], "false")
        self.assertEqual(resolve_node_variant("node", opts), "ts")

    def test_supported_node_target_aliases(self):
        for tname in ("node", "ts", "js", "esm", "cjs", "ecmascript"):
            code = f"module M; target {tname} {{}} contract C {{ fn ok() -> bool {{ post: result == true; }} }}"
            sema_res, _ = self.parse_and_analyze(code)
            self.assertTrue(sema_res.success, f"Target {tname} should pass sema")

    def test_e008_invalid_node_variant_rejected(self):
        code = 'module M; target node { variant: coffeescript; } contract C { fn ok() -> bool; }'
        sema_res, _ = self.parse_and_analyze(code)
        self.assertFalse(sema_res.success)
        codes = [d.code for d in sema_res.diagnostics]
        self.assertIn("E008", codes)

    def test_examples_04_and_05_pass_sema(self):
        for fname in ("04_rate_limiter_ts.afl", "05_payload_validator_esm.afl"):
            fpath = os.path.join(REPO_ROOT, "examples", fname)
            res = subprocess.run([PARSER_BIN, fpath], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Parser failed on {fname}:\n{res.stderr}")
            ast = json.loads(res.stdout)
            sema_res = SemanticAnalyzer(fpath).analyze(ast)
            self.assertTrue(sema_res.success, f"Sema failed on {fname}: {[d.message for d in sema_res.diagnostics]}")


class TestNodeLoweringAndEmitters(unittest.TestCase):
    def test_expr_lowering_node_variants(self):
        len_expr = {
            "kind": "call",
            "args": [{"kind": "member", "value": "len", "args": [{"kind": "ident", "value": "payload"}]}],
        }
        eq_expr = {
            "kind": "binary",
            "op": "==",
            "args": [{"kind": "ident", "value": "ct"}, {"kind": "string", "value": "application/json"}],
        }
        bytes_expr = {"kind": "unit", "value": "64", "unit": "MB"}
        implies_expr = {
            "kind": "binary",
            "op": "implies",
            "args": [{"kind": "ident", "value": "a"}, {"kind": "ident", "value": "b"}],
        }
        clamp_expr = {
            "kind": "call",
            "args": [
                {"kind": "ident", "value": "clamp"},
                {"kind": "ident", "value": "v"},
                {"kind": "ident", "value": "lo"},
                {"kind": "ident", "value": "hi"},
            ],
        }

        for target in ("node", "ts", "js", "esm", "cjs"):
            self.assertTrue(is_node_target(target))
            self.assertEqual(ExprLowerer.lower(len_expr, target, {"payload": "string"}), "payload.length")
            self.assertEqual(ExprLowerer.lower(eq_expr, target, {"ct": "string"}), '(ct === "application/json")')
            self.assertEqual(ExprLowerer.lower(bytes_expr, target), "(64 * 1024 * 1024)")
            self.assertEqual(ExprLowerer.lower(implies_expr, target), "(!(a) || (b))")
            self.assertEqual(ExprLowerer.lower(clamp_expr, target), "Math.max(lo, Math.min(hi, v))")

    def test_node_emitter_outputs(self):
        pkg_ts = json.loads(
            NodeEmitter.generate_package_json("Examples.RateLimiter", ["RateLimiter"], {"package": "@ex/rl"}, "ts")
        )
        self.assertEqual(pkg_ts["type"], "module")
        self.assertEqual(pkg_ts["main"], "./src/RateLimiter.ts")
        self.assertEqual(pkg_ts["types"], "./src/RateLimiter.ts")
        self.assertEqual(pkg_ts["exports"]["./RateLimiter"]["import"], "./src/RateLimiter.ts")

        pkg_cjs = json.loads(
            NodeEmitter.generate_package_json("Security.TokenManager", ["TokenStore"], {}, "cjs")
        )
        self.assertEqual(pkg_cjs["type"], "commonjs")
        self.assertEqual(pkg_cjs["main"], "./src/TokenStore.cjs")
        self.assertEqual(pkg_cjs["types"], "./src/TokenStore.d.ts")
        self.assertEqual(pkg_cjs["exports"]["."]["require"], "./src/TokenStore.cjs")

        tsconfig = json.loads(NodeEmitter.generate_tsconfig())
        self.assertTrue(tsconfig["compilerOptions"]["erasableSyntaxOnly"])
        self.assertTrue(tsconfig["compilerOptions"]["allowImportingTsExtensions"])
        self.assertTrue(tsconfig["compilerOptions"]["noEmit"])

        mk = NodeEmitter.generate_makefile("Examples.RateLimiter", ["RateLimiter"], {}, "ts")
        self.assertIn("\n\t", mk)
        self.assertIn("$(NODE) --test test/RateLimiter.test.ts", mk)
        self.assertIn("$(NODE) src/RateLimiter_cli.ts selftest", mk)

        dts = NodeEmitter.generate_dts({
            "name": "DemoSvc",
            "types": [
                {"kind": "enum", "name": "Mode", "variants": ["Fast", "Safe"]},
                {"kind": "struct", "name": "Req", "fields": [{"name": "id", "type": "string"}, {"name": "count", "type": "u32"}]},
            ],
            "state_machines": [],
            "traces": ["PRD-001"],
            "functions": [{"name": "ping", "return_type": "bool", "parameters": [{"name": "m", "type": "Mode"}], "traces": []}],
        })
        self.assertIn("export declare class DemoSvc", dts)
        self.assertIn("export interface Req", dts)
        self.assertIn("export declare const Mode: Readonly<", dts)

    def test_containerfile_generation_node(self):
        cfile_ts = ContainerEmitter.generate_containerfile(
            module_name="Examples.RateLimiter",
            contracts=["RateLimiter"],
            target_lang="ts",
            package_options={"base": "alpine", "tag": "1.0.0"},
            target_options={"variant": "ts"},
            artifacts=[{"type": "prd", "id": "PRD-RL-001"}],
        )
        self.assertIn("FROM docker.io/library/node:22-alpine", cfile_ts)
        self.assertIn("--experimental-strip-types", cfile_ts)
        self.assertIn("USER 65532:65532", cfile_ts)
        self.assertIn('io.agentc.target="node-ts"', cfile_ts)
        self.assertIn('io.agentc.lineage="PRD:PRD-RL-001"', cfile_ts)
        self.assertIn('ENTRYPOINT ["node", "/opt/agentc/app/src/RateLimiter_cli.ts"]', cfile_ts)

        cfile_distroless = ContainerEmitter.generate_containerfile(
            module_name="Examples.PayloadGuard",
            contracts=["PayloadGuard"],
            target_lang="js",
            package_options={"base": "distroless", "tag": "1.2.0"},
            target_options={},
            artifacts=[],
        )
        self.assertIn("FROM gcr.io/distroless/nodejs22-debian12:nonroot", cfile_distroless)
        self.assertIn('io.agentc.target="node-esm"', cfile_distroless)
        self.assertIn('ENTRYPOINT ["/nodejs/bin/node", "/opt/agentc/app/src/PayloadGuard_cli.mjs"]', cfile_distroless)

    def test_drex_and_auto_healer_node(self):
        drex = DrexDecisionEngine(offline_mode=True)
        state = CompilerState(module_name="Demo.Node", target_lang="ts", optimization_goal="speed")
        ts_res = drex.select_build_toolchain("ts", state)
        self.assertEqual(ts_res.selected_option.option_id, "toolchain_node_native_ts")
        esm_res = drex.select_build_toolchain("esm", state)
        self.assertEqual(esm_res.selected_option.option_id, "toolchain_node_esm")

        tsc_log = "src/RateLimiter.ts(42,13): error TS2322: Type 'string' is not assignable to type 'number'."
        diags = AutoHealer.parse_diagnostics(tsc_log, "ts")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["code"], "TS2322")
        self.assertEqual(diags[0]["line"], 42)


class TestNodeEndToEndAndConsumers(unittest.TestCase):
    def test_build_examples_across_node_dialects(self):
        matrix = [
            ("01_math_service.afl", "js"),
            ("02_token_service.afl", "cjs"),
            ("03_order_service.afl", "node"),
            ("04_rate_limiter_ts.afl", "ts"),
            ("05_payload_validator_esm.afl", "js"),
            ("05_payload_validator_esm.afl", "cjs"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, (afl, target) in enumerate(matrix):
                out_dir = os.path.join(tmpdir, f"case_{idx}_{target}")
                afl_path = os.path.join(REPO_ROOT, "examples", afl)
                res = subprocess.run(
                    [AGENTC_BIN, "build", afl_path, "--target", target, "--out-dir", out_dir, "--force"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 0, f"Build failed for {afl} [{target}]:\n{res.stdout}\n{res.stderr}")
                self.assertIn("Build SUCCESSFUL!", res.stdout)
                self.assertTrue(os.path.exists(os.path.join(out_dir, "package.json")))
                self.assertTrue(os.path.exists(os.path.join(out_dir, "Makefile")))
                self.assertTrue(os.path.exists(os.path.join(out_dir, "Containerfile")))

                mk_res = subprocess.run(["make", "test", "selftest"], cwd=out_dir, capture_output=True, text=True)
                self.assertEqual(mk_res.returncode, 0, f"Makefile test failed for {afl} [{target}]:\n{mk_res.stdout}\n{mk_res.stderr}")

    def test_polyglot_new_examples_on_cpp_and_java(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for afl in ("04_rate_limiter_ts.afl", "05_payload_validator_esm.afl"):
                afl_path = os.path.join(REPO_ROOT, "examples", afl)
                for target in ("cpp", "java"):
                    out_dir = os.path.join(tmpdir, f"{afl}_{target}")
                    cmd = [AGENTC_BIN, "build", afl_path, "--target", target, "--out-dir", out_dir, "--force"]
                    if target == "cpp":
                        cmd.extend(["--build-system", "make"])
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, f"Polyglot {target} failed on {afl}:\n{res.stdout}\n{res.stderr}")

    def test_external_consumer_code_ts_esm_and_cjs(self):
        """Compiles contracts and executes standalone TypeScript, ESM, and CJS consumer code importing them."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_dir = os.path.join(tmpdir, "rl_ts")
            esm_dir = os.path.join(tmpdir, "pg_esm")
            cjs_dir = os.path.join(tmpdir, "tok_cjs")

            for afl, tgt, out in [
                ("04_rate_limiter_ts.afl", "ts", ts_dir),
                ("05_payload_validator_esm.afl", "js", esm_dir),
                ("02_token_service.afl", "cjs", cjs_dir),
            ]:
                res = subprocess.run(
                    [AGENTC_BIN, "build", os.path.join(REPO_ROOT, "examples", afl), "--target", tgt, "--out-dir", out, "--force"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 0, f"Setup build failed for {afl}: {res.stdout}\n{res.stderr}")

            # 1. External TypeScript consumer application importing RateLimiter.ts directly
            ts_consumer = os.path.join(tmpdir, "consumer_app.ts")
            with open(ts_consumer, "w", encoding="utf-8") as f:
                f.write(
                    f"""import assert from "node:assert/strict";
import {{ RateLimiter, RateLimiterState, CircuitState, type QuotaSnapshot }} from "{ts_dir}/src/RateLimiter.ts";

const limiter = new RateLimiter();
const snapshot: QuotaSnapshot = {{
    clientId: "svc-alpha",
    remaining: limiter.consumeQuota("svc-alpha", 100, 25),
    state: CircuitState.Closed,
}};
assert.equal(snapshot.remaining, 75);
assert.equal(limiter.getState(), RateLimiterState.Closed);

// Invalid transition Closed -> HalfOpen must be blocked
assert.throws(() => limiter.probeRecovery(500), /Invalid state transition/);

// Valid full circuit lifecycle: Closed -> Open -> HalfOpen -> Closed
assert.equal(limiter.tripCircuit(1000), true);
assert.equal(limiter.getState(), RateLimiterState.Open);
assert.equal(limiter.probeRecovery(600), true);
assert.equal(limiter.getState(), RateLimiterState.HalfOpen);
assert.equal(limiter.closeCircuit(2), true);
assert.equal(limiter.getState(), RateLimiterState.Closed);

// Dimensioned units: 1000ms and 64KB ceilings
assert.equal(limiter.checkWindowBudget(999, 65536), true);
assert.throws(() => limiter.checkWindowBudget(1000, 1024), /Precondition failed/);
assert.throws(() => limiter.checkWindowBudget(100, 65537), /Precondition failed/);
console.log("TS_CONSUMER_OK");
"""
                )

            if shutil.which("deno"):
                ts_chk = subprocess.run(
                    ["deno", "check", "--no-config", "--no-lock", ts_consumer],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(ts_chk.returncode, 0, f"deno check failed on consumer_app.ts:\n{ts_chk.stderr}")

            ts_run = subprocess.run(["node", ts_consumer], capture_output=True, text=True)
            self.assertEqual(ts_run.returncode, 0, f"TS consumer failed:\n{ts_run.stdout}\n{ts_run.stderr}")
            self.assertIn("TS_CONSUMER_OK", ts_run.stdout)

            # 2. External ECMAScript (.mjs) consumer application importing PayloadGuard.mjs
            esm_consumer = os.path.join(tmpdir, "consumer_esm.mjs")
            with open(esm_consumer, "w", encoding="utf-8") as f:
                f.write(
                    f"""import assert from "node:assert/strict";
import {{ PayloadGuard }} from "{esm_dir}/src/PayloadGuard.mjs";

const guard = new PayloadGuard();
assert.equal(guard.acceptPayload("application/json", 32768, false), true);
assert.throws(() => guard.acceptPayload("application/json", 65537, false), /Precondition failed/);
assert.equal(guard.acceptPayload("application/json", 65537, true), true);
assert.throws(() => guard.acceptPayload("application/json", 1048577, true), /Precondition failed/);
assert.equal(guard.clampBatchSize(-10, 1, 50), 1);
assert.equal(guard.clampBatchSize(500, 1, 50), 50);
assert.equal(guard.isJsonContent("application/json"), true);
assert.equal(guard.isJsonContent("application/xml"), false);
console.log("ESM_CONSUMER_OK");
"""
                )
            esm_run = subprocess.run(["node", esm_consumer], capture_output=True, text=True)
            self.assertEqual(esm_run.returncode, 0, f"ESM consumer failed:\n{esm_run.stdout}\n{esm_run.stderr}")
            self.assertIn("ESM_CONSUMER_OK", esm_run.stdout)

            # 3. External CommonJS (.cjs) consumer application requiring TokenStore.cjs
            cjs_consumer = os.path.join(tmpdir, "consumer_cjs.cjs")
            with open(cjs_consumer, "w", encoding="utf-8") as f:
                f.write(
                    f"""const assert = require("node:assert/strict");
const {{ TokenStore, TokenStatus }} = require({json.dumps(os.path.join(cjs_dir, "src", "TokenStore.cjs"))});

assert.equal(TokenStatus.Active, "Active");
const store = new TokenStore();
const tok = store.issueToken("alice", 120);
assert.ok(tok.length >= 32);
assert.equal(store.validateToken(tok), true);
assert.equal(store.revokeToken(tok), true);
assert.equal(store.validateToken(tok), false);
assert.throws(() => store.issueToken("", 120), /Precondition failed/);
assert.throws(() => store.issueToken("alice", 5), /Precondition failed/);
console.log("CJS_CONSUMER_OK");
"""
                )
            cjs_run = subprocess.run(["node", cjs_consumer], capture_output=True, text=True)
            self.assertEqual(cjs_run.returncode, 0, f"CJS consumer failed:\n{cjs_run.stdout}\n{cjs_run.stderr}")
            self.assertIn("CJS_CONSUMER_OK", cjs_run.stdout)

    def test_cli_run_host_node_targets(self):
        rl_afl = os.path.join(REPO_ROOT, "examples", "04_rate_limiter_ts.afl")
        pg_afl = os.path.join(REPO_ROOT, "examples", "05_payload_validator_esm.afl")

        res_quota = subprocess.run(
            [AGENTC_BIN, "run", rl_afl, "--target", "ts", "--", "consumeQuota", "cliUser", "100", "25"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_quota.returncode, 0, res_quota.stderr)
        self.assertEqual(json.loads(res_quota.stdout)["result"], 75)

        res_bad = subprocess.run(
            [AGENTC_BIN, "run", rl_afl, "--target", "ts", "--", "consumeQuota", "cliUser", "10", "25"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_bad.returncode, 2)
        self.assertIn("Precondition failed", res_bad.stderr)

        res_json = subprocess.run(
            [AGENTC_BIN, "run", pg_afl, "--target", "js", "--", "isJsonContent", "application/json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_json.returncode, 0, res_json.stderr)
        self.assertEqual(json.loads(res_json.stdout)["result"], True)


if __name__ == "__main__":
    unittest.main()
