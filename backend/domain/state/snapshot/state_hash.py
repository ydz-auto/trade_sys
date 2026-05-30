import hashlib
import json
from typing import Dict, Any


def compute_runtime_hash(state_dict: Dict[str, Any]) -> str:
    content = json.dumps(state_dict, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


def verify_runtime_hash(state_dict: Dict[str, Any], expected_hash: str) -> bool:
    actual_hash = compute_runtime_hash(state_dict)
    return actual_hash == expected_hash
