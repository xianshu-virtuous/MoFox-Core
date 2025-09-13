"""
PlanExecutor: 接收 Plan 对象并执行其中的所有动作。
"""
from src.chat.planner_actions.action_manager import ActionManager
from src.common.data_models.info_data_model import Plan
from src.common.logger import get_logger

logger = get_logger("plan_executor")


class PlanExecutor:
    """
    执行 Plan 中最终确定的动作。
    """

    def __init__(self, action_manager: ActionManager):
        self.action_manager = action_manager

    async def execute(self, plan: Plan):
        """
        读取 Plan 对象的 decided_actions 字段并执行。
        """
        if not plan.decided_actions:
            logger.info("没有需要执行的动作。")
            return

        for action_info in plan.decided_actions:
            if action_info.action_type == "no_action":
                logger.info(f"规划器决策不执行动作，原因: {action_info.reasoning}")
                continue

            # TODO: 对接 ActionManager 的执行方法
            # 这是一个示例调用，需要根据 ActionManager 的最终实现进行调整
            logger.info(f"执行动作: {action_info.action_type}, 原因: {action_info.reasoning}")
            # await self.action_manager.execute_action(
            #     action_name=action_info.action_type,
            #     action_data=action_info.action_data,
            #     reasoning=action_info.reasoning,
            #     action_message=action_info.action_message,
            # )
