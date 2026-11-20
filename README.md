# `agentc` — The AI-First Programming Language & Agentic Compiler

[![Compiler](https://img.shields.io/badge/compiler-bison%203.8%20%7C%20flex%202.6-blue)](#)
[![Standard](https://img.shields.io/badge/C%2B%2B-20%20%7C%2023-purple)](#)
[![Java](https://img.shields.io/badge/Java-OpenJDK%2021%2B-red)](#)
[![Node.js](https://img.shields.io/badge/Node.js-ESM%20%7C%20CJS%20%7C%20TS-brightgreen)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

`agentc` is a next-generation programming language and compiling toolchain engineered for the agentic development era. It shifts the paradigm of programming from mechanical, boilerplate-heavy syntax to **verified semantic contracts, architectural intents, and an autonomous compiler agent**.

---

## 🚀 Key Innovations

1. **Artifact-Interlinked Runtime (PRD / ADR / HLD / LLD Lineage)**:
   - Preserves and continuously enforces architectural intent: PRD acceptance criteria compile into dynamic invariants; ADR non-functional constraints (latency budgets, concurrency, memory limits) govern optimization choices; HLD/LLD define module boundaries.
   - Every generated C++ and Java file includes `@lineage` and traceability annotations linking source code directly to corresponding engineering documents.
2. **Dual-Tier AI Reasoning Topology (JEV + Drex Architecture)**:
   - **Macro Tier (JEV / Generative Synthesis)**: Multi-step reasoning over contracts, complex refactoring strategies, and code synthesis.
   - **Micro Tier (Drex Decision Engine)**: High-speed single-pass option scoring (<6B param profile, scoring **51.73 on Decision Index 0.2** at ~25 decisions/s). Evaluates compiler flags, target toolchains, and ADR constraint compliance with zero token streaming.
3. **Dual-Layer Language Design (`AgentLang`)**:
   - **Deterministic Scaffold**: Module boundaries, contracts, types, invariants, and build targets are parsed deterministically via **GNU Bison (LALR(1)) and Flex** in sub-milliseconds.
   - **Semantic Intent Nodes**: High-level functionality is declared via `intent`, `invariants`, and `contract` pre/post-conditions, drastically reducing token generation overhead.
4. **Polyglot Autonomous Compiling Agent**:
   - `agentc` comprehends the program's structural semantics and synthesizes idiomatic, production-grade target implementations.
   - Supports polyglot toolchains: **modern C++20 via CMake/Make**, **Java 21+ via Maven/Javac**, and **Node.js 22+ across ECMAScript Modules (`.mjs` + `.d.ts`), CommonJS (`.cjs` + `.d.ts`), and Native Erasable TypeScript (`.ts`)**.
5. **Closed-Loop Verification & Self-Healing (TDD Loop)**:
   - When native compilers (`clang++`, `g++`, `javac`) report warnings or test assertions fail, `agentc` parses the diagnostics, cross-references active PRD/ADR bounds, and iteratively refines the implementation until all quality gates pass.
6. **Incremental Merkle AST Caching**:
   - Contracts are hashed using Merkle SHA-256 trees. Unmodified modules are compiled instantly from cache (`Cache HIT`), enabling lightning-fast feedback loops.
7. **SDLC-First Primitives**:
   - First-class syntax for the entire software development lifecycle: `artifact`, `verify`, `benchmark`, `package` (Docker/OCI), and `deploy` (Kubernetes).
8. **Explicit Traceability Directives (`traces: [...]`)**:
   - Contract- and method-level traceability linking source code directly to PRD/ADR items with semantic verification (`E009`) and emitted `@trace` comments.
9. **Stateful Contracts & First-Class State Machines (`state machine`)**:
   - Deterministic state machine declarations (`initial: Created; transitions: [Created -> Processing];`) and function transition guards (`transition: Processing -> Fulfilled;`) with runtime state validation.
10. **Temporal Invariants & `old()` Expressions**:
   - Pre-execution snapshot capture in postconditions (`post: result == old(currentBalance) - 10;`) with automatic prelude emission in C++ and Java.
11. **Dimensioned Unit Literals (`TIME_LITERAL`, `BYTES_LITERAL`)**:
   - First-class lexical tokens for duration (`500ms`, `10s`, `100us`) and storage (`64MB`, `1GB`) with target-aware integer count lowering.

---

## 📂 Project Architecture

```
agentc/
├── bin/
│   ├── agentc                    # Unified CLI executable
│   └── agentc-parser             # Native Flex/Bison frontend binary
├── compiler/
│   ├── frontend/
│   │   ├── lexer.l               # Flex lexical specification (locations, %, tokens)
│   │   ├── parser.y              # Bison LALR(1) grammar (typed Expr, recovery, destructor)
│   │   ├── ast.hpp / ast.cpp     # Abstract Semantic Graph (ASG) data structures & Expr AST
│   │   ├── driver.hpp / driver.cpp # Reentrant parser driver with source line diagnostics
│   │   └── main.cpp              # Native parser CLI (supports files and stdin '-')
│   ├── middleend/
│   │   ├── sema.py               # Semantic analysis (E001-E008 diagnostics & W101 warnings)
│   │   ├── agent_synthesizer.py  # Agentic synthesis core (postconditions & CLI harnesses)
│   │   └── cache_manager.py      # Merkle AST caching engine (intent, target, artifact aware)
│   ├── backend/
│   │   ├── expr_lowering.py      # Target-aware lowering (implies, string equality, clamp, length)
│   │   ├── cpp_emitter.py        # C++20, CMakeLists.txt & standalone Makefile generator
│   │   ├── java_emitter.py       # Java 21, standalone Makefile & Maven pom.xml generator
│   │   ├── node_emitter.py       # Node.js package.json, tsconfig.json, .d.ts & Makefile generator
│   │   ├── container_emitter.py  # OCI Containerfile & .containerignore generator
│   │   └── toolchain_runner.py   # Subprocess runner for CMake, Make, Javac, Maven & Node
│   └── repair/
│       └── auto_healer.py        # Closed-loop compiler diagnostic parser & repair loop
├── cli/
│   └── agentc.py                 # Unified driver CLI (check, build, package, run, inspect)
├── examples/
│   ├── 01_math_service.afl       # Arithmetic & statistics contract
│   ├── 02_token_service.afl      # Cryptographic token store with structs & enums
│   ├── 03_order_service.afl      # Stateful order service (state machines, old(), units, traces)
│   ├── 04_rate_limiter_ts.afl    # Native TypeScript stateful circuit breaker & rate limiter
│   └── 05_payload_validator_esm.afl # ECMAScript/CJS polyglot payload validator
├── tests/
│   ├── test_build_systems.py     # Standalone Makefile and parser build tests
│   ├── test_cache.py             # Invalidation and deterministic hit tests
│   ├── test_compilation_pipeline.py # End-to-end integration tests (C++ & Java)
│   ├── test_container_emitter.py # OCI Containerfile & Podman/Buildah tests
│   ├── test_drex_engine.py       # ADR constraint evaluation and scoring benchmarks
│   ├── test_grammar.py           # Parser grammar, operator precedence, and AST tests
│   ├── test_lowering.py          # Target-aware expression lowering tests
│   ├── test_node_support.py      # Wave 3 Node.js (TS/ESM/CJS), .d.ts & consumer code tests
│   ├── test_parser.py            # Unit tests for Flex/Bison grammar
│   ├── test_sema.py              # Semantic analyzer E001-E012 validation tests
│   └── test_wave2_features.py    # Wave 2 specifications (traces, state machine, old(), units)
├── CMakeLists.txt                # Native parser CMake configuration
├── Containerfile                 # Portable agentc toolchain container
├── Makefile                      # Dual build system (CMake or direct G++/Flex/Bison)
└── README.md
```

---

## 📝 Syntax Overview (`.afl` / `.agent`)

```agentlang
module Security.TokenManager;

import std.crypto.pbkdf2;
import std.net.http;

// Polyglot target directives
target cpp {
    toolchain: cmake;
    standard: "c++20";
    namespace: "corp::security";
}

target java {
    toolchain: maven;
    jdk: 21;
    package: "com.corp.security";
}

// Formal contract with types and pre/post conditions
contract TokenStore {
    enum TokenStatus {
        Active,
        Revoked,
        Expired
    };

    struct TokenMetadata {
        userId: string;
        issuedAt: u64;
        expiresAt: u64;
        status: TokenStatus;
    };

    fn issueToken(userId: string, ttlSeconds: u32) -> string {
        pre: userId.len() > 0;
        pre: ttlSeconds >= 60 and ttlSeconds <= 86400;
        post: result.len() >= 32;
    }

    fn validateToken(token: string) -> bool {
        pre: token.len() > 0;
    }

    fn revokeToken(token: string) -> bool {
        pre: token.len() > 0;
    }
}

// Agentic Synthesis Node
agent implementation for TokenStore {
    intent: "Implement high-throughput cryptographically secure token management using PBKDF2 hashing, secure random bytes generation, and thread-safe concurrent storage.";
    
    invariants: [
        "Cryptographically secure randomness for token entropy",
        "Constant-time string comparison for token validation to thwart timing attacks",
        "Thread-safe concurrent reads and writes with mutex or concurrent map",
        "Automated revocation state transition"
    ];

    harness: tdd {
        coverage_minimum: "95%";
        property_tests: "true";
    };
}

// Full SDLC Lifecycle Mapping
lifecycle sdlc {
    verify: [unit_tests, security_audit, concurrency_stress_test];
    benchmark: {
        latency_p99: "< 5ms";
        throughput: "> 50000 req/sec";
    };
    package: docker {
        base: "distroless";
        tag: "2.1.0";
    };
    deploy: k8s {
        namespace: "security";
        replicas: "3";
        port: "8443";
    };
}
```

---

## 🛠️ Usage & CLI Commands

The `agentc` executable is installed and available directly in your PATH:

### 1. Build Parser & Toolchain (Dual Build: Make or CMake)
You can build the native Flex/Bison parser using GNU Make directly (no CMake needed) or via CMake:
```bash
# Direct build with GNU Make (Bison 3.8 + Flex 2.6 + G++ C++20)
make BUILD_SYSTEM=make

# Or using CMake:
make BUILD_SYSTEM=cmake
```

### 2. Check Syntax, Semantics & Artifact Lineage
Runs Flex/Bison parsing followed by the Semantic Analyzer (`sema.py`), reporting diagnostics `E001-E012` (undefined types, missing parameters, duplicate members, unsupported targets, orphan agents, invalid traces, undeclared states, invalid transitions, old() scope) and warnings `W101`:
```bash
agentc check examples/01_math_service.afl
agentc check examples/03_order_service.afl
```

### 3. Inspect Artifact Lineage (PRD / ADR / HLD / LLD Map)
```bash
agentc inspect examples/01_math_service.afl
```

### 4. Inspect ASG AST (`schema_version: 2` with Typed Expr)
```bash
agentc parse examples/01_math_service.afl
```

### 5. Compile for C++ Target (CMake or Direct Makefile)
```bash
# Uses CMake or standalone Makefile automatically
agentc build examples/01_math_service.afl --target cpp

# Build using pure GNU Make (without CMake):
agentc build examples/01_math_service.afl --target cpp --no-cmake
```
*Emits modern C++20 header (`.hpp`), implementation (`.cpp`), test harness (`_test.cpp`), CLI dispatcher (`_cli.cpp`), `CMakeLists.txt`, and standalone `Makefile`. Verifies contract preconditions and postconditions actively at runtime.*

### 6. Compile for Java Target (Direct Makefile or Maven)
```bash
# Uses standalone Makefile (javac + jar) or Maven automatically
agentc build examples/01_math_service.afl --target java
```
*Emits Java 21 class, JUnit 5 test suite, CLI dispatcher harness, `pom.xml`, and standalone `Makefile`. Enforces pre/postconditions and unsigned `u32` range parity.*

### 7. Compile for Node.js (TypeScript, ECMAScript ESM, CommonJS & `.d.ts` Bindings)
```bash
# Native Erasable TypeScript (.ts + tsconfig.json + node:test)
agentc build examples/04_rate_limiter_ts.afl --target ts

# Modern ES2024 ECMAScript Modules (.mjs + .d.ts TypeScript bindings)
agentc build examples/05_payload_validator_esm.afl --target js

# CommonJS (.cjs + .d.ts TypeScript bindings)
agentc build examples/02_token_service.afl --target cjs

# Resolve variant from `target node { variant: ...; }` in the .afl source
agentc build examples/03_order_service.afl --target node
```
*Emits standard `package.json`, `tsconfig.json` (for TS), `.d.ts` bindings (for ESM/CJS), standalone `Makefile`, `node:test` verification suite, and JSON CLI harness.*

### 8. Package into OCI Container (Podman / Buildah)
Generate a multi-stage, libc-paired (Alpine or Distroless), non-root OCI `Containerfile` and build an image:
```bash
# Package with Podman/Buildah (builds and tags localhost/<image>:<tag>)
agentc package examples/01_math_service.afl --target cpp --engine podman
agentc package examples/04_rate_limiter_ts.afl --target ts --emit-only

# Emit Containerfile and .containerignore without invoking container runtime:
agentc package examples/01_math_service.afl --target cpp --emit-only
```

### 9. Run Contract Functions Directly (Host or Container)
Directly invoke contract methods via the generated CLI dispatcher or run selftest:
```bash
# Run a specific contract function:
agentc run examples/01_math_service.afl --target cpp -- divide 10 2
agentc run examples/04_rate_limiter_ts.afl --target ts -- consumeQuota clientA 100 25
# Output: {"result": 75}

# Run selftest:
agentc run examples/01_math_service.afl --target js -- selftest

# Run inside the containerized image:
agentc run examples/01_math_service.afl --target cpp --container -- divide 10 2
```

### 10. Run Comprehensive Test Suite
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📊 Evaluation & Verification Summary

| Component | Target / Toolchain | Build System | Verification | Execution Time |
|:---|:---|:---|:---|:---|
| **C++20** | `gcc` / `clang++` C++20 | CMake 3.20+ & Standalone Make | Full pre/postcondition enforcement, CLI selftest | ~3.1s (fresh) / ~0.003s (AST cache) |
| **Java 21** | OpenJDK 21 / 26 | Standalone Make & Maven | Full pre/postcondition enforcement, CLI selftest | ~0.8s (fresh) / ~0.002s (AST cache) |
| **Node.js (TS/ESM/CJS)** | Node `v22.6+` / `v26` + Deno/TSC | Standalone Make & `package.json` | Native TS, ESM/CJS + `.d.ts`, `node:test`, consumer code | ~0.8s (TS) / ~2.6s (ESM/CJS) |
| **Parser** | Bison 3.8 / Flex 2.6 | Dual: GNU Make & CMake | 100% deterministic, 0 conflicts, typed Expr AST | < 3ms |
| **Containers**| OCI / Multi-stage | Podman 6.2+ & Buildah 1.46+ | Distroless & Alpine, non-root, lineage labels | Verified via `podman run` |
| **Quality Gates**| Python 3.12+ Unit Tests | `unittest` test runner | 74/74 tests passing (100%) | ~65s full suite |
