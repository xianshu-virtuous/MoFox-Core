"""
回复动作模块

定义了三种回复相关动作：
- reply: 针对单条消息的深度回复（使用 s4u 模板）
- respond: 对未读消息的统一回应（使用 normal 模板）
- no_reply: 选择不回复
"""

import asyncio
from typing import ClassVar

from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import ActionActivationType, BaseAction, ChatMode
from src.plugin_system.apis import database_api, generator_api, send_api

logger = get_logger("reply_actions")


class ReplyAction(BaseAction):
    """Reply动作 - 针对单条消息的深度回复
    
    特点：
    - 使用 s4u (Speak for You) 模板
    - 专注于理解和回应单条消息的具体内容
    - 适合 Focus 模式下的精准回复
    - 仅限 AffinityFlowChatter 使用
    """

    # 动作基本信息
    action_name = "reply"
    action_description = "针对特定消息进行精准回复。深度理解并回应单条消息的具体内容。需要指定目标消息ID。"

    # 激活设置
    activation_type = ActionActivationType.ALWAYS  # 回复动作总是可用
    mode_enable = ChatMode.ALL  # 在所有模式下都可用
    parallel_action = False  # 回复动作不能与其他动作并行
    
    # Chatter 限制：仅允许 AffinityFlowChatter 使用
    chatter_allow: ClassVar[list[str]] = ["AffinityFlowChatter"]

    # 动作参数定义
    action_parameters: ClassVar = {
        "target_message_id": "要回复的目标消息ID（必需，来自未读消息的 <m...> 标签）",
        "content": "回复的具体内容（可选，由LLM生成）",
        "should_quote_reply": "是否引用原消息（可选，true/false，默认false。群聊中回复较早消息或需要明确指向时使用true）",
    }

    # 动作使用场景
    action_require: ClassVar = [
        "需要针对特定消息进行精准回复时使用",
        "适合单条消息的深度理解和回应",
        "必须提供准确的 target_message_id（来自未读历史的 <m...> 标签）",
        "私聊场景必须使用此动作（不支持 respond）",
        "群聊中需要明确回应某个特定用户或问题时使用",
        "关注单条消息的具体内容和上下文细节",
    ]

    # 关联类型
    associated_types: ClassVar[list[str]] = ["text"]

    async def execute(self) -> tuple[bool, str]:
        """执行reply动作 - 完整的回复流程"""
        try:
            # 检查目标消息是否为表情包
            if self.action_message and getattr(self.action_message, "is_emoji", False):
                if not getattr(global_config.chat, "allow_reply_to_emoji", True):
                    logger.info(f"{self.log_prefix} 目标消息为表情包且配置不允许回复，跳过")
                    return True, ""
            
            # 准备 action_data
            action_data = self.action_data.copy()
            action_data["prompt_mode"] = "s4u"
            
            # 生成回复
            success, response_set, _ = await generator_api.generate_reply(
                chat_stream=self.chat_stream,
                reply_message=self.action_message,
                action_data=action_data,
                available_actions={self.action_name: None},
                enable_tool=global_config.tool.enable_tool,
                request_type="chat.replyer",
                from_plugin=False,
            )
            
            if not success or not response_set:
                logger.warning(f"{self.log_prefix} 回复生成失败")
                return False, ""
            
            # 发送回复
            reply_text = await self._send_response(response_set)
            
            # 存储动作信息
            await self._store_action_info(reply_text)
            
            logger.info(f"{self.log_prefix} reply 动作执行成功")
            return True, reply_text
            
        except asyncio.CancelledError:
            logger.debug(f"{self.log_prefix} 回复任务被取消")
            return False, ""
        except Exception as e:
            logger.error(f"{self.log_prefix} reply 动作执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False, ""
    
    async def _send_response(self, response_set) -> str:
        """发送回复内容"""
        reply_text = ""
        should_quote = self.action_data.get("should_quote_reply", False)
        first_sent = False
        
        for reply_seg in response_set:
            # 处理元组格式
            if isinstance(reply_seg, tuple) and len(reply_seg) >= 2:
                _, data = reply_seg
            else:
                data = str(reply_seg)
            
            if isinstance(data, list):
                data = "".join(map(str, data))
            
            reply_text += data
            
            # 发送消息
            if not first_sent:
                await send_api.text_to_stream(
                    text=data,
                    stream_id=self.chat_stream.stream_id,
                    reply_to_message=self.action_message,
                    set_reply=should_quote and bool(self.action_message),
                    typing=False,
                )
                first_sent = True
            else:
                await send_api.text_to_stream(
                    text=data,
                    stream_id=self.chat_stream.stream_id,
                    reply_to_message=None,
                    set_reply=False,
                    typing=True,
                )
        
        return reply_text
    
    async def _store_action_info(self, reply_text: str):
        """存储动作信息到数据库"""
        from src.person_info.person_info import get_person_info_manager
        
        person_info_manager = get_person_info_manager()
        
        if self.action_message:
            platform = self.action_message.chat_info.platform
            user_id = self.action_message.user_info.user_id
        else:
            platform = getattr(self.chat_stream, "platform", "unknown")
            user_id = ""
        
        person_id = person_info_manager.get_person_id(platform, user_id)
        person_name = await person_info_manager.get_value(person_id, "person_name")
        action_prompt_display = f"你对{person_name}进行了回复：{reply_text}"
        
        await database_api.store_action_info(
            chat_stream=self.chat_stream,
            action_build_into_prompt=False,
            action_prompt_display=action_prompt_display,
            action_done=True,
            thinking_id=self.thinking_id,
            action_data={"reply_text": reply_text},
            action_name="reply",
        )


class RespondAction(BaseAction):
    """Respond动作 - 对未读消息的统一回应
    
    特点：
    - 关注整体对话动态和未读消息的统一回应
    - 适合对于群聊消息下的宏观回应
    - 避免与单一用户深度对话而忽略其他用户的消息
    - 仅限 AffinityFlowChatter 使用
    """

    # 动作基本信息
    action_name = "respond"
    action_description = "统一回应所有未读消息。理解整体对话动态和话题走向，生成连贯的回复。无需指定目标消息。"

    # 激活设置
    activation_type = ActionActivationType.ALWAYS  # 回应动作总是可用
    mode_enable = ChatMode.ALL  # 在所有模式下都可用
    parallel_action = False  # 回应动作不能与其他动作并行
    
    # Chatter 限制：仅允许 AffinityFlowChatter 使用
    chatter_allow: ClassVar[list[str]] = ["AffinityFlowChatter"]

    # 动作参数定义
    action_parameters: ClassVar = {
        "content": "回复的具体内容（可选，由LLM生成）",
    }

    # 动作使用场景
    action_require: ClassVar = [
        "需要统一回应多条未读消息时使用（Normal 模式专用）",
        "适合理解整体对话动态而非单条消息",
        "不需要指定 target_message_id，会自动处理所有未读消息",
        "关注对话流程、话题走向和整体氛围",
        "适合群聊中的自然对话流，无需精确指向特定消息",
        "可以同时回应多个话题或参与者",
    ]

    # 关联类型
    associated_types: ClassVar[list[str]] = ["text"]

    async def execute(self) -> tuple[bool, str]:
        """执行respond动作 - 完整的回复流程"""
        try:
            # 准备 action_data
            action_data = self.action_data.copy()
            action_data["prompt_mode"] = "normal"
            
            # 生成回复
            success, response_set, _ = await generator_api.generate_reply(
                chat_stream=self.chat_stream,
                reply_message=self.action_message,
                action_data=action_data,
                available_actions={self.action_name: None},
                enable_tool=global_config.tool.enable_tool,
                request_type="chat.replyer",
                from_plugin=False,
            )
            
            if not success or not response_set:
                logger.warning(f"{self.log_prefix} 回复生成失败")
                return False, ""
            
            # 发送回复（respond 默认不引用）
            reply_text = await self._send_response(response_set)
            
            # 存储动作信息
            await self._store_action_info(reply_text)
            
            logger.info(f"{self.log_prefix} respond 动作执行成功")
            return True, reply_text
            
        except asyncio.CancelledError:
            logger.debug(f"{self.log_prefix} 回复任务被取消")
            return False, ""
        except Exception as e:
            logger.error(f"{self.log_prefix} respond 动作执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False, ""
    
    async def _send_response(self, response_set) -> str:
        """发送回复内容（不引用原消息）"""
        reply_text = ""
        first_sent = False
        
        for reply_seg in response_set:
            if isinstance(reply_seg, tuple) and len(reply_seg) >= 2:
                _, data = reply_seg
            else:
                data = str(reply_seg)
            
            if isinstance(data, list):
                data = "".join(map(str, data))
            
            reply_text += data
            
            if not first_sent:
                await send_api.text_to_stream(
                    text=data,
                    stream_id=self.chat_stream.stream_id,
                    reply_to_message=None,
                    set_reply=False,
                    typing=False,
                )
                first_sent = True
            else:
                await send_api.text_to_stream(
                    text=data,
                    stream_id=self.chat_stream.stream_id,
                    reply_to_message=None,
                    set_reply=False,
                    typing=True,
                )
        
        return reply_text
    
    async def _store_action_info(self, reply_text: str):
        """存储动作信息到数据库"""
        await database_api.store_action_info(
            chat_stream=self.chat_stream,
            action_build_into_prompt=False,
            action_prompt_display=f"统一回应：{reply_text}",
            action_done=True,
            thinking_id=self.thinking_id,
            action_data={"reply_text": reply_text},
            action_name="respond",
        )
