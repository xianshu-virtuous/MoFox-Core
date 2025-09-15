"""
主规划器入口，负责协调 PlanGenerator, PlanFilter, 和 PlanExecutor。
集成兴趣度评分系统和用户关系追踪机制，实现智能化的聊天决策。
"""
import time
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from src.chat.planner_actions.action_manager import ActionManager
from src.chat.planner_actions.plan_executor import PlanExecutor
from src.chat.planner_actions.plan_filter import PlanFilter
from src.chat.planner_actions.plan_generator import PlanGenerator
from src.chat.affinity_flow.interest_scoring import InterestScoringSystem
from src.chat.affinity_flow.relationship_tracker import UserRelationshipTracker
from src.common.data_models.info_data_model import Plan
from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system.base.component_types import ChatMode
import src.chat.planner_actions.planner_prompts #noga  # noqa: F401
# 导入提示词模块以确保其被初始化

logger = get_logger("planner")




class ActionPlanner:
    """
    增强版ActionPlanner，集成兴趣度评分和用户关系追踪机制。

    核心功能：
    1. 兴趣度评分系统：根据兴趣匹配度、关系分、提及度、时间因子对消息评分
    2. 用户关系追踪：自动追踪用户交互并更新关系分
    3. 智能回复决策：基于兴趣度阈值和连续不回复概率的智能决策
    4. 完整的规划流程：生成→筛选→执行的完整三阶段流程
    """

    def __init__(self, chat_id: str, action_manager: ActionManager):
        """
        初始化增强版ActionPlanner。

        Args:
            chat_id (str): 当前聊天的 ID。
            action_manager (ActionManager): 一个 ActionManager 实例。
        """
        self.chat_id = chat_id
        self.action_manager = action_manager
        self.generator = PlanGenerator(chat_id)
        self.filter = PlanFilter()
        self.executor = PlanExecutor(action_manager)

        # 初始化兴趣度评分系统
        self.interest_scoring = InterestScoringSystem()

        # 初始化用户关系追踪器
        self.relationship_tracker = UserRelationshipTracker(self.interest_scoring)

        # 设置执行器的关系追踪器
        self.executor.set_relationship_tracker(self.relationship_tracker)

        # 规划器统计
        self.planner_stats = {
            "total_plans": 0,
            "successful_plans": 0,
            "failed_plans": 0,
            "replies_generated": 0,
            "other_actions_executed": 0,
        }

    async def plan(self, mode: ChatMode = ChatMode.FOCUS, use_enhanced: bool = True) -> Tuple[List[Dict], Optional[Dict]]:
        """
        执行完整的增强版规划流程。

        Args:
            mode (ChatMode): 当前的聊天模式，默认为 FOCUS。
            use_enhanced (bool): 是否使用增强功能，默认为 True。

        Returns:
            Tuple[List[Dict], Optional[Dict]]: 一个元组，包含：
                - final_actions_dict (List[Dict]): 最终确定的动作列表（字典格式）。
                - final_target_message_dict (Optional[Dict]): 最终的目标消息（字典格式）。
        """
        try:
            self.planner_stats["total_plans"] += 1

            if use_enhanced:
                return await self._enhanced_plan_flow(mode)
            else:
                return await self._standard_plan_flow(mode)

        except Exception as e:
            logger.error(f"规划流程出错: {e}")
            self.planner_stats["failed_plans"] += 1
            return [], None

    async def _enhanced_plan_flow(self, mode: ChatMode) -> Tuple[List[Dict], Optional[Dict]]:
        """执行增强版规划流程"""
        try:
            # 1. 生成初始 Plan
            initial_plan = await self.generator.generate(mode)

            # 2. 兴趣度评分
            if initial_plan.chat_history:
                bot_nickname = global_config.bot.nickname
                interest_scores = self.interest_scoring.calculate_interest_scores(
                    initial_plan.chat_history, bot_nickname
                )

                # 3. 根据兴趣度调整可用动作
                if interest_scores:
                    latest_score = max(interest_scores, key=lambda s: s.total_score)
                    should_reply = self.interest_scoring.should_reply(latest_score)

                    if not should_reply and "reply" in initial_plan.available_actions:
                        logger.info(f"消息兴趣度不足({latest_score.total_score:.2f})，移除reply动作")
                        del initial_plan.available_actions["reply"]
                        self.interest_scoring.record_reply_action(False)
                    else:
                        self.interest_scoring.record_reply_action(True)

            # 4. 筛选 Plan
            filtered_plan = await self.filter.filter(initial_plan)

            # 5. 执行 Plan
            await self._execute_plan_with_tracking(filtered_plan)

            # 6. 检查关系更新
            await self.relationship_tracker.check_and_update_relationships()

            # 7. 返回结果
            return self._build_return_result(filtered_plan)

        except Exception as e:
            logger.error(f"增强版规划流程出错: {e}")
            self.planner_stats["failed_plans"] += 1
            return [], None

    async def _standard_plan_flow(self, mode: ChatMode) -> Tuple[List[Dict], Optional[Dict]]:
        """执行标准规划流程"""
        try:
            # 1. 生成初始 Plan
            initial_plan = await self.generator.generate(mode)

            # 2. 筛选 Plan
            filtered_plan = await self.filter.filter(initial_plan)

            # 3. 执行 Plan
            await self._execute_plan_with_tracking(filtered_plan)

            # 4. 返回结果
            return self._build_return_result(filtered_plan)

        except Exception as e:
            logger.error(f"标准规划流程出错: {e}")
            self.planner_stats["failed_plans"] += 1
            return [], None

    async def _execute_plan_with_tracking(self, plan: Plan):
        """执行Plan并追踪用户关系"""
        if not plan.decided_actions:
            return

        for action_info in plan.decided_actions:
            if action_info.action_type in ["reply", "proactive_reply"] and action_info.action_message:
                # 记录用户交互
                self.relationship_tracker.add_interaction(
                    user_id=action_info.action_message.user_id,
                    user_name=action_info.action_message.user_nickname or action_info.action_message.user_id,
                    user_message=action_info.action_message.content,
                    bot_reply="Bot回复内容",  # 这里需要实际的回复内容
                    reply_timestamp=time.time()
                )

            # 执行动作
            try:
                await self.action_manager.execute_action(
                    action_name=action_info.action_type,
                    chat_id=self.chat_id,
                    target_message=action_info.action_message,
                    reasoning=action_info.reasoning,
                    action_data=action_info.action_data or {},
                )

                self.planner_stats["successful_plans"] += 1
                if action_info.action_type in ["reply", "proactive_reply"]:
                    self.planner_stats["replies_generated"] += 1
                else:
                    self.planner_stats["other_actions_executed"] += 1

            except Exception as e:
                logger.error(f"执行动作失败: {action_info.action_type}, 错误: {e}")

    def _build_return_result(self, plan: Plan) -> Tuple[List[Dict], Optional[Dict]]:
        """构建返回结果"""
        final_actions = plan.decided_actions or []
        final_target_message = next(
            (act.action_message for act in final_actions if act.action_message), None
        )

        final_actions_dict = [asdict(act) for act in final_actions]

        if final_target_message:
            if hasattr(final_target_message, '__dataclass_fields__'):
                final_target_message_dict = asdict(final_target_message)
            else:
                final_target_message_dict = final_target_message
        else:
            final_target_message_dict = None

        return final_actions_dict, final_target_message_dict

    def get_user_relationship(self, user_id: str) -> float:
        """获取用户关系分"""
        return self.interest_scoring.get_user_relationship(user_id)

    def update_interest_keywords(self, new_keywords: Dict[str, List[str]]):
        """更新兴趣关键词"""
        self.interest_scoring.interest_keywords.update(new_keywords)
        logger.info(f"已更新兴趣关键词: {list(new_keywords.keys())}")

    def get_planner_stats(self) -> Dict[str, any]:
        """获取规划器统计"""
        return self.planner_stats.copy()

    def get_interest_scoring_stats(self) -> Dict[str, any]:
        """获取兴趣度评分统计"""
        return {
            "no_reply_count": self.interest_scoring.no_reply_count,
            "max_no_reply_count": self.interest_scoring.max_no_reply_count,
            "reply_threshold": self.interest_scoring.reply_threshold,
            "mention_threshold": self.interest_scoring.mention_threshold,
            "user_relationships": len(self.interest_scoring.user_relationships),
        }

    def get_relationship_stats(self) -> Dict[str, any]:
        """获取用户关系统计"""
        return {
            "tracking_users": len(self.relationship_tracker.tracking_users),
            "relationship_history": len(self.relationship_tracker.relationship_history),
            "max_tracking_users": self.relationship_tracker.max_tracking_users,
        }


# 全局兴趣度评分系统实例
interest_scoring_system = InterestScoringSystem()