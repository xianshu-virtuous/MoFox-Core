"""
PlanGenerator: 负责搜集和汇总所有决策所需的信息，生成一个未经筛选的“原始计划” (Plan)。
"""
import time
from typing import Dict, Optional, Tuple

from src.chat.utils.chat_message_builder import get_raw_msg_before_timestamp_with_chat
from src.chat.utils.utils import get_chat_type_and_target_info
from src.common.data_models.database_data_model import DatabaseMessages
from src.common.data_models.info_data_model import Plan, TargetPersonInfo
from src.config.config import global_config
from src.plugin_system.base.component_types import ActionInfo, ChatMode, ComponentType
from src.plugin_system.core.component_registry import component_registry


class PlanGenerator:
    """
    搜集信息并生成初始 Plan 对象。
    """

    def __init__(self, chat_id: str):
        from src.chat.planner_actions.action_manager import ActionManager
        self.chat_id = chat_id
        # 注意：ActionManager 可能需要根据实际情况初始化
        self.action_manager = ActionManager()

    async def generate(self, mode: ChatMode) -> Plan:
        """
        生成并填充初始的 Plan 对象。
        """
        _is_group_chat, chat_target_info_dict = get_chat_type_and_target_info(self.chat_id)
        
        target_info = None
        if chat_target_info_dict:
            target_info = TargetPersonInfo(**chat_target_info_dict)

        available_actions = self._get_available_actions()

        chat_history_raw = get_raw_msg_before_timestamp_with_chat(
            chat_id=self.chat_id,
            timestamp=time.time(),
            limit=int(global_config.chat.max_context_size),
        )
        chat_history = [DatabaseMessages(**msg) for msg in chat_history_raw]


        plan = Plan(
            chat_id=self.chat_id,
            mode=mode,
            available_actions=available_actions,
            chat_history=chat_history,
            target_info=target_info,
        )
        return plan

    def _get_available_actions(self) -> Dict[str, "ActionInfo"]:
        """
        获取当前可用的动作。
        """
        current_available_actions_dict = self.action_manager.get_using_actions()
        all_registered_actions: Dict[str, ActionInfo] = component_registry.get_components_by_type( # type: ignore
            ComponentType.ACTION
        )
        
        current_available_actions = {}
        for action_name in current_available_actions_dict:
            if action_name in all_registered_actions:
                current_available_actions[action_name] = all_registered_actions[action_name]

        no_reply_info = ActionInfo(
            name="no_reply",
            component_type=ComponentType.ACTION,
            description="系统级动作：选择不回复消息的决策",
            action_parameters={},
            activation_keywords=[],
            plugin_name="SYSTEM",
            enabled=True,
            parallel_action=False,
        )
        current_available_actions["no_reply"] = no_reply_info
        
        return current_available_actions