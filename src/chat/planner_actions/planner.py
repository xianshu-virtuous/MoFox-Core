"""
主规划器入口，负责协调 PlanGenerator, PlanFilter, 和 PlanExecutor。
"""
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from src.chat.planner_actions.action_manager import ActionManager
from src.chat.planner_actions.plan_executor import PlanExecutor
from src.chat.planner_actions.plan_filter import PlanFilter
from src.chat.planner_actions.plan_generator import PlanGenerator
from src.common.data_models.info_data_model import ActionPlannerInfo
from src.common.logger import get_logger
from src.plugin_system.base.component_types import ChatMode

# 导入提示词模块以确保其被初始化
from . import planner_prompts

logger = get_logger("planner")


class ActionPlanner:
    """
    协调器，按顺序调用 Generator -> Filter -> Executor。
    """

    def __init__(self, chat_id: str, action_manager: ActionManager):
        self.chat_id = chat_id
        self.action_manager = action_manager
        self.generator = PlanGenerator(chat_id)
        self.filter = PlanFilter()
        self.executor = PlanExecutor(action_manager)

    async def plan(
        self, mode: ChatMode = ChatMode.FOCUS
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """
        执行完整的规划流程。
        """
        # 1. 生成初始 Plan
        initial_plan = await self.generator.generate(mode)

        # 2. 筛选 Plan
        filtered_plan = await self.filter.filter(initial_plan)

        # 3. 执行 Plan
        await self.executor.execute(filtered_plan)

        # 4. 返回结果 (与旧版 planner 的返回值保持兼容)
        final_actions = filtered_plan.decided_actions or []
        final_target_message = next(
            (act.action_message for act in final_actions if act.action_message), None
        )
        
        final_actions_dict = [asdict(act) for act in final_actions]
        final_target_message_dict = asdict(final_target_message) if final_target_message else None

        return final_actions_dict, final_target_message_dict
