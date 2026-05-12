"""
Content Dedup - 内容指纹去重模块
使用 SimHash/MinHash 算法进行高效去重
"""
import hashlib
import re
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("quality.dedup")


@dataclass
class ContentFingerprint:
    """内容指纹"""
    simhash: int = 0
    minhash: Tuple[int, ...] = ()
    content_hash: str = ""
    title_hash: str = ""
    
    def similarity(self, other: 'ContentFingerprint') -> float:
        """计算与另一个指纹的相似度"""
        if not self.simhash or not other.simhash:
            return 0.0
        
        xor = self.simhash ^ other.simhash
        distance = bin(xor).count('1')
        
        return 1.0 - (distance / 64.0)
    
    def is_duplicate(self, other: 'ContentFingerprint', threshold: float = 0.85) -> bool:
        """判断是否为重复内容"""
        return self.similarity(other) >= threshold


class SimHash:
    """SimHash 算法实现"""
    
    FEATURE_COUNT = 64
    
    @classmethod
    def compute(cls, text: str) -> int:
        """计算文本的 SimHash"""
        if not text or not text.strip():
            return 0
        
        features = cls._extract_features(text)
        v = [0] * cls.FEATURE_COUNT
        
        for feature in features:
            hash_value = cls._hash_feature(feature)
            
            for i in range(cls.FEATURE_COUNT):
                bit = (hash_value >> i) & 1
                v[i] += 1 if bit else -1
        
        simhash = 0
        for i in range(cls.FEATURE_COUNT):
            if v[i] > 0:
                simhash |= (1 << i)
        
        return simhash
    
    @classmethod
    def _extract_features(cls, text: str) -> List[str]:
        """提取特征词"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        features = []
        for i in range(len(words) - 2):
            features.append(' '.join(words[i:i+3]))
        
        return features
    
    @classmethod
    def _hash_feature(cls, feature: str) -> int:
        """哈希特征"""
        return int(hashlib.md5(feature.encode()).hexdigest(), 16)


class MinHash:
    """MinHash 算法实现"""
    
    DEFAULT_PERMUTATIONS = 128
    
    @classmethod
    def compute(cls, text: str, num_permutations: int = None) -> Tuple[int, ...]:
        """计算 MinHash 签名"""
        if num_permutations is None:
            num_permutations = cls.DEFAULT_PERMUTATIONS
        
        if not text or not text.strip():
            return tuple([0] * num_permutations)
        
        shingles = cls._generate_shingles(text, 3)
        shingles_array = np.array(list(shingles))
        
        minhash = []
        for i in range(num_permutations):
            min_val = float('inf')
            for j, shingle in enumerate(shingles_array):
                hash_val = cls._hash(shingle, i, j)
                if hash_val < min_val:
                    min_val = hash_val
            minhash.append(int(min_val))
        
        return tuple(minhash)
    
    @classmethod
    def _generate_shingles(cls, text: str, k: int = 3) -> Set[str]:
        """生成 k-shingles"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        shingles = set()
        for i in range(len(words) - k + 1):
            shingles.add(' '.join(words[i:i+k]))
        
        return shingles
    
    @classmethod
    def _hash(cls, shingle: str, perm_idx: int, shingle_idx: int) -> int:
        """计算哈希"""
        seed = perm_idx * 1000 + shingle_idx
        hash_val = hashlib.md5(f"{shingle}_{seed}".encode()).hexdigest()
        return int(hash_val, 16)


@dataclass
class DuplicateCandidate:
    """重复候选"""
    new_fingerprint: ContentFingerprint
    existing_id: str
    existing_title: str
    similarity: float
    merge_type: str = "content"


@dataclass
class DedupResult:
    """去重结果"""
    is_duplicate: bool
    original_id: Optional[str] = None
    candidates: List[DuplicateCandidate] = field(default_factory=list)
    fingerprint: Optional[ContentFingerprint] = None


class ContentDeduplicator:
    """内容去重器
    
    使用 SimHash + MinHash 进行高效去重
    支持：
    - 内容指纹去重
    - 标题+来源+时间组合去重
    - 语义相似度去重
    """
    
    SIMHASH_THRESHOLD = 0.85
    MINHASH_THRESHOLD = 0.80
    TITLE_SIMILARITY_THRESHOLD = 0.90
    
    def __init__(
        self,
        simhash_threshold: float = None,
        minhash_threshold: float = None
    ):
        self.simhash_threshold = simhash_threshold or self.SIMHASH_THRESHOLD
        self.minhash_threshold = minhash_threshold or self.MINHASH_THRESHOLD
        
        self._content_store: dict = {}
        self._title_index: dict = defaultdict(list)
        self._source_time_index: dict = {}
        
        self._simhash_index: List[Tuple[int, str]] = []
        self._last_compact = 0
    
    def compute_fingerprint(
        self,
        title: str,
        content: str
    ) -> ContentFingerprint:
        """计算内容指纹"""
        return ContentFingerprint(
            simhash=SimHash.compute(content),
            minhash=MinHash.compute(content),
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            title_hash=hashlib.md5(title.encode()).hexdigest()
        )
    
    def check_duplicate(
        self,
        title: str,
        content: str,
        source: str,
        published_at: int
    ) -> DedupResult:
        """检查是否为重复内容"""
        fingerprint = self.compute_fingerprint(title, content)
        
        candidates = []
        is_duplicate = False
        original_id = None
        
        title_lower = title.lower()
        source_time_key = f"{source}_{published_at // 86400}"
        
        if source_time_key in self._source_time_index:
            for existing_id in self._source_time_index[source_time_key]:
                if existing_id in self._content_store:
                    existing = self._content_store[existing_id]
                    
                    if self._titles_similar(title_lower, existing["title"].lower()):
                        candidates.append(DuplicateCandidate(
                            new_fingerprint=fingerprint,
                            existing_id=existing_id,
                            existing_title=existing["title"],
                            similarity=0.95,
                            merge_type="title_source_time"
                        ))
        
        for existing_id, existing_fp in self._simhash_index:
            if existing_id in self._content_store:
                existing = self._content_store[existing_id]
                
                sim = fingerprint.similarity(existing_fp)
                
                if sim >= self.simhash_threshold:
                    candidates.append(DuplicateCandidate(
                        new_fingerprint=fingerprint,
                        existing_id=existing_id,
                        existing_title=existing["title"],
                        similarity=sim,
                        merge_type="simhash"
                    ))
                    
                    if not is_duplicate:
                        is_duplicate = True
                        original_id = existing_id
        
        best_candidate = None
        if candidates:
            best_candidate = max(candidates, key=lambda c: c.similarity)
        
        if best_candidate and best_candidate.similarity >= self.simhash_threshold:
            is_duplicate = True
            original_id = best_candidate.existing_id
        
        return DedupResult(
            is_duplicate=is_duplicate,
            original_id=original_id,
            candidates=candidates,
            fingerprint=fingerprint
        )
    
    def add_content(
        self,
        content_id: str,
        title: str,
        content: str,
        source: str,
        published_at: int
    ):
        """添加内容到索引"""
        fingerprint = self.compute_fingerprint(title, content)
        
        self._content_store[content_id] = {
            "id": content_id,
            "title": title,
            "content": content,
            "source": source,
            "published_at": published_at,
            "fingerprint": fingerprint,
            "added_at": int(datetime.now().timestamp())
        }
        
        self._title_index[title.lower()[:50]].append(content_id)
        
        source_time_key = f"{source}_{published_at // 86400}"
        if source_time_key not in self._source_time_index:
            self._source_time_index[source_time_key] = []
        self._source_time_index[source_time_key].append(content_id)
        
        self._simhash_index.append((content_id, fingerprint))
        
        if len(self._simhash_index) > 10000:
            self._compact_index()
    
    def _titles_similar(self, title1: str, title2: str) -> bool:
        """判断标题是否相似"""
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = words1 & words2
        union = words1 | words2
        
        jaccard = len(intersection) / len(union)
        
        return jaccard >= 0.7
    
    def _compact_index(self):
        """压缩索引"""
        current_time = int(datetime.now().timestamp())
        
        expired_ids = set()
        for content_id, content in self._content_store.items():
            if current_time - content["added_at"] > 86400 * 7:
                expired_ids.add(content_id)
        
        for content_id in expired_ids:
            if content_id in self._content_store:
                del self._content_store[content_id]
        
        self._simhash_index = [
            (cid, fp) for cid, fp in self._simhash_index
            if cid in self._content_store
        ]
        
        self._title_index = {
            k: [cid for cid in v if cid in self._content_store]
            for k, v in self._title_index.items()
        }
        
        self._source_time_index = {
            k: [cid for cid in v if cid in self._content_store]
            for k, v in self._source_time_index.items()
        }
        
        logger.info(f"Compact index: removed {len(expired_ids)} expired items")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "content_count": len(self._content_store),
            "simhash_index_size": len(self._simhash_index),
            "title_index_size": len(self._title_index),
            "source_time_index_size": len(self._source_time_index)
        }


from datetime import datetime


# 全局去重器实例
_deduplicator: Optional[ContentDeduplicator] = None

def get_deduplicator() -> ContentDeduplicator:
    """获取去重器单例"""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = ContentDeduplicator()
    return _deduplicator
