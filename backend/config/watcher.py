"""
Config Watcher - 配置热更新

监听配置变化并触发回调。
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime


class ConfigWatcher:
    """
    配置监听器
    
    职责：
    - 监听配置文件变化
    - 触发配置更新回调
    - 记录配置版本
    """
    
    def __init__(self, config_dir: str, poll_interval: float = 5.0):
        self.config_dir = Path(config_dir)
        self.poll_interval = poll_interval
        
        self._file_hashes: Dict[str, str] = {}
        self._callbacks: List[Callable] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def on_change(self, callback: Callable) -> None:
        """注册配置变化回调"""
        self._callbacks.append(callback)
    
    def _compute_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        if not file_path.exists():
            return ""
        
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _scan_files(self) -> Dict[str, str]:
        """扫描配置文件"""
        hashes = {}
        
        for yaml_file in self.config_dir.rglob("*.yaml"):
            relative_path = str(yaml_file.relative_to(self.config_dir))
            hashes[relative_path] = self._compute_hash(yaml_file)
        
        return hashes
    
    def _detect_changes(self, new_hashes: Dict[str, str]) -> List[str]:
        """检测变化的文件"""
        changes = []
        
        for file_path, new_hash in new_hashes.items():
            old_hash = self._file_hashes.get(file_path)
            if old_hash != new_hash:
                changes.append(file_path)
        
        for file_path in self._file_hashes:
            if file_path not in new_hashes:
                changes.append(file_path)
        
        return changes
    
    async def _notify_callbacks(self, changes: List[str]) -> None:
        """通知回调"""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(changes)
                else:
                    callback(changes)
            except Exception:
                pass
    
    async def _watch_loop(self) -> None:
        """监听循环"""
        while self._running:
            try:
                new_hashes = self._scan_files()
                changes = self._detect_changes(new_hashes)
                
                if changes:
                    await self._notify_callbacks(changes)
                    self._file_hashes = new_hashes
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception:
                await asyncio.sleep(self.poll_interval)
    
    async def start(self) -> None:
        """启动监听"""
        self._file_hashes = self._scan_files()
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
    
    async def stop(self) -> None:
        """停止监听"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    def get_current_version(self) -> Dict[str, Any]:
        """获取当前配置版本"""
        return {
            "files": dict(self._file_hashes),
            "updated_at": datetime.now().isoformat(),
        }
