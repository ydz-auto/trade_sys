import json
import time
import uuid
from typing import Dict, Any, List, Optional

from runtime.kernel.snapshot.state_hash import compute_runtime_hash


CHECKPOINT_KEY_PREFIX = "checkpoint"
CHECKPOINT_INDEX_KEY = "checkpoint_index"


def _checkpoint_data_key(runtime_name: str, checkpoint_id: str) -> str:
    return f"{CHECKPOINT_KEY_PREFIX}:{runtime_name}:{checkpoint_id}"


def _checkpoint_index_key(runtime_name: str) -> str:
    return f"{CHECKPOINT_INDEX_KEY}:{runtime_name}"


class CheckpointManager:

    def __init__(self):
        self._redis = None

    async def _ensure_redis(self):
        if self._redis is None:
            from infrastructure.persistence.cache.redis_client import get_redis_client
            client = get_redis_client()
            if not client.is_connected:
                await client.connect()
            self._redis = client

    async def save_checkpoint(
        self,
        runtime_name: str,
        state_dict: Dict[str, Any],
    ) -> str:
        await self._ensure_redis()

        checkpoint_id = f"cp_{uuid.uuid4().hex[:12]}"
        state_hash = compute_runtime_hash(state_dict)
        timestamp = int(time.time() * 1000)

        metadata = {
            "checkpoint_id": checkpoint_id,
            "runtime_name": runtime_name,
            "timestamp": timestamp,
            "state_hash": state_hash,
        }

        checkpoint_data = {
            "metadata": metadata,
            "state": state_dict,
        }

        data_key = _checkpoint_data_key(runtime_name, checkpoint_id)
        await self._redis.set_json(data_key, checkpoint_data)

        index_key = _checkpoint_index_key(runtime_name)
        await self._redis.zadd(index_key, {checkpoint_id: timestamp})

        return checkpoint_id

    async def load_checkpoint(
        self,
        runtime_name: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_redis()

        if checkpoint_id is None:
            index_key = _checkpoint_index_key(runtime_name)
            results = await self._redis.zrevrange(index_key, 0, 0)
            if not results:
                return None
            checkpoint_id = results[0]

        data_key = _checkpoint_data_key(runtime_name, checkpoint_id)
        data = await self._redis.get_json(data_key)
        return data

    async def list_checkpoints(
        self,
        runtime_name: str,
    ) -> List[Dict[str, Any]]:
        await self._ensure_redis()

        index_key = _checkpoint_index_key(runtime_name)
        checkpoint_ids = await self._redis.zrevrange(index_key, 0, -1)

        checkpoints = []
        for cp_id in checkpoint_ids:
            data_key = _checkpoint_data_key(runtime_name, cp_id)
            data = await self._redis.get_json(data_key)
            if data and "metadata" in data:
                checkpoints.append(data["metadata"])

        return checkpoints

    async def delete_checkpoint(
        self,
        runtime_name: str,
        checkpoint_id: str,
    ) -> bool:
        await self._ensure_redis()

        data_key = _checkpoint_data_key(runtime_name, checkpoint_id)
        deleted = await self._redis.delete(data_key)

        index_key = _checkpoint_index_key(runtime_name)
        if hasattr(self._redis, "zrem"):
            await self._redis.zrem(index_key, checkpoint_id)
        else:
            await self._redis.client.zrem(index_key, checkpoint_id)

        return deleted > 0
