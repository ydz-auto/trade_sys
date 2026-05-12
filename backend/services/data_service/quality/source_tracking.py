"""
Source Tracking - 溯源与快照存储
保留原始链接、原始时间和 HTML 快照
"""
import hashlib
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import aiofiles

from infrastructure.logging import get_logger

logger = get_logger("quality.tracking")


class SnapshotStatus(Enum):
    """快照状态"""
    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class SourceRecord:
    """来源记录"""
    content_id: str
    original_url: str
    original_title: str
    original_published_at: int
    original_html: Optional[str]
    html_captured_at: Optional[float]
    html_snapshot_path: Optional[str]
    status: SnapshotStatus
    redirect_chain: List[str] = field(default_factory=list)
    final_url: Optional[str] = None
    http_status: Optional[int] = None
    content_hash: str = ""
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())


@dataclass
class SourceSnapshot:
    """来源快照"""
    content_id: str
    url: str
    title: str
    published_at: int
    html_content: str
    text_content: str
    captured_at: float
    capture_method: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceTrace:
    """溯源追踪"""
    content_id: str
    source_record: SourceRecord
    versions: List[Dict] = field(default_factory=list)
    corrections: List[Dict] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


class SourceTracker:
    """来源追踪器
    
    功能：
    - 保存原始 URL 和发布时间
    - 捕获 HTML 快照
    - 追踪重定向链
    - 版本历史
    - 修正记录
    """
    
    def __init__(
        self,
        snapshot_dir: str = "/tmp/snapshots",
        max_snapshots: int = 10000,
        snapshot_retention_days: int = 30
    ):
        self.snapshot_dir = snapshot_dir
        self.max_snapshots = max_snapshots
        self.snapshot_retention_days = snapshot_retention_days
        
        self._records: Dict[str, SourceRecord] = {}
        self._snapshots: Dict[str, SourceSnapshot] = {}
        self._traces: Dict[str, SourceTrace] = {}
        self._url_to_content: Dict[str, str] = {}
        
        self._stats = {
            "total_records": 0,
            "total_snapshots": 0,
            "captured": 0,
            "failed": 0
        }
    
    def create_record(
        self,
        content_id: str,
        url: str,
        title: str,
        published_at: int,
        html_content: str = None,
        http_status: int = None,
        redirect_chain: List[str] = None
    ) -> SourceRecord:
        """创建来源记录"""
        content_hash = hashlib.md5(f"{url}{title}".encode()).hexdigest()
        
        record = SourceRecord(
            content_id=content_id,
            original_url=url,
            original_title=title,
            original_published_at=published_at,
            original_html=html_content,
            html_captured_at=time.time() if html_content else None,
            html_snapshot_path=None,
            status=SnapshotStatus.CAPTURED if html_content else SnapshotStatus.PENDING,
            redirect_chain=redirect_chain or [],
            final_url=redirect_chain[-1] if redirect_chain else url,
            http_status=http_status,
            content_hash=content_hash
        )
        
        self._records[content_id] = record
        self._url_to_content[url] = content_id
        
        self._stats["total_records"] += 1
        
        return record
    
    async def capture_snapshot(
        self,
        content_id: str,
        url: str,
        html_content: str,
        capture_method: str = "http"
    ) -> Optional[SourceSnapshot]:
        """捕获快照"""
        if content_id not in self._records:
            logger.warning(f"Content {content_id} not found in records")
            return None
        
        record = self._records[content_id]
        
        try:
            snapshot_id = hashlib.md5(f"{url}_{time.time()}".encode()).hexdigest()
            
            snapshot = SourceSnapshot(
                content_id=content_id,
                url=url,
                title=record.original_title,
                published_at=record.original_published_at,
                html_content=html_content,
                text_content=self._extract_text(html_content),
                captured_at=time.time(),
                capture_method=capture_method,
                metadata={
                    "http_status": record.http_status,
                    "redirect_chain": record.redirect_chain
                }
            )
            
            self._snapshots[snapshot_id] = snapshot
            record.html_snapshot_path = snapshot_id
            record.status = SnapshotStatus.CAPTURED
            
            self._stats["captured"] += 1
            
            await self._save_snapshot_to_disk(snapshot)
            
            logger.info(f"Captured snapshot for {content_id}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to capture snapshot: {e}")
            record.status = SnapshotStatus.FAILED
            self._stats["failed"] += 1
            return None
    
    def _extract_text(self, html: str) -> str:
        """从 HTML 提取纯文本"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            
            while "\n\n\n" in text:
                text = text.replace("\n\n\n", "\n\n")
            
            return text
        except Exception as e:
            logger.warning(f"Failed to extract text: {e}")
            return ""
    
    async def _save_snapshot_to_disk(self, snapshot: SourceSnapshot):
        """保存快照到磁盘"""
        try:
            import os
            os.makedirs(self.snapshot_dir, exist_ok=True)
            
            filename = f"{snapshot.content_id}_{int(snapshot.captured_at)}.html"
            filepath = os.path.join(self.snapshot_dir, filename)
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(snapshot.html_content)
            
            logger.debug(f"Saved snapshot to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save snapshot to disk: {e}")
    
    async def load_snapshot_from_disk(self, content_id: str, timestamp: float) -> Optional[str]:
        """从磁盘加载快照"""
        try:
            import os
            
            filename = f"{content_id}_{int(timestamp)}.html"
            filepath = os.path.join(self.snapshot_dir, filename)
            
            if os.path.exists(filepath):
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    return await f.read()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load snapshot from disk: {e}")
            return None
    
    def add_version(
        self,
        content_id: str,
        version_data: Dict
    ):
        """添加版本记录"""
        if content_id not in self._traces:
            self._traces[content_id] = SourceTrace(
                content_id=content_id,
                source_record=self._records.get(content_id)
            )
        
        version_data["version_at"] = time.time()
        self._traces[content_id].versions.append(version_data)
    
    def add_correction(
        self,
        content_id: str,
        correction_type: str,
        old_value: Any,
        new_value: Any,
        reason: str
    ):
        """添加修正记录"""
        if content_id not in self._traces:
            self._traces[content_id] = SourceTrace(
                content_id=content_id,
                source_record=self._records.get(content_id)
            )
        
        correction = {
            "type": correction_type,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "corrected_at": time.time()
        }
        
        self._traces[content_id].corrections.append(correction)
        logger.info(f"Added correction for {content_id}: {correction_type}")
    
    def add_flag(
        self,
        content_id: str,
        flag: str,
        details: str = ""
    ):
        """添加标记"""
        if content_id not in self._traces:
            self._traces[content_id] = SourceTrace(
                content_id=content_id,
                source_record=self._records.get(content_id)
            )
        
        flag_entry = {
            "flag": flag,
            "details": details,
            "flagged_at": time.time()
        }
        
        self._traces[content_id].flags.append(flag_entry)
    
    def get_record(self, content_id: str) -> Optional[SourceRecord]:
        """获取来源记录"""
        return self._records.get(content_id)
    
    def get_snapshot(self, snapshot_id: str) -> Optional[SourceSnapshot]:
        """获取快照"""
        return self._snapshots.get(snapshot_id)
    
    def get_trace(self, content_id: str) -> Optional[SourceTrace]:
        """获取溯源追踪"""
        return self._traces.get(content_id)
    
    def find_by_url(self, url: str) -> Optional[str]:
        """通过 URL 查找内容 ID"""
        return self._url_to_content.get(url)
    
    def get_versions(self, content_id: str) -> List[Dict]:
        """获取版本历史"""
        trace = self._traces.get(content_id)
        if trace:
            return trace.versions
        return []
    
    def get_corrections(self, content_id: str) -> List[Dict]:
        """获取修正历史"""
        trace = self._traces.get(content_id)
        if trace:
            return trace.corrections
        return []
    
    def get_flags(self, content_id: str) -> List[Dict]:
        """获取标记"""
        trace = self._traces.get(content_id)
        if trace:
            return trace.flags
        return []
    
    def cleanup_old_snapshots(self):
        """清理过期快照"""
        cutoff_time = time.time() - (self.snapshot_retention_days * 86400)
        
        expired = [
            sid for sid, snap in self._snapshots.items()
            if snap.captured_at < cutoff_time
        ]
        
        for sid in expired:
            del self._snapshots[sid]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired snapshots")
        
        self._stats["total_snapshots"] = len(self._snapshots)
        
        return len(expired)
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "total_records": len(self._records),
            "total_snapshots": len(self._snapshots),
            "total_traces": len(self._traces)
        }


# 全局追踪器
_tracker: Optional[SourceTracker] = None

def get_tracker() -> SourceTracker:
    """获取追踪器单例"""
    global _tracker
    if _tracker is None:
        _tracker = SourceTracker()
    return _tracker
