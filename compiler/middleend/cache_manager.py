#!/usr/bin/env python3
"""
cache_manager.py
Merkle-based AST node caching for incremental compilation in agentc.
Computes deterministic multi-factor compilation unit hashes covering
contracts, agent implementations, target options, and artifact lineage.
"""

import os
import json
import hashlib
from typing import Dict, Any, Optional, List

CACHE_DIR = ".agentc/cache"

class CacheManager:
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.cache_dir = os.path.join(base_dir, CACHE_DIR)
        os.makedirs(self.cache_dir, exist_ok=True)

    def compute_node_hash(self, node: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 hash of an AST node."""
        serialized = json.dumps(node, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def compute_compilation_unit_hash(self, contract: Dict[str, Any], agent_impl: Dict[str, Any],
                                      target: str, target_options: Dict[str, Any],
                                      artifacts: Optional[List[Dict[str, Any]]] = None) -> str:
        """Computes deterministic hash over all inputs that affect code emission."""
        payload = {
            "contract": contract,
            "agent_impl": agent_impl,
            "target": target.lower(),
            "target_options": target_options,
            "artifacts": artifacts or []
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_cached_artifact(self, contract_name: str, target: str, node_hash: str) -> Optional[Dict[str, str]]:
        """Retrieves cached generated code if node hash matches."""
        cache_file = os.path.join(self.cache_dir, f"{contract_name}_{target}_{node_hash[:16]}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def store_cached_artifact(self, contract_name: str, target: str, node_hash: str, artifacts: Dict[str, str]):
        """Persists generated code in cache indexed by AST hash."""
        cache_file = os.path.join(self.cache_dir, f"{contract_name}_{target}_{node_hash[:16]}.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(artifacts, f, indent=2)
        except Exception:
            pass

    def clear(self):
        """Clears the compilation cache."""
        if os.path.exists(self.cache_dir):
            for f in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, f)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
