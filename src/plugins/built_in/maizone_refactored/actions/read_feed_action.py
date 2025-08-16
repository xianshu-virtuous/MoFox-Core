# -*- coding: utf-8 -*-
"""
阅读说说动作组件
"""
from typing import Tuple

from src.common.logger import get_logger
from src.plugin_system import BaseAction, ActionActivationType, ChatMode
from src.plugin_system.apis import person_api, generator_api
from ..services.manager import get_qzone_service, get_config_getter

logger = get_logger("MaiZone.ReadFeedAction")


class ReadFeedAction(BaseAction):
    """
    当检测到用户想要阅读好友动态时，此动作被激活。
    """
    action_name: str = "read_feed"
    action_description: str = "读取好友的最新动态并进行评论点赞"
    activation_type: ActionActivationType = ActionActivationType.KEYWORD
    mode_enable: ChatMode = ChatMode.ALL
    activation_keywords: list = ["看说说", "看空间", "看动态", "刷空间"]

    action_parameters = {
        "target_name": "需要阅读动态的好友的昵称",
        "user_name": "请求你阅读动态的好友的昵称",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _check_permission(self) -> bool:
        """检查当前用户是否有权限执行此动作"""
        user_name = self.action_data.get("user_name", "")
        person_id = person_api.get_person_id_by_name(user_name)
        if not person_id:
            return False
        
        user_id = await person_api.get_person_value(person_id, "user_id")
        if not user_id:
            return False

        get_config = get_config_getter()
        permission_list = get_config("read.permission", [])
        permission_type = get_config("read.permission_type", "blacklist")

        if not isinstance(permission_list, list):
            return False

        if permission_type == 'whitelist':
            return user_id in permission_list
        elif permission_type == 'blacklist':
            return user_id not in permission_list
        return False

    async def execute(self) -> Tuple[bool, str]:
        """
        执行动作的核心逻辑。
        """
        if not await self._check_permission():
            _, reply_set, _ = await generator_api.generate_reply(
                chat_stream=self.chat_stream,
                action_data={"extra_info_block": "无权命令你阅读说说，请用符合你人格特点的方式拒绝请求"}
            )
            if reply_set and isinstance(reply_set, list):
                for reply_type, reply_content in reply_set:
                    if reply_type == "text":
                        await self.send_text(reply_content)
            return False, "权限不足"

        target_name = self.action_data.get("target_name", "")
        if not target_name:
            await self.send_text("你需要告诉我你想看谁的空间哦。")
            return False, "缺少目标用户"

        await self.send_text(f"好哦，我这就去看看'{target_name}'最近发了什么。")

        try:
            qzone_service = get_qzone_service()
            stream_id = self.chat_stream.stream_id
            result = await qzone_service.read_and_process_feeds(target_name, stream_id)

            if result.get("success"):
                _, reply_set, _ = await generator_api.generate_reply(
                    chat_stream=self.chat_stream,
                    action_data={"extra_info_block": f"你刚刚看完了'{target_name}'的空间，并进行了互动。{result.get('message', '')}"}
                )
                if reply_set and isinstance(reply_set, list):
                    for reply_type, reply_content in reply_set:
                        if reply_type == "text":
                            await self.send_text(reply_content)
                return True, "阅读成功"
            else:
                await self.send_text(f"看'{target_name}'的空间时好像失败了：{result.get('message', '未知错误')}")
                return False, result.get('message', '未知错误')
        
        except Exception as e:
            logger.error(f"执行阅读说说动作时发生未知异常: {e}", exc_info=True)
            await self.send_text("糟糕，在看说说的过程中网络好像出问题了...")
            return False, "动作执行异常"