# -*- coding: utf-8 -*-
"""
发送说说命令组件
"""
from typing import Tuple

from src.common.logger import get_logger
from src.plugin_system import BaseCommand
from ..services.manager import get_qzone_service, get_config_getter

logger = get_logger("MaiZone.SendFeedCommand")


class SendFeedCommand(BaseCommand):
    """
    响应用户通过 `/send_feed` 命令发送说说的请求。
    """
    command_name: str = "send_feed"
    command_description: str = "发送一条QQ空间说说"
    command_pattern: str = r"^/send_feed(?:\s+(?P<topic>.*))?$"
    command_help: str = "使用 /send_feed [主题] 来发送一条说说"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _check_permission(self) -> bool:
        """检查当前用户是否有权限执行此命令"""
        user_id = self.message.message_info.user_info.user_id
        if not user_id:
            return False

        get_config = get_config_getter()
        permission_list = get_config("send.permission", [])
        permission_type = get_config("send.permission_type", "whitelist")

        if not isinstance(permission_list, list):
            return False

        if permission_type == 'whitelist':
            return user_id in permission_list
        elif permission_type == 'blacklist':
            return user_id not in permission_list
        return False

    async def execute(self) -> Tuple[bool, str, bool]:
        """
        执行命令的核心逻辑。
        """
        if not self._check_permission():
            await self.send_text("抱歉，你没有权限使用这个命令哦。")
            return False, "权限不足", True

        topic = self.matched_groups.get("topic", "")
        stream_id = self.message.chat_stream.stream_id

        await self.send_text(f"收到！正在为你生成关于“{topic or '随机'}”的说说，请稍候...")

        try:
            qzone_service = get_qzone_service()
            result = await qzone_service.send_feed(topic, stream_id)

            if result.get("success"):
                reply_message = f"已经成功发送说说：\n{result.get('message', '')}"
                get_config = get_config_getter()
                if get_config("send.enable_reply", True):
                    await self.send_text(reply_message)
                return True, "发送成功", True
            else:
                await self.send_text(f"哎呀，发送失败了：{result.get('message', '未知错误')}")
                return False, result.get('message', '未知错误'), True

        except Exception as e:
            logger.error(f"执行发送说说命令时发生未知异常: {e}", exc_info=True)
            await self.send_text("呜... 发送过程中好像出了点问题。")
            return False, "命令执行异常", True