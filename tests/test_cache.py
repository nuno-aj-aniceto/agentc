#!/usr/bin/env python3
"""
test_cache.py
Verifies Merkle compilation unit hashing and cache invalidation.
Ensures changes to intent, target options, or artifacts produce a cache MISS.
"""

import unittest
from compiler.middleend.cache_manager import CacheManager

class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.cache = CacheManager("/tmp/agentc_test_cache")

    def test_cache_key_invalidation_on_intent_change(self):
        contract = {"name": "TestContract", "functions": []}
        agent_v1 = {"contract_name": "TestContract", "intent": "Speed optimized"}
        agent_v2 = {"contract_name": "TestContract", "intent": "Memory compact"}

        h1 = self.cache.compute_compilation_unit_hash(contract, agent_v1, "cpp", {})
        h2 = self.cache.compute_compilation_unit_hash(contract, agent_v2, "cpp", {})
        self.assertNotEqual(h1, h2, "Changing agent intent must invalidate compilation cache")

    def test_cache_key_invalidation_on_target_options(self):
        contract = {"name": "TestContract", "functions": []}
        agent = {"contract_name": "TestContract", "intent": "Standard"}

        h1 = self.cache.compute_compilation_unit_hash(contract, agent, "cpp", {"namespace": "ns1"})
        h2 = self.cache.compute_compilation_unit_hash(contract, agent, "cpp", {"namespace": "ns2"})
        self.assertNotEqual(h1, h2, "Changing target options must invalidate compilation cache")

    def test_cache_key_invalidation_on_artifact_change(self):
        contract = {"name": "TestContract", "functions": []}
        agent = {"contract_name": "TestContract", "intent": "Standard"}
        art_v1 = [{"type": "adr", "id": "ADR-1", "metadata": {"latency": "1ms"}}]
        art_v2 = [{"type": "adr", "id": "ADR-1", "metadata": {"latency": "5ms"}}]

        h1 = self.cache.compute_compilation_unit_hash(contract, agent, "cpp", {}, art_v1)
        h2 = self.cache.compute_compilation_unit_hash(contract, agent, "cpp", {}, art_v2)
        self.assertNotEqual(h1, h2, "Changing ADR constraints must invalidate compilation cache")

    def test_cache_key_deterministic_hit(self):
        contract = {"name": "TestContract", "functions": []}
        agent = {"contract_name": "TestContract", "intent": "Standard"}

        h1 = self.cache.compute_compilation_unit_hash(contract, agent, "cpp", {"standard": "c++20"})
        h2 = self.cache.compute_compilation_unit_hash(contract, agent, "cpp", {"standard": "c++20"})
        self.assertEqual(h1, h2, "Identical compilation unit must produce deterministic cache HIT")

if __name__ == "__main__":
    unittest.main()
