"""
配置版本化支持

确保配置可回测复现
每个 signal/order/trade 都应该带有 config_version
"""

import json
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from infrastructure.config.manager import ConfigManager, get_config_manager


@dataclass
class ConfigSnapshot:
    """
    配置快照
    用于回测复现
    """
    version_id: str
    timestamp: int
    config_hash: str
    configs: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigSnapshot":
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "ConfigSnapshot":
        return cls.from_dict(json.loads(json_str))


class ConfigVersioning:
    """
    配置版本化管理器
    负责配置的快照、版本追踪和回测复现
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self._config_manager = config_manager or get_config_manager()
        self._snapshots: Dict[str, ConfigSnapshot] = {}
        self._current_version_id: Optional[str] = None

    def _generate_version_id(self, configs: Dict[str, Any]) -> str:
        """生成配置版本 ID"""
        config_str = json.dumps(configs, sort_keys=True)
        hash_obj = hashlib.sha256(config_str.encode())
        return hash_obj.hexdigest()[:16]

    def _generate_config_hash(self, configs: Dict[str, Any]) -> str:
        """生成配置哈希"""
        config_str = json.dumps(configs, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def create_snapshot(self, config_keys: Optional[List[str]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> ConfigSnapshot:
        """
        创建配置快照

        Args:
            config_keys: 要快照的配置键列表，None 表示所有配置
            metadata: 快照元数据（如 strategy_id, timestamp 等）

        Returns:
            ConfigSnapshot
        """
        if config_keys:
            configs = {key: self._config_manager.get(key) for key in config_keys}
        else:
            configs = self._config_manager.get_all()

        version_id = self._generate_version_id(configs)
        config_hash = self._generate_config_hash(configs)
        timestamp = int(datetime.now().timestamp())

        snapshot = ConfigSnapshot(
            version_id=version_id,
            timestamp=timestamp,
            config_hash=config_hash,
            configs=configs,
            metadata=metadata or {},
        )

        self._snapshots[version_id] = snapshot
        self._current_version_id = version_id

        return snapshot

    def get_snapshot(self, version_id: str) -> Optional[ConfigSnapshot]:
        """获取配置快照"""
        return self._snapshots.get(version_id)

    def restore_snapshot(self, version_id: str) -> bool:
        """
        恢复配置快照
        用于回测复现

        Args:
            version_id: 快照版本 ID

        Returns:
            bool: 是否成功恢复
        """
        snapshot = self._snapshots.get(version_id)
        if not snapshot:
            return False

        for key, value in snapshot.configs.items():
            self._config_manager.set(key, value, reason=f"Restore from snapshot {version_id}")

        self._current_version_id = version_id
        return True

    def get_current_version_id(self) -> Optional[str]:
        """获取当前版本 ID"""
        return self._current_version_id

    def get_current_snapshot(self) -> Optional[ConfigSnapshot]:
        """获取当前快照"""
        if self._current_version_id:
            return self._snapshots.get(self._current_version_id)
        return None

    def list_snapshots(self) -> List[ConfigSnapshot]:
        """列出所有快照"""
        return list(self._snapshots.values())

    def export_for_backtest(self, snapshot: ConfigSnapshot) -> str:
        """
        导出自测配置
        包含完整的配置快照信息
        """
        return snapshot.to_json()

    def import_for_backtest(self, snapshot_json: str) -> ConfigSnapshot:
        """
        导入回测配置
        用于复现历史回测
        """
        snapshot = ConfigSnapshot.from_json(snapshot_json)
        self._snapshots[snapshot.version_id] = snapshot
        return snapshot


_versioning: Optional[ConfigVersioning] = None


def get_config_versioning() -> ConfigVersioning:
    """获取全局配置版本化管理器"""
    global _versioning
    if _versioning is None:
        _versioning = ConfigVersioning()
    return _versioning


def create_trading_snapshot(strategy_id: Optional[str] = None,
                           regime: Optional[str] = None) -> ConfigSnapshot:
    """
    创建交易快照
    用于记录当前交易配置状态
    """
    metadata = {
        "type": "trading",
    }
    if strategy_id:
        metadata["strategy_id"] = strategy_id
    if regime:
        metadata["regime"] = regime

    versioning = get_config_versioning()
    return versioning.create_snapshot(metadata=metadata)


def create_backtest_snapshot(backtest_id: str,
                            strategy_id: str,
                            start_time: int,
                            end_time: int) -> ConfigSnapshot:
    """
    创建回测快照
    用于记录回测开始时的配置
    """
    metadata = {
        "type": "backtest",
        "backtest_id": backtest_id,
        "strategy_id": strategy_id,
        "start_time": start_time,
        "end_time": end_time,
    }

    versioning = get_config_versioning()
    return versioning.create_snapshot(metadata=metadata)
