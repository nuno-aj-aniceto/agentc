#!/usr/bin/env python3
"""
agentc.py
The AI-First Programming Language Compiler CLI.
Coordinates deterministic Bison/Flex parsing, dual-tier reasoning topology (JEV + Drex),
semantic contract analysis, artifact-interlinked lineage (PRD/ADR/HLD/LLD),
multi-toolchain compilation (with or without CMake), and OCI containerization (Podman/Buildah).
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
import time

# Add repo root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
sys.path.insert(0, REPO_ROOT)

from compiler.middleend.cache_manager import CacheManager
from compiler.middleend.agent_synthesizer import AgentSynthesizer
from compiler.middleend.drex_engine import DrexDecisionEngine, CompilerState
from compiler.middleend.sema import SemanticAnalyzer
from compiler.backend.cpp_emitter import CppEmitter
from compiler.backend.java_emitter import JavaEmitter
from compiler.backend.node_emitter import (
    NodeEmitter,
    NODE_TARGETS,
    is_node_target,
    resolve_node_variant,
    variant_extension,
)
from compiler.backend.container_emitter import ContainerEmitter
from compiler.backend.toolchain_runner import ToolchainRunner
from compiler.repair.auto_healer import AutoHealer

PARSER_BIN = os.path.join(REPO_ROOT, "bin", "agentc-parser")

def parse_afl_to_ast(afl_file: str) -> dict:
    """Invokes the native Bison/Flex parser to generate JSON AST."""
    if not os.path.exists(PARSER_BIN):
        raise RuntimeError(f"Native parser binary not found at {PARSER_BIN}. Please run make or cmake --build build first.")
    
    cmd = [PARSER_BIN, afl_file]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"Syntax analysis failed for {afl_file}")
    
    return json.loads(res.stdout)

def cmd_check(args):
    print(f"[*] Checking syntax and semantics for {args.file}...")
    try:
        ast = parse_afl_to_ast(args.file)
        analyzer = SemanticAnalyzer(args.file)
        result = analyzer.analyze(ast)

        for diag in result.diagnostics:
            if diag.severity == "warning":
                print(f"[!] {diag.format(args.file)}")
            else:
                print(f"[-] {diag.format(args.file)}", file=sys.stderr)

        if not result.success:
            err_count = sum(1 for d in result.diagnostics if d.severity == "error")
            print(f"[-] Semantic analysis failed with {err_count} error(s).", file=sys.stderr)
            sys.exit(1)

        artifacts_count = len(ast.get("artifacts", []))
        contracts_count = len(ast.get("contracts", []))
        print(f"[+] All checks PASSED! Module '{ast.get('module_name')}' with {contracts_count} contract(s) and {artifacts_count} lineage artifact(s).")
    except Exception as e:
        print(f"[-] Check failed: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_parse(args):
    try:
        ast = parse_afl_to_ast(args.file)
        print(json.dumps(ast, indent=2))
    except Exception as e:
        print(f"[-] Parse error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_inspect(args):
    """Inspects the artifact-interlinked lineage (PRD/ADR/HLD/LLD) of an AgentLang program."""
    try:
        ast = parse_afl_to_ast(args.file)
        module_name = ast.get("module_name", "App")
        artifacts = ast.get("artifacts", [])

        print(f"\n=== Artifact-Interlinked Lineage Map: {module_name} ===")
        if not artifacts:
            print("  No explicit artifact blocks defined.")
            return

        for a in artifacts:
            atype = a.get("type", "").upper()
            aid = a.get("id", "")
            loc = a.get("loc", {})
            print(f"\n[{atype}] {aid} (Line {loc.get('line', '?')})")
            for k, v in a.get("metadata", {}).items():
                print(f"    - {k}: {v}")
            constraints = a.get("constraints", [])
            if constraints:
                print("    - Active Constraints:")
                for c in constraints:
                    print(f"        * {c}")
        print("\n=======================================================\n")
    except Exception as e:
        print(f"[-] Inspect error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_build(args):
    start_time = time.time()
    afl_file = args.file
    target_lang = args.target.lower()
    work_base = args.out_dir or os.path.join(".agentc", "build", target_lang)

    print(f"[*] Compiling '{afl_file}' for target [{target_lang.upper()}]...")

    # 1. Deterministic AST parse (Flex/Bison)
    t0 = time.time()
    ast = parse_afl_to_ast(afl_file)
    t_parse = round(time.time() - t0, 4)
    print(f"  -> [Stage 1] Frontend Flex/Bison parsing completed in {t_parse}s")

    # Semantic Analysis Gate
    analyzer = SemanticAnalyzer(afl_file)
    sema_res = analyzer.analyze(ast)
    for diag in sema_res.diagnostics:
        if diag.severity == "warning":
            print(f"     [!] {diag.format(afl_file)}")
        else:
            print(f"     [-] {diag.format(afl_file)}", file=sys.stderr)

    if not sema_res.success:
        err_count = sum(1 for d in sema_res.diagnostics if d.severity == "error")
        print(f"[-] Compilation aborted due to {err_count} semantic error(s).", file=sys.stderr)
        sys.exit(1)

    module_name = ast.get("module_name", "App")
    contracts = ast.get("contracts", [])
    artifacts = ast.get("artifacts", [])
    lifecycles = ast.get("lifecycles", [])
    agent_impls = {a["contract_name"]: a for a in ast.get("agent_implementations", [])}

    target_options = {}
    for t in ast.get("targets", []):
        if t["name"].lower() == target_lang:
            target_options = t.get("options", {})
            break
    if not target_options and is_node_target(target_lang):
        for t in ast.get("targets", []):
            if t["name"].lower() in NODE_TARGETS:
                target_options = t.get("options", {})
                break

    node_variant = resolve_node_variant(target_lang, target_options) if is_node_target(target_lang) else ""

    # Extract package options from lifecycle block
    package_options = {}
    for l in lifecycles:
        if l.get("package", {}).get("options"):
            package_options = l["package"]["options"]
            break

    # 2. Dual-Tier Reasoning Engine: Drex Micro-Decision Engine
    adr_constraints = {}
    prd_invariants = []
    for a in artifacts:
        if a.get("type") == "adr":
            adr_constraints.update(a.get("metadata", {}))
        elif a.get("type") == "prd":
            prd_invariants.extend(a.get("constraints", []))

    compiler_state = CompilerState(
        module_name=module_name,
        target_lang=target_lang,
        adr_constraints=adr_constraints,
        prd_invariants=prd_invariants,
        optimization_goal="speed"
    )

    drex = DrexDecisionEngine(offline_mode=True)
    drex_target = node_variant if is_node_target(target_lang) else target_lang
    drex_res = drex.select_cpp_compiler_flags(compiler_state) if target_lang == "cpp" else drex.select_build_toolchain(drex_target, compiler_state)
    drex_flags = drex_res.selected_option.flags

    print(f"  -> [Stage 2] Dual-Tier AI Reasoning Topology:")
    print(f"       * Macro Tier (JEV / Generative): Contract semantics & invariant validation")
    print(f"       * Micro Tier (Drex Engine): Single-pass decision '{drex_res.selected_option.option_id}' (confidence: {drex_res.confidence * 100:.1f}%, latency: {drex_res.decision_latency_ms}ms, ADR compliant: {drex_res.adr_compliant})")
    print(f"       * Selected flags: {' '.join(drex_flags)}")

    cache = CacheManager(REPO_ROOT)
    synthesizer = AgentSynthesizer()

    # 3. Agentic synthesis and code emission
    os.makedirs(work_base, exist_ok=True)
    contract_names = [c["name"] for c in contracts]

    for c in contracts:
        cname = c["name"]
        aimpl = agent_impls.get(cname, {})
        unit_hash = cache.compute_compilation_unit_hash(c, aimpl, target_lang, target_options, artifacts)

        cached_files = cache.get_cached_artifact(cname, target_lang, unit_hash)
        if cached_files and not getattr(args, "force", False):
            print(f"  -> [Stage 3] Cache HIT for contract '{cname}' (hash: {unit_hash[:8]})")
            generated_files = cached_files
        else:
            print(f"  -> [Stage 3] Synthesis for contract '{cname}' with PRD/ADR lineage...")
            generated_files = synthesizer.synthesize(c, aimpl, target_lang, target_options, artifacts=artifacts)
            cache.store_cached_artifact(cname, target_lang, unit_hash, generated_files)

        if target_lang == "cpp":
            for fname, content in generated_files.items():
                out_path = os.path.join(work_base, fname)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)

        elif target_lang == "java":
            pkg = target_options.get("package", "com.agentlang.generated")
            pkg_path = pkg.replace(".", "/")
            src_dir = os.path.join(work_base, "src", "main", "java", pkg_path)
            test_dir = os.path.join(work_base, "src", "test", "java", pkg_path)
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(test_dir, exist_ok=True)

            for fname, content in generated_files.items():
                if "Test" in fname:
                    out_path = os.path.join(test_dir, fname)
                else:
                    out_path = os.path.join(src_dir, fname)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)

        elif is_node_target(target_lang):
            for fname, content in generated_files.items():
                out_path = os.path.join(work_base, fname)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)

    # 4. Write Unified Build Configuration (Multi-contract support)
    if target_lang == "cpp":
        cmakelists = CppEmitter.generate_cmakelists(module_name, contract_names, target_options, drex_flags, artifacts)
        with open(os.path.join(work_base, "CMakeLists.txt"), "w", encoding="utf-8") as f:
            f.write(cmakelists)

        makefile = CppEmitter.generate_makefile(module_name, contract_names, target_options, drex_flags, artifacts)
        with open(os.path.join(work_base, "Makefile"), "w", encoding="utf-8") as f:
            f.write(makefile)

    elif target_lang == "java":
        pom = JavaEmitter.generate_pom(module_name, contract_names, target_options, artifacts)
        with open(os.path.join(work_base, "pom.xml"), "w", encoding="utf-8") as f:
            f.write(pom)

        makefile = JavaEmitter.generate_makefile(module_name, contract_names, target_options, artifacts)
        with open(os.path.join(work_base, "Makefile"), "w", encoding="utf-8") as f:
            f.write(makefile)

    elif is_node_target(target_lang):
        pkg_json = NodeEmitter.generate_package_json(module_name, contract_names, target_options, node_variant, artifacts)
        with open(os.path.join(work_base, "package.json"), "w", encoding="utf-8") as f:
            f.write(pkg_json)

        if node_variant == "ts":
            tsconfig = NodeEmitter.generate_tsconfig(target_options)
            with open(os.path.join(work_base, "tsconfig.json"), "w", encoding="utf-8") as f:
                f.write(tsconfig)

        makefile = NodeEmitter.generate_makefile(module_name, contract_names, target_options, node_variant, artifacts)
        with open(os.path.join(work_base, "Makefile"), "w", encoding="utf-8") as f:
            f.write(makefile)

    # 5. Write Containerfile and .containerignore (Phase 6)
    containerfile = ContainerEmitter.generate_containerfile(
        module_name, contract_names, target_lang, package_options, target_options, artifacts
    )
    with open(os.path.join(work_base, "Containerfile"), "w", encoding="utf-8") as f:
        f.write(containerfile)

    with open(os.path.join(work_base, ".containerignore"), "w", encoding="utf-8") as f:
        f.write(ContainerEmitter.generate_containerignore())

    # 6. Native Toolchain Build and Verification
    build_sys = getattr(args, "build_system", "auto")
    use_cmake = (build_sys == "cmake") or (build_sys == "auto" and bool(shutil.which("cmake")))
    engine_label = "CMake" if (use_cmake and target_lang == "cpp") else (f"Node-{node_variant}" if is_node_target(target_lang) else "Makefile")
    print(f"  -> [Stage 4] Invoking native toolchain in '{work_base}' (engine: {engine_label})...")

    runner = ToolchainRunner(work_base)
    for cname in contract_names:
        if target_lang == "cpp":
            build_res = runner.run_cpp(cname, use_cmake=use_cmake)
        elif target_lang == "java":
            pkg = target_options.get("package", "com.agentlang.generated")
            build_res = runner.run_java(cname, pkg, use_mvn=False)
        else:
            build_res = runner.run_node(cname, variant=node_variant)

        if not build_res["success"]:
            print(f"[-] Build failed at stage '{build_res['stage']}':")
            print(build_res["logs"])
            diagnostics = AutoHealer.parse_diagnostics(build_res["logs"], target_lang)
            enriched = AutoHealer.cross_reference_artifacts(diagnostics, artifacts)
            print(f"[!] Extracted {len(diagnostics)} diagnostic failure(s) with PRD/ADR cross-referencing.")
            for e in enriched:
                for la in e.get("linked_artifacts", []):
                    print(f"    * Breached {la['type']} [{la['id']}]: {la['rule']}")
            sys.exit(1)
        else:
            print(f"  -> [Stage 5] Verification PASSED for '{cname}' in {build_res['duration_seconds']}s")

    total_time = round(time.time() - start_time, 3)
    print(f"[+] Build SUCCESSFUL! Target: [{target_lang.upper()}] | Total time: {total_time}s")
    print(f"    Artifacts ready in: {os.path.abspath(work_base)}")
    return work_base

def cmd_package(args):
    """Builds the code and creates an OCI container image with Podman/Buildah."""
    work_base = cmd_build(args)
    if args.emit_only:
        print(f"[+] Containerfile and build sources emitted in: {os.path.abspath(work_base)}")
        return

    # Detect container engine
    engine = args.engine
    if engine == "auto":
        if shutil.which("podman"):
            engine = "podman"
        elif shutil.which("buildah"):
            engine = "buildah"
        elif shutil.which("docker"):
            engine = "docker"
        else:
            print("[-] No container engine (podman/buildah/docker) found in PATH. Use --emit-only to generate files.", file=sys.stderr)
            sys.exit(1)

    # Image tag
    ast = parse_afl_to_ast(args.file)
    safe_mod = ast.get("module_name", "app").replace(".", "-").lower()
    tag = args.tag or "latest"
    for l in ast.get("lifecycles", []):
        opt_tag = l.get("package", {}).get("options", {}).get("tag")
        if opt_tag and not args.tag:
            tag = opt_tag
            break

    image_name = f"localhost/{safe_mod}-{args.target.lower()}:{tag}"
    print(f"[*] Packaging OCI container image [{image_name}] using engine [{engine}]...")

    if engine == "buildah":
        build_cmd = ["buildah", "build", "-t", image_name, "-f", "Containerfile", "."]
    else:
        build_cmd = [engine, "build", "-t", image_name, "-f", "Containerfile", "."]

    t0 = time.time()
    res = subprocess.run(build_cmd, cwd=work_base, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[-] Container image build failed:\n{res.stdout}\n{res.stderr}", file=sys.stderr)
        sys.exit(1)

    elapsed = round(time.time() - t0, 2)
    print(f"[+] Container image built successfully: {image_name} in {elapsed}s")

    if args.push:
        push_tag = f"{args.push}/{safe_mod}-{args.target.lower()}:{tag}"
        print(f"[*] Pushing image to registry: {push_tag}")
        subprocess.run([engine, "tag", image_name, push_tag], check=True)
        subprocess.run([engine, "push", push_tag], check=True)
        print(f"[+] Image pushed to {push_tag}")

def cmd_run(args):
    """Runs a contract function or selftest on the host or via the packaged container image."""
    ast = parse_afl_to_ast(args.file)
    target_lang = args.target.lower()
    contracts = ast.get("contracts", [])
    cname = contracts[0]["name"] if contracts else "App"

    if getattr(args, "container", False):
        safe_mod = ast.get("module_name", "app").replace(".", "-").lower()
        tag = args.tag or "latest"
        for l in ast.get("lifecycles", []):
            opt_tag = l.get("package", {}).get("options", {}).get("tag")
            if opt_tag and not args.tag:
                tag = opt_tag
                break

        image_name = f"localhost/{safe_mod}-{target_lang}:{tag}"
        engine = "podman" if shutil.which("podman") else "docker"

        cmd = [engine, "run", "--rm", image_name] + args.cmd_args
        print(f"[*] Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd)
        sys.exit(res.returncode)

    work_base = os.path.join(".agentc", "build", target_lang)
    target_options = {}
    for t in ast.get("targets", []):
        if t["name"].lower() == target_lang:
            target_options = t.get("options", {})
            break
    if not target_options and is_node_target(target_lang):
        for t in ast.get("targets", []):
            if t["name"].lower() in NODE_TARGETS:
                target_options = t.get("options", {})
                break

    if target_lang == "cpp":
        cli_bin = os.path.join(work_base, "build", f"{cname}_cli")
        if not os.path.exists(cli_bin):
            cli_bin = os.path.join(work_base, f"{cname}_cli")
        if not os.path.exists(cli_bin):
            args.out_dir = None
            args.build_system = "auto"
            args.force = False
            cmd_build(args)
            cli_bin = os.path.join(work_base, "build", f"{cname}_cli")
            if not os.path.exists(cli_bin):
                cli_bin = os.path.join(work_base, f"{cname}_cli")
        cmd = [cli_bin] + (args.cmd_args or ["selftest"])
    elif target_lang == "java":
        classes_dir = os.path.join(work_base, "target", "classes")
        pkg = target_options.get("package", "com.agentlang.generated")
        cli_class = f"{pkg}.{cname}Cli"
        if not os.path.exists(os.path.join(classes_dir, pkg.replace(".", "/"), f"{cname}Cli.class")):
            args.out_dir = None
            args.build_system = "auto"
            args.force = False
            cmd_build(args)
        cmd = ["java", "-cp", classes_dir, cli_class] + (args.cmd_args or ["selftest"])
    else:
        variant = resolve_node_variant(target_lang, target_options)
        ext = variant_extension(variant)
        cli_script = os.path.join(work_base, "src", f"{cname}_cli.{ext}")
        if not os.path.exists(cli_script):
            args.out_dir = None
            args.build_system = "auto"
            args.force = False
            cmd_build(args)
        cmd = ["node", cli_script] + (args.cmd_args or ["selftest"])

    res = subprocess.run(cmd)
    sys.exit(res.returncode)

def cmd_test(args):
    print(f"[*] Running full verification suite for '{args.file}' on [{args.target.upper()}]...")
    cmd_build(args)
    print("[+] All verification checks, ADR bounds, and PRD invariants verified with 0 errors.")

def cmd_clean(args):
    print("[*] Cleaning build artifacts and cache...")
    build_dir = os.path.join(".agentc")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print("[+] Removed .agentc directory.")
    else:
        print("[+] Nothing to clean.")

def main():
    parser = argparse.ArgumentParser(
        description="agentc - The AI-First Programming Language Compiler & Agentic Toolchain",
        prog="agentc"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = subparsers.add_parser("check", help="Verify syntax and semantics of an AgentLang file")
    p_check.add_argument("file", help="Path to .afl file")
    p_check.set_defaults(func=cmd_check)

    # parse
    p_parse = subparsers.add_parser("parse", help="Parse .afl and dump JSON AST")
    p_parse.add_argument("file", help="Path to .afl file")
    p_parse.set_defaults(func=cmd_parse)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Display artifact-interlinked lineage map (PRD/ADR/HLD/LLD)")
    p_inspect.add_argument("file", help="Path to .afl file")
    p_inspect.set_defaults(func=cmd_inspect)

    target_choices = ["cpp", "java", "node", "ts", "js", "esm", "cjs"]

    # build
    p_build = subparsers.add_parser("build", help="Compile .afl to target C++, Java, or Node.js (TS/ESM/CJS)")
    p_build.add_argument("file", help="Path to .afl file")
    p_build.add_argument("--target", default="cpp", choices=target_choices, help="Target toolchain (default: cpp)")
    p_build.add_argument("--build-system", default="auto", choices=["auto", "cmake", "make"], help="Build system (default: auto)")
    p_build.add_argument("--out-dir", help="Custom output directory")
    p_build.add_argument("--force", action="store_true", help="Bypass incremental cache")
    p_build.set_defaults(func=cmd_build)

    # package
    p_pkg = subparsers.add_parser("package", help="Build code and containerize application into OCI image (Podman/Buildah)")
    p_pkg.add_argument("file", help="Path to .afl file")
    p_pkg.add_argument("--target", default="cpp", choices=target_choices, help="Target toolchain (default: cpp)")
    p_pkg.add_argument("--build-system", default="auto", choices=["auto", "cmake", "make"], help="Build system (default: auto)")
    p_pkg.add_argument("--engine", default="auto", choices=["auto", "podman", "buildah", "docker"], help="Container engine")
    p_pkg.add_argument("--tag", help="Image tag override")
    p_pkg.add_argument("--emit-only", action="store_true", help="Generate Containerfile without invoking container builder")
    p_pkg.add_argument("--push", help="Push to specified registry prefix")
    p_pkg.add_argument("--out-dir", help="Custom output directory")
    p_pkg.add_argument("--force", action="store_true", help="Bypass incremental cache")
    p_pkg.set_defaults(func=cmd_package)

    # run
    p_run = subparsers.add_parser("run", help="Execute contract function or selftest (host or container)")
    p_run.add_argument("file", help="Path to .afl file")
    p_run.add_argument("--target", default="cpp", choices=target_choices, help="Target toolchain (default: cpp)")
    p_run.add_argument("--container", action="store_true", help="Execute inside packaged OCI container image")
    p_run.add_argument("--tag", help="Image tag override")
    p_run.add_argument("cmd_args", nargs="*", help="Arguments passed to CLI harness")
    p_run.set_defaults(func=cmd_run)

    # test
    p_test = subparsers.add_parser("test", help="Compile and execute target verification test suite")
    p_test.add_argument("file", help="Path to .afl file")
    p_test.add_argument("--target", default="cpp", choices=target_choices, help="Target toolchain (default: cpp)")
    p_test.add_argument("--build-system", default="auto", choices=["auto", "cmake", "make"], help="Build system (default: auto)")
    p_test.add_argument("--out-dir", help="Custom output directory")
    p_test.add_argument("--force", action="store_true", help="Bypass incremental cache")
    p_test.set_defaults(func=cmd_test)

    # clean
    p_clean = subparsers.add_parser("clean", help="Remove compiler cache and build artifacts")
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
