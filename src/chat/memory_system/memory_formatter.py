# -*- coding: utf-8 -*-
"""
记忆格式化器
将召回的记忆转化为LLM友好的Markdown格式
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from src.common.logger import get_logger
from src.chat.memory_system.memory_chunk import MemoryChunk, MemoryType

logger = get_logger(__name__)


@dataclass
class FormatterConfig:
    """格式化器配置"""
    include_timestamps: bool = True      # 是否包含时间信息
    include_memory_types: bool = True    # 是否包含记忆类型
    include_confidence: bool = False     # 是否包含置信度信息
    max_display_length: int = 200       # 单条记忆最大显示长度
    datetime_format: str = "%Y年%m月%d日" # 时间格式
    use_emoji_icons: bool = True         # 是否使用emoji图标
    group_by_type: bool = False          # 是否按类型分组
    use_bracket_format: bool = False     # 是否使用方括号格式 [类型] 内容
    compact_format: bool = False         # 是否使用紧凑格式


class MemoryFormatter:
    """记忆格式化器 - 将记忆转化为提示词友好的格式"""
    
    # 记忆类型对应的emoji图标
    TYPE_EMOJI_MAP = {
        MemoryType.PERSONAL_FACT: "👤",
        MemoryType.EVENT: "📅",
        MemoryType.PREFERENCE: "❤️",
        MemoryType.OPINION: "💭",
        MemoryType.RELATIONSHIP: "👥",
        MemoryType.EMOTION: "😊",
        MemoryType.KNOWLEDGE: "📚",
        MemoryType.SKILL: "🛠️",
        MemoryType.GOAL: "🎯",
        MemoryType.EXPERIENCE: "🌟",
        MemoryType.CONTEXTUAL: "💬"
    }
    
    # 记忆类型的中文标签 - 优化格式
    TYPE_LABELS = {
        MemoryType.PERSONAL_FACT: "个人事实",
        MemoryType.EVENT: "事件",
        MemoryType.PREFERENCE: "偏好",
        MemoryType.OPINION: "观点",
        MemoryType.RELATIONSHIP: "关系",
        MemoryType.EMOTION: "情感",
        MemoryType.KNOWLEDGE: "知识",
        MemoryType.SKILL: "技能",
        MemoryType.GOAL: "目标",
        MemoryType.EXPERIENCE: "经验",
        MemoryType.CONTEXTUAL: "上下文"
    }
    
    def __init__(self, config: Optional[FormatterConfig] = None):
        self.config = config or FormatterConfig()
    
    def format_memories_for_prompt(
        self,
        memories: List[MemoryChunk],
        query_context: Optional[str] = None
    ) -> str:
        """
        将记忆列表格式化为LLM提示词
        
        Args:
            memories: 记忆列表
            query_context: 查询上下文（可选）
            
        Returns:
            格式化的Markdown文本
        """
        if not memories:
            return ""
        
        lines = ["## 🧠 相关记忆回顾", ""]
        
        if query_context:
            lines.extend([
                f"*查询上下文: {query_context}*",
                ""
            ])
        
        if self.config.group_by_type:
            lines.extend(self._format_memories_by_type(memories))
        else:
            lines.extend(self._format_memories_chronologically(memories))
        
        return "\n".join(lines)
    
    def _format_memories_by_type(self, memories: List[MemoryChunk]) -> List[str]:
        """按类型分组格式化记忆"""
        # 按类型分组
        grouped_memories = {}
        for memory in memories:
            memory_type = memory.memory_type
            if memory_type not in grouped_memories:
                grouped_memories[memory_type] = []
            grouped_memories[memory_type].append(memory)
        
        lines = []
        
        # 为每个类型生成格式化文本
        for memory_type, type_memories in grouped_memories.items():
            emoji = self.TYPE_EMOJI_MAP.get(memory_type, "📝")
            label = self.TYPE_LABELS.get(memory_type, memory_type.value)
            
            lines.extend([
                f"### {emoji} {label}",
                ""
            ])
            
            for memory in type_memories:
                formatted_item = self._format_single_memory(memory, include_type=False)
                lines.append(formatted_item)
            
            lines.append("")  # 类型间空行
        
        return lines
    
    def _format_memories_chronologically(self, memories: List[MemoryChunk]) -> List[str]:
        """按时间顺序格式化记忆"""
        lines = []
        
        for i, memory in enumerate(memories, 1):
            formatted_item = self._format_single_memory(memory, include_type=True, index=i)
            lines.append(formatted_item)
        
        return lines
    
    def _format_single_memory(
        self,
        memory: MemoryChunk,
        include_type: bool = True,
        index: Optional[int] = None
    ) -> str:
        """格式化单条记忆"""
        # 如果启用方括号格式，使用新格式
        if self.config.use_bracket_format:
            return self._format_single_memory_bracket(memory)

        # 获取显示文本
        display_text = memory.display or memory.text_content
        if len(display_text) > self.config.max_display_length:
            display_text = display_text[:self.config.max_display_length - 3] + "..."

        # 构建前缀
        prefix_parts = []

        # 添加序号
        if index is not None:
            prefix_parts.append(f"{index}.")

        # 添加类型标签
        if include_type and self.config.include_memory_types:
            if self.config.use_emoji_icons:
                emoji = self.TYPE_EMOJI_MAP.get(memory.memory_type, "📝")
                prefix_parts.append(f"**{emoji}")
            else:
                label = self.TYPE_LABELS.get(memory.memory_type, memory.memory_type.value)
                prefix_parts.append(f"**[{label}]")

        # 添加时间信息
        if self.config.include_timestamps:
            timestamp = memory.metadata.created_at
            if timestamp > 0:
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime(self.config.datetime_format)
                if self.config.use_emoji_icons:
                    prefix_parts.append(f"⏰ {time_str}")
                else:
                    prefix_parts.append(f"({time_str})")

        # 添加置信度信息
        if self.config.include_confidence:
            confidence = memory.metadata.confidence.value
            confidence_stars = "★" * confidence + "☆" * (4 - confidence)
            prefix_parts.append(f"信度:{confidence_stars}")

        # 构建完整格式
        if prefix_parts:
            if self.config.include_memory_types and self.config.use_emoji_icons:
                prefix = " ".join(prefix_parts) + "** "
            else:
                prefix = " ".join(prefix_parts) + " "
            return f"- {prefix}{display_text}"
        else:
            return f"- {display_text}"

    def _format_single_memory_bracket(self, memory: MemoryChunk) -> str:
        """格式化单条记忆 - 使用方括号格式 [类型] 内容"""
        # 获取显示文本
        display_text = memory.display or memory.text_content

        # 如果启用紧凑格式，只显示核心内容
        if self.config.compact_format:
            if len(display_text) > self.config.max_display_length:
                display_text = display_text[:self.config.max_display_length - 3] + "..."
        else:
            # 非紧凑格式可以包含时间信息
            if self.config.include_timestamps:
                timestamp = memory.metadata.created_at
                if timestamp > 0:
                    dt = datetime.fromtimestamp(timestamp)
                    time_str = dt.strftime("%Y年%m月%d日")
                    # 将时间信息自然地整合到内容中
                    if "在" not in display_text and "当" not in display_text:
                        display_text = f"在{time_str}，{display_text}"

        # 获取类型标签
        label = self.TYPE_LABELS.get(memory.memory_type, memory.memory_type.value)

        # 构建方括号格式: **[类型]** 内容
        return f"- **[{label}]** {display_text}"
    
    def format_memory_summary(self, memories: List[MemoryChunk]) -> str:
        """生成记忆摘要统计"""
        if not memories:
            return "暂无相关记忆。"
        
        # 统计信息
        total_count = len(memories)
        type_counts = {}
        
        for memory in memories:
            memory_type = memory.memory_type
            type_counts[memory_type] = type_counts.get(memory_type, 0) + 1
        
        # 生成摘要
        lines = [f"**记忆摘要**: 共找到 {total_count} 条相关记忆"]
        
        if len(type_counts) > 1:
            type_summaries = []
            for memory_type, count in type_counts.items():
                emoji = self.TYPE_EMOJI_MAP.get(memory_type, "📝")
                label = self.TYPE_LABELS.get(memory_type, memory_type.value)
                type_summaries.append(f"{emoji}{label} {count}条")
            
            lines.append(f"包括: {', '.join(type_summaries)}")
        
        return " | ".join(lines)
    
    def format_for_debug(self, memories: List[MemoryChunk]) -> str:
        """生成调试格式的记忆列表"""
        if not memories:
            return "无记忆数据"
        
        lines = ["### 记忆调试信息", ""]
        
        for i, memory in enumerate(memories, 1):
            lines.extend([
                f"**记忆 {i}** (ID: {memory.memory_id[:8]})",
                f"- 类型: {memory.memory_type.value}",
                f"- 内容: {memory.display[:100]}{'...' if len(memory.display) > 100 else ''}",
                f"- 访问次数: {memory.metadata.access_count}",
                f"- 置信度: {memory.metadata.confidence.value}/4",
                f"- 重要性: {memory.metadata.importance.value}/4",
                f"- 创建时间: {datetime.fromtimestamp(memory.metadata.created_at).strftime('%Y-%m-%d %H:%M')}",
                ""
            ])
        
        return "\n".join(lines)


# 创建默认格式化器实例
default_formatter = MemoryFormatter()


def format_memories_for_llm(
    memories: List[MemoryChunk],
    query_context: Optional[str] = None,
    config: Optional[FormatterConfig] = None
) -> str:
    """
    便捷函数：将记忆格式化为LLM提示词
    """
    if config:
        formatter = MemoryFormatter(config)
    else:
        formatter = default_formatter
    
    return formatter.format_memories_for_prompt(memories, query_context)


def format_memory_summary(
    memories: List[MemoryChunk],
    config: Optional[FormatterConfig] = None
) -> str:
    """
    便捷函数：生成记忆摘要
    """
    if config:
        formatter = MemoryFormatter(config)
    else:
        formatter = default_formatter

    return formatter.format_memory_summary(memories)


def format_memories_bracket_style(
    memories: List[MemoryChunk],
    query_context: Optional[str] = None,
    compact: bool = True,
    include_timestamps: bool = True
) -> str:
    """
    便捷函数：使用方括号格式格式化记忆

    Args:
        memories: 记忆列表
        query_context: 查询上下文
        compact: 是否使用紧凑格式
        include_timestamps: 是否包含时间信息

    Returns:
        格式化的Markdown文本
    """
    config = FormatterConfig(
        use_bracket_format=True,
        compact_format=compact,
        include_timestamps=include_timestamps,
        include_memory_types=True,
        use_emoji_icons=False,
        group_by_type=False
    )

    formatter = MemoryFormatter(config)
    return formatter.format_memories_for_prompt(memories, query_context)