#!/usr/bin/env python3
"""
test_container_emitter.py
Verifies Containerfile emission for OCI compliance, Podman/Buildah compatibility,
PRD/ADR lineage labels, and contract test gates.
"""

import unittest
from compiler.backend.container_emitter import ContainerEmitter

class TestContainerEmitter(unittest.TestCase):
    def test_cpp_alpine_containerfile(self):
        cfile = ContainerEmitter.generate_containerfile(
            module_name="Security.TokenManager",
            contracts=["TokenStore"],
            target_lang="cpp",
            package_options={"base": "alpine", "tag": "2.1.0"},
            target_options={"standard": "c++20"},
            artifacts=[{"type": "prd", "id": "PRD-SEC-002"}, {"type": "adr", "id": "ADR-0042"}]
        )
        self.assertIn("FROM docker.io/library/alpine:3.23 AS builder", cfile)
        self.assertIn("RUN make all test", cfile)
        self.assertIn("RUN make install PREFIX=/opt/agentc", cfile)
        self.assertIn("FROM docker.io/library/alpine:3.23", cfile)
        self.assertIn('org.opencontainers.image.title="security-tokenmanager"', cfile)
        self.assertIn('org.opencontainers.image.version="2.1.0"', cfile)
        self.assertIn('io.agentc.lineage="PRD:PRD-SEC-002,ADR:ADR-0042"', cfile)
        self.assertIn("USER 65532:65532", cfile)
        self.assertIn('ENTRYPOINT ["/opt/agentc/bin/TokenStore_cli"]', cfile)
        self.assertIn('CMD ["selftest"]', cfile)

    def test_cpp_distroless_containerfile(self):
        cfile = ContainerEmitter.generate_containerfile(
            module_name="Examples.MathService",
            contracts=["MathOperations"],
            target_lang="cpp",
            package_options={"base": "distroless", "tag": "1.0.0"},
            target_options={"standard": "c++20"},
            artifacts=[]
        )
        self.assertIn("FROM docker.io/library/debian:12-slim AS builder", cfile)
        self.assertIn("FROM gcr.io/distroless/cc-debian12:nonroot", cfile)
        self.assertIn("USER 65532:65532", cfile)

    def test_java_containerfile(self):
        cfile = ContainerEmitter.generate_containerfile(
            module_name="Examples.MathService",
            contracts=["MathOperations"],
            target_lang="java",
            package_options={"base": "alpine", "tag": "1.0.0"},
            target_options={"jdk": "21", "package": "com.examples.math"},
            artifacts=[]
        )
        self.assertIn("FROM docker.io/library/eclipse-temurin:21-jdk-alpine AS builder", cfile)
        self.assertIn("FROM docker.io/library/eclipse-temurin:21-jre-alpine", cfile)
        self.assertIn("ENTRYPOINT [\"java\", \"-cp\", \"/app/app.jar\", \"com.examples.math.MathOperationsCli\"]", cfile)

    def test_containerignore_content(self):
        cignore = ContainerEmitter.generate_containerignore()
        self.assertIn(".agentc/cache", cignore)
        self.assertIn("*.o", cignore)
        self.assertIn("*.a", cignore)

if __name__ == "__main__":
    unittest.main()
