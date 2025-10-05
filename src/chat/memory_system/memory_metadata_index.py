"""
记忆元数据索引。
"""

from dataclasses import asdict, dataclass
from typing import Any

from src.common.logger import get_logger

logger = get_logger(__name__)

from inkfox.memory import PyMetadataIndex as _RustIndex  # type: ignore


@dataclass
class MemoryMetadataIndexEntry:
    memory_id: str
    user_id: str
    memory_type: str
    subjects: list[str]
    objects: list[str]
    keywords: list[str]
    tags: list[str]
    importance: int
    confidence: int
    created_at: float
    access_count: int
    chat_id: str | None = None
    content_preview: str | None = None


class MemoryMetadataIndex:
    """Rust 加速版本唯一实现。"""

    def __init__(self, index_file: str = "data/memory_metadata_index.json"):
        self._rust = _RustIndex(index_file)
        # 仅为向量层和调试提供最小缓存（长度判断、get_entry 返回）
        self.index: dict[str, MemoryMetadataIndexEntry] = {}
        logger.info("✅ MemoryMetadataIndex (Rust) 初始化完成，仅支持加速实现")

    # 向后代码仍调用的接口：batch_add_or_update / add_or_update
    def batch_add_or_update(self, entries: list[MemoryMetadataIndexEntry]):
        if not entries:
            return
        payload = []
        for e in entries:
            if not e.memory_id:
                continue
            self.index[e.memory_id] = e
            payload.append(asdict(e))
        if payload:
            try:
                self._rust.batch_add(payload)
            except Exception as ex:
                logger.error(f"Rust 元数据批量添加失败: {ex}")

    def add_or_update(self, entry: MemoryMetadataIndexEntry):
        self.batch_add_or_update([entry])

    def search(
        self,
        memory_types: list[str] | None = None,
        subjects: list[str] | None = None,
        keywords: list[str] | None = None,
        tags: list[str] | None = None,
        importance_min: int | None = None,
        importance_max: int | None = None,
        created_after: float | None = None,
        created_before: float | None = None,
        user_id: str | None = None,
        limit: int | None = None,
        flexible_mode: bool = True,
    ) -> list[str]:
        params: dict[str, Any] = {
            "user_id": user_id,
            "memory_types": memory_types,
            "subjects": subjects,
            "keywords": keywords,
            "tags": tags,
            "importance_min": importance_min,
            "importance_max": importance_max,
            "created_after": created_after,
            "created_before": created_before,
            "limit": limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        try:
            if flexible_mode:
                return list(self._rust.search_flexible(params))
            return list(self._rust.search_strict(params))
        except Exception as ex:
            logger.error(f"Rust 搜索失败返回空: {ex}")
            return []

    def get_entry(self, memory_id: str) -> MemoryMetadataIndexEntry | None:
        return self.index.get(memory_id)

    def get_stats(self) -> dict[str, Any]:
        try:
            raw = self._rust.stats()
            return {
                "total_memories": raw.get("total", 0),
                "types": raw.get("types_dist", {}),
                "subjects_count": raw.get("subjects_indexed", 0),
                "keywords_count": raw.get("keywords_indexed", 0),
                "tags_count": raw.get("tags_indexed", 0),
            }
        except Exception as ex:
            logger.warning(f"读取 Rust stats 失败: {ex}")
            return {"total_memories": 0}

    def save(self):  # 仅调用 rust save
        try:
            self._rust.save()
        except Exception as ex:
            logger.warning(f"Rust save 失败: {ex}")


__all__ = [
    "MemoryMetadataIndex",
    "MemoryMetadataIndexEntry",
]
