import json
import hashlib
import re
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

from src.common.logger import get_logger

logger = get_logger("cache_manager")


class ToolCache:
    """工具缓存管理器，用于缓存工具调用结果，支持近似匹配"""

    def __init__(
        self,
        cache_dir: str = "data/tool_cache",
        max_age_hours: int = 24,
        similarity_threshold: float = 0.65,
    ):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径
            max_age_hours: 缓存最大存活时间（小时）
            similarity_threshold: 近似匹配的相似度阈值 (0-1)
        """
        self.cache_dir = Path(cache_dir)
        self.max_age = timedelta(hours=max_age_hours)
        self.max_age_seconds = max_age_hours * 3600
        self.similarity_threshold = similarity_threshold
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_query(query: str) -> str:
        """
        标准化查询文本，用于相似度比较

        Args:
            query: 原始查询文本

        Returns:
            标准化后的查询文本
        """
        if not query:
            return ""

        # 纯 Python 实现
        normalized = query.lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = " ".join(normalized.split())
        return normalized

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度分数 (0-1)
        """
        if not text1 or not text2:
            return 0.0

        # 纯 Python 实现
        norm_text1 = self._normalize_query(text1)
        norm_text2 = self._normalize_query(text2)

        if norm_text1 == norm_text2:
            return 1.0

        return SequenceMatcher(None, norm_text1, norm_text2).ratio()

    @staticmethod
    def _generate_cache_key(tool_name: str, function_args: Dict[str, Any]) -> str:
        """
        生成缓存键

        Args:
            tool_name: 工具名称
            function_args: 函数参数

        Returns:
            缓存键字符串
        """
        # 将参数排序后序列化，确保相同参数产生相同的键
        sorted_args = json.dumps(function_args, sort_keys=True, ensure_ascii=False)

        # 纯 Python 实现
        cache_string = f"{tool_name}:{sorted_args}"
        return hashlib.md5(cache_string.encode("utf-8")).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_expired(self, cached_time: datetime) -> bool:
        """检查缓存是否过期"""
        return datetime.now() - cached_time > self.max_age

    def _find_similar_cache(
        self, tool_name: str, function_args: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        查找相似的缓存条目

        Args:
            tool_name: 工具名称
            function_args: 函数参数

        Returns:
            相似的缓存结果，如果不存在则返回None
        """
        query = function_args.get("query", "")
        if not query:
            return None

        candidates = []
        cache_data_list = []

        # 遍历所有缓存文件，收集候选项
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                # 检查是否是同一个工具
                if cache_data.get("tool_name") != tool_name:
                    continue

                # 检查缓存是否过期
                cached_time = datetime.fromisoformat(cache_data["timestamp"])
                if self._is_cache_expired(cached_time):
                    continue

                # 检查其他参数是否匹配（除了query）
                cached_args = cache_data.get("function_args", {})
                args_match = True
                for key, value in function_args.items():
                    if key != "query" and cached_args.get(key) != value:
                        args_match = False
                        break

                if not args_match:
                    continue

                # 收集候选项
                cached_query = cached_args.get("query", "")
                candidates.append((cached_query, len(cache_data_list)))
                cache_data_list.append(cache_data)

            except Exception as e:
                logger.warning(f"检查缓存文件时出错: {cache_file}, 错误: {e}")
                continue

        if not candidates:
            logger.debug(
                f"未找到相似缓存: {tool_name}, 查询: '{query}'，相似度阈值: {self.similarity_threshold}"
            )
            return None

        # 纯 Python 实现
        best_match = None
        best_similarity = 0.0

        for cached_query, index in candidates:
            similarity = self._calculate_similarity(query, cached_query)
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = cache_data_list[index]

        if best_match is not None:
            cached_query = best_match["function_args"].get("query", "")
            logger.info(
                f"相似缓存命中，相似度: {best_similarity:.2f}, 原查询: '{cached_query}', 当前查询: '{query}'"
            )
            return best_match["result"]

        logger.debug(
            f"未找到相似缓存: {tool_name}, 查询: '{query}'，相似度阈值: {self.similarity_threshold}"
        )
        return None

    def get(
        self, tool_name: str, function_args: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        从缓存获取结果，支持精确匹配和近似匹配

        Args:
            tool_name: 工具名称
            function_args: 函数参数

        Returns:
            缓存的结果，如果不存在或已过期则返回None
        """
        # 首先尝试精确匹配
        cache_key = self._generate_cache_key(tool_name, function_args)
        cache_file = self._get_cache_file_path(cache_key)

        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                # 检查缓存是否过期
                cached_time = datetime.fromisoformat(cache_data["timestamp"])
                if self._is_cache_expired(cached_time):
                    logger.debug(f"缓存已过期: {cache_key}")
                    cache_file.unlink()  # 删除过期缓存
                else:
                    logger.debug(f"精确匹配缓存: {tool_name}")
                    return cache_data["result"]

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"读取缓存文件失败: {cache_file}, 错误: {e}")
                # 删除损坏的缓存文件
                if cache_file.exists():
                    cache_file.unlink()

        # 如果精确匹配失败，尝试近似匹配
        return self._find_similar_cache(tool_name, function_args)

    def set(
        self, tool_name: str, function_args: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        """
        将结果保存到缓存

        Args:
            tool_name: 工具名称
            function_args: 函数参数
            result: 缓存结果
        """
        cache_key = self._generate_cache_key(tool_name, function_args)
        cache_file = self._get_cache_file_path(cache_key)

        cache_data = {
            "tool_name": tool_name,
            "function_args": function_args,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"缓存已保存: {tool_name} -> {cache_key}")
        except Exception as e:
            logger.error(f"保存缓存失败: {cache_file}, 错误: {e}")

    def clear_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            删除的文件数量
        """
        removed_count = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                cached_time = datetime.fromisoformat(cache_data["timestamp"])
                if self._is_cache_expired(cached_time):
                    cache_file.unlink()
                    removed_count += 1
                    logger.debug(f"删除过期缓存: {cache_file}")

            except Exception as e:
                logger.warning(f"清理缓存文件时出错: {cache_file}, 错误: {e}")
                # 删除损坏的文件
                try:
                    cache_file.unlink()
                    removed_count += 1
                except (OSError, json.JSONDecodeError, KeyError, ValueError):
                    logger.warning(f"删除损坏的缓存文件失败: {cache_file}, 错误: {e}")

        logger.info(f"清理完成，删除了 {removed_count} 个过期缓存文件")
        return removed_count

    def clear_all(self) -> int:
        """
        清空所有缓存

        Returns:
            删除的文件数量
        """
        removed_count = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                removed_count += 1
            except Exception as e:
                logger.warning(f"删除缓存文件失败: {cache_file}, 错误: {e}")

        logger.info(f"清空缓存完成，删除了 {removed_count} 个文件")
        return removed_count

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息字典
        """
        total_files = 0
        expired_files = 0
        total_size = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                total_files += 1
                total_size += cache_file.stat().st_size

                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                cached_time = datetime.fromisoformat(cache_data["timestamp"])
                if self._is_cache_expired(cached_time):
                    expired_files += 1

            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                expired_files += 1  # 损坏的文件也算作过期

        return {
            "total_files": total_files,
            "expired_files": expired_files,
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
            "max_age_hours": self.max_age.total_seconds() / 3600,
            "similarity_threshold": self.similarity_threshold,
        }

tool_cache = ToolCache()