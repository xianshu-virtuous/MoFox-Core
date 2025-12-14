# mmc/src/schedule/schedule_context.py

"""
日程上下文管理器

负责将日程信息以合适的方式提供给对话系统，而不强制Bot提及日程。
这个模块的核心目标是让日程成为"可选的背景信息"而非"强制的话题"。

主要功能：
1. 判断何时应该在对话中包含日程信息
2. 为LLM构建适当的日程上下文
3. 生成格式化的系统提示词
4. 控制日程提及的频率和方式

使用方式：
    from src.schedule.schedule_manager import schedule_manager
    from src.schedule.schedule_context import ScheduleContextManager
    
    # 创建上下文管理器
    context_mgr = ScheduleContextManager(schedule_manager)
    
    # 构建上下文
    context = context_mgr.build_context_for_llm(user_query="你在做什么？")
    
    # 获取系统提示词
    hint = context_mgr.format_schedule_hint_for_system_prompt(user_query)
"""

from datetime import datetime
from typing import Any

from src.common.logger import get_logger
from src.config.config import global_config

logger = get_logger("schedule_context")


class ScheduleContextManager:
    """
    管理日程如何被集成到对话上下文中。
    
    设计原则：
    - 默认情况下，不在对话中包含日程信息
    - 只在用户明确询问或需要时才提供日程
    - 即使提供日程，也强调其"参考性"而非"强制性"
    """
    
    def __init__(self, schedule_manager):
        """
        初始化上下文管理器。
        
        Args:
            schedule_manager: ScheduleManager 实例
        """
        self.schedule_manager = schedule_manager
        self.mention_mode = "passive"  # passive: 被动模式, active: 主动模式, hidden: 隐藏模式
        
        # 用户询问日程的关键词
        self.schedule_query_keywords = [
            "在做什么", "在干什么", "在干嘛", "现在做什么", "正在做什么",
            "日程", "计划", "安排", "忙吗", "有空吗", "在忙", "忙不忙",
            "schedule", "plan", "busy", "free", "doing what"
        ]
    
    def should_include_schedule_in_context(self, user_query: str = "") -> bool:
        """
        判断是否应该在当前对话中包含日程信息。
        
        Args:
            user_query (str): 用户的查询内容
            
        Returns:
            bool: 是否应该包含日程
        """
        if not user_query:
            return False
        
        # 检查用户是否主动询问日程相关内容
        user_query_lower = user_query.lower()
        if any(keyword in user_query_lower for keyword in self.schedule_query_keywords):
            logger.debug(f"检测到用户询问日程相关内容: {user_query[:30]}...")
            return True
        
        # 根据配置决定是否自动包含
        auto_include = getattr(
            global_config.planning_system,
            "auto_include_schedule_in_context",
            False  # 默认不自动包含
        )
        
        if auto_include:
            logger.debug("配置启用了自动包含日程")
            return True
        
        return False
    
    def build_context_for_llm(
        self, 
        user_query: str = "",
        force_include: bool = False,
        detail_level: str = "brief"
    ) -> dict[str, Any]:
        """
        为LLM构建包含日程信息的上下文。
        
        Args:
            user_query (str): 用户查询
            force_include (bool): 是否强制包含日程
            detail_level (str): 详细程度
                - "brief": 简要模式，只提供当前活动
                - "normal": 正常模式，提供当前活动和时间
                - "detailed": 详细模式，包含完整日程
            
        Returns:
            dict: 包含日程上下文的字典
                - has_schedule: 是否有日程信息
                - current_activity: 当前活动详情
                - schedule_text: 格式化的日程文本
                - should_mention: 是否应该在对话中提及
        """
        context = {
            "has_schedule": False,
            "current_activity": None,
            "schedule_text": "",
            "should_mention": False
        }
        
        if not global_config.planning_system.schedule_enable:
            logger.debug("日程系统未启用")
            return context
        
        # 判断是否应该包含日程
        should_include = force_include or self.should_include_schedule_in_context(user_query)
        
        if not should_include:
            logger.debug("不包含日程信息到对话上下文")
            return context
        
        # 获取当前活动
        current_activity = self.schedule_manager.get_current_activity(mode="reference")
        
        if not current_activity:
            logger.debug("当前没有可用的日程活动")
            return context
        
        context["has_schedule"] = True
        context["current_activity"] = current_activity
        
        # 根据详细程度构建文本
        if detail_level == "brief":
            # 简要模式：只提供当前活动
            activity = current_activity.get("activity", "")
            context["schedule_text"] = f"背景：原定为 {activity}（仅供参考，可灵活调整）"
            context["should_mention"] = False
            
        elif detail_level == "normal":
            # 正常模式：提供当前活动和时间
            activity = current_activity.get("activity", "")
            time_range = current_activity.get("time_range", "")
            is_temp = current_activity.get("is_temporary", False)
            
            if is_temp:
                reason = current_activity.get("reason", "")
                context["schedule_text"] = (
                    f"当前状态：{time_range} - {activity}\n"
                    f"（这是临时调整，原因：{reason}）"
                )
            else:
                context["schedule_text"] = (
                    f"日程参考：{time_range} - {activity}\n"
                    f"（这只是参考计划，你可以根据对话情况灵活调整）"
                )
            context["should_mention"] = self.schedule_manager.should_mention_schedule()
            
        elif detail_level == "detailed":
            # 详细模式：包含完整日程
            context["schedule_text"] = self.schedule_manager.get_schedule_context(verbose=True)
            context["should_mention"] = True
        
        logger.debug(f"构建日程上下文 (detail_level={detail_level}): {context['schedule_text'][:50]}...")
        return context
    
    def format_schedule_hint_for_system_prompt(
        self, 
        user_query: str = "",
        include_usage_guide: bool = True
    ) -> str:
        """
        为系统提示词生成日程提示信息。
        
        这个方法生成的文本可以直接添加到系统提示词中，
        为LLM提供日程背景信息和使用指导。
        
        Args:
            user_query (str): 用户查询
            include_usage_guide (bool): 是否包含使用指南
            
        Returns:
            str: 格式化的提示信息，如果不需要包含日程则返回空字符串
        """
        context = self.build_context_for_llm(user_query, detail_level="normal")
        
        if not context["has_schedule"]:
            return ""
        
        # 构建基础日程信息
        hint = f"""
## 📅 日程背景信息（可选参考）

{context['schedule_text']}
"""
        
        # 如果需要，添加使用指南
        if include_usage_guide:
            hint += """
**使用建议**:
- 这份日程仅作为你生活节奏的参考背景
- 不需要在每次对话中都提及你在做什么
- 只在以下情况考虑提及日程：
  1. 用户明确询问你在做什么或你的日程安排
  2. 用户的请求与你当前活动有明显冲突时（如你在休息时被要求做大量工作）
  3. 对话自然需要交代背景时（如解释为什么回复慢了）
- 大多数情况下，直接响应用户需求即可，无需强调日程

**灵活应对原则**:
如果用户的请求与日程冲突，你应该：
- 优先满足用户需求（临时调整日程）
- 或者友好地说明情况并提供替代方案
- 避免僵硬地说"我现在在XXX，不能XXX"

**自然对话示例**:
- ❌ 不好的回应："我现在正在学习时间，不太方便陪你玩游戏。"
- ✅ 好的回应："好呀！玩什么游戏？"
- ✅ 好的回应（如果确实在忙）："我现在在看点东西，不过可以暂停一下，想玩什么？"
"""
        
        return hint
    
    def get_schedule_summary(self) -> str:
        """
        获取日程的简要摘要，用于日志或调试。
        
        Returns:
            str: 日程摘要
        """
        activity = self.schedule_manager.get_current_activity(mode="reference")
        if not activity:
            return "无当前活动"
        
        activity_text = activity.get("activity", "未知")
        time_range = activity.get("time_range", "未知")
        is_temp = activity.get("is_temporary", False)
        
        if is_temp:
            return f"[临时] {time_range}: {activity_text}"
        else:
            return f"{time_range}: {activity_text}"
    
    def set_mention_mode(self, mode: str):
        """
        设置日程提及模式。
        
        Args:
            mode (str): 模式
                - "passive": 被动模式，只在被询问时提及（默认）
                - "active": 主动模式，适当主动提及
                - "hidden": 隐藏模式，完全不提及
        """
        if mode in ["passive", "active", "hidden"]:
            self.mention_mode = mode
            logger.info(f"日程提及模式已设置为: {mode}")
        else:
            logger.warning(f"无效的提及模式: {mode}，保持当前模式: {self.mention_mode}")


# 便捷函数：创建默认的上下文管理器
def create_schedule_context_manager():
    """
    创建默认的日程上下文管理器实例。
    
    Returns:
        ScheduleContextManager: 上下文管理器实例
    """
    from .schedule_manager import schedule_manager
    return ScheduleContextManager(schedule_manager)
