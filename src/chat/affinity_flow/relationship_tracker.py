"""
用户关系追踪器
负责追踪用户交互历史，并通过LLM分析更新用户关系分
"""
import time
from typing import Dict, List, Optional

from src.common.logger import get_logger
from src.config.config import model_config
from src.llm_models.utils_model import LLMRequest

logger = get_logger("relationship_tracker")


class UserRelationshipTracker:
    """用户关系追踪器"""

    def __init__(self, interest_scoring_system=None):
        self.tracking_users: Dict[str, Dict] = {}  # user_id -> interaction_data
        self.max_tracking_users = 3
        self.update_interval_minutes = 30
        self.last_update_time = time.time()
        self.relationship_history: List[Dict] = []
        self.interest_scoring_system = interest_scoring_system

        # 关系更新LLM
        try:
            self.relationship_llm = LLMRequest(
                model_set=model_config.model_task_config.relationship_tracker,
                request_type="relationship_tracker"
            )
        except AttributeError:
            # 如果relationship_tracker配置不存在，尝试其他可用的模型配置
            available_models = [attr for attr in dir(model_config.model_task_config)
                             if not attr.startswith('_') and attr != 'model_dump']

            if available_models:
                # 使用第一个可用的模型配置
                fallback_model = available_models[0]
                logger.warning(f"relationship_tracker model configuration not found, using fallback: {fallback_model}")
                self.relationship_llm = LLMRequest(
                    model_set=getattr(model_config.model_task_config, fallback_model),
                    request_type="relationship_tracker"
                )
            else:
                # 如果没有任何模型配置，创建一个简单的LLMRequest
                logger.warning("No model configurations found, creating basic LLMRequest")
                self.relationship_llm = LLMRequest(
                    model_set="gpt-3.5-turbo",  # 默认模型
                    request_type="relationship_tracker"
                )

    def set_interest_scoring_system(self, interest_scoring_system):
        """设置兴趣度评分系统引用"""
        self.interest_scoring_system = interest_scoring_system

    def add_interaction(self, user_id: str, user_name: str, user_message: str, bot_reply: str, reply_timestamp: float):
        """添加用户交互记录"""
        if len(self.tracking_users) >= self.max_tracking_users:
            # 移除最旧的记录
            oldest_user = min(self.tracking_users.keys(),
                            key=lambda k: self.tracking_users[k].get("reply_timestamp", 0))
            del self.tracking_users[oldest_user]

        # 获取当前关系分
        current_relationship_score = 0.3  # 默认值
        if self.interest_scoring_system:
            current_relationship_score = self.interest_scoring_system.get_user_relationship(user_id)

        self.tracking_users[user_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "user_message": user_message,
            "bot_reply": bot_reply,
            "reply_timestamp": reply_timestamp,
            "current_relationship_score": current_relationship_score
        }

        logger.debug(f"添加用户交互追踪: {user_id}")

    async def check_and_update_relationships(self) -> List[Dict]:
        """检查并更新用户关系"""
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval_minutes * 60:
            return []

        updates = []
        for user_id, interaction in list(self.tracking_users.items()):
            if current_time - interaction["reply_timestamp"] > 60 * 5:  # 5分钟
                update = await self._update_user_relationship(interaction)
                if update:
                    updates.append(update)
                    del self.tracking_users[user_id]

        self.last_update_time = current_time
        return updates

    async def _update_user_relationship(self, interaction: Dict) -> Optional[Dict]:
        """更新单个用户的关系"""
        try:
            prompt = f"""
分析以下用户交互，更新用户关系：

用户ID: {interaction['user_id']}
用户名: {interaction['user_name']}
用户消息: {interaction['user_message']}
Bot回复: {interaction['bot_reply']}
当前关系分: {interaction['current_relationship_score']}

请以JSON格式返回更新结果：
{{
    "new_relationship_score": 0.0~1.0的数值,
    "reasoning": "更新理由",
    "interaction_summary": "交互总结"
}}
"""

            llm_response, _ = await self.relationship_llm.generate_response_async(prompt=prompt)
            if llm_response:
                import json
                response_data = json.loads(llm_response)
                new_score = max(0.0, min(1.0, float(response_data.get("new_relationship_score", 0.3))))

                if self.interest_scoring_system:
                    self.interest_scoring_system.update_user_relationship(
                        interaction['user_id'],
                        new_score - interaction['current_relationship_score']
                    )

                return {
                    "user_id": interaction['user_id'],
                    "new_relationship_score": new_score,
                    "reasoning": response_data.get("reasoning", ""),
                    "interaction_summary": response_data.get("interaction_summary", "")
                }

        except Exception as e:
            logger.error(f"更新用户关系时出错: {e}")

        return None

    def get_tracking_users(self) -> Dict[str, Dict]:
        """获取正在追踪的用户"""
        return self.tracking_users.copy()

    def get_user_interaction(self, user_id: str) -> Optional[Dict]:
        """获取特定用户的交互记录"""
        return self.tracking_users.get(user_id)

    def remove_user_tracking(self, user_id: str):
        """移除用户追踪"""
        if user_id in self.tracking_users:
            del self.tracking_users[user_id]
            logger.debug(f"移除用户追踪: {user_id}")

    def clear_all_tracking(self):
        """清空所有追踪"""
        self.tracking_users.clear()
        logger.info("清空所有用户追踪")

    def get_relationship_history(self) -> List[Dict]:
        """获取关系历史记录"""
        return self.relationship_history.copy()

    def add_to_history(self, relationship_update: Dict):
        """添加到关系历史"""
        self.relationship_history.append({
            **relationship_update,
            "update_time": time.time()
        })

        # 限制历史记录数量
        if len(self.relationship_history) > 100:
            self.relationship_history = self.relationship_history[-100:]

    def get_tracker_stats(self) -> Dict:
        """获取追踪器统计"""
        return {
            "tracking_users": len(self.tracking_users),
            "max_tracking_users": self.max_tracking_users,
            "update_interval_minutes": self.update_interval_minutes,
            "relationship_history": len(self.relationship_history),
            "last_update_time": self.last_update_time,
        }

    def update_config(self, max_tracking_users: int = None, update_interval_minutes: int = None):
        """更新配置"""
        if max_tracking_users is not None:
            self.max_tracking_users = max_tracking_users
            logger.info(f"更新最大追踪用户数: {max_tracking_users}")

        if update_interval_minutes is not None:
            self.update_interval_minutes = update_interval_minutes
            logger.info(f"更新关系更新间隔: {update_interval_minutes} 分钟")

    def force_update_relationship(self, user_id: str, new_score: float, reasoning: str = ""):
        """强制更新用户关系分"""
        if user_id in self.tracking_users:
            current_score = self.tracking_users[user_id]["current_relationship_score"]
            if self.interest_scoring_system:
                self.interest_scoring_system.update_user_relationship(
                    user_id,
                    new_score - current_score
                )

            update_info = {
                "user_id": user_id,
                "new_relationship_score": new_score,
                "reasoning": reasoning or "手动更新",
                "interaction_summary": "手动更新关系分"
            }
            self.add_to_history(update_info)
            logger.info(f"强制更新用户关系: {user_id} -> {new_score:.2f}")

    def get_user_summary(self, user_id: str) -> Dict:
        """获取用户交互总结"""
        if user_id not in self.tracking_users:
            return {}

        interaction = self.tracking_users[user_id]
        return {
            "user_id": user_id,
            "user_name": interaction["user_name"],
            "current_relationship_score": interaction["current_relationship_score"],
            "interaction_count": 1,  # 简化版本，每次追踪只记录一次交互
            "last_interaction": interaction["reply_timestamp"],
            "recent_message": interaction["user_message"][:100] + "..." if len(interaction["user_message"]) > 100 else interaction["user_message"]
        }