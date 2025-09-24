import re
from typing import List, Tuple, Type

from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    ComponentInfo,
    ActionActivationType,
    ConfigField,
)
from src.common.logger import get_logger
from .qq_emoji_list import qq_face
from src.plugin_system.base.component_types import ChatType
from src.plugin_system.apis import llm_api
from src.config.config import model_config, global_config
from src.chat.utils.chat_message_builder import build_readable_messages

logger = get_logger("set_emoji_like_plugin")


async def get_emoji_id(emoji_input: str) -> str | None:
    """根据输入获取表情ID"""
    # 如果输入本身就是数字ID，直接返回
    if emoji_input.isdigit() or (isinstance(emoji_input, str) and emoji_input.startswith("😊")):
        if emoji_input in qq_face:
            return emoji_input

    # 尝试从 "[表情：xxx]" 格式中提取
    match = re.search(r"\[表情：(.+?)\]", emoji_input)
    if match:
        emoji_name = match.group(1).strip()
    else:
        emoji_name = emoji_input.strip()

    # 遍历查找
    for key, value in qq_face.items():
        # value 的格式是 "[表情：xxx]"
        if f"[表情：{emoji_name}]" == value:
            return key

    return None


# ===== Action组件 =====
class SetEmojiLikeAction(BaseAction):
    """设置消息表情回应"""

    # === 基本信息（必须填写）===
    action_name = "set_emoji_like"
    action_description = "为某条已经存在的消息添加‘贴表情’回应（类似点赞），而不是发送新消息。可以在觉得某条消息非常有趣、值得赞同或者需要特殊情感回应时主动使用。"
    activation_type = ActionActivationType.ALWAYS  # 消息接收时激活(?)
    chat_type_allow = ChatType.GROUP
    parallel_action = True

    # === 功能描述（必须填写）===
    # 从 qq_face 字典中提取所有表情名称用于提示
    emoji_options = []
    for name in qq_face.values():
        match = re.search(r"\[表情：(.+?)\]", name)
        if match:
            emoji_options.append(match.group(1))

    action_parameters = {
        "emoji": f"要回应的表情,必须从以下表情中选择: {', '.join(emoji_options)}",
        "set": "是否设置回应 (True/False)",
    }
    action_require = [
        "当需要对一个已存在消息进行‘贴表情’回应时使用",
        "这是一个对旧消息的操作，而不是发送新消息",
        "如果你想发送一个新的表情包消息，请使用 'emoji' 动作",
    ]
    llm_judge_prompt = """
    判定是否需要使用贴表情动作的条件：
    1. 用户明确要求使用贴表情包
    2. 这是一个适合表达强烈情绪的场合
    3. 不要发送太多表情包，如果你已经发送过多个表情包则回答"否"
    
    请回答"是"或"否"。
    """
    associated_types = ["text"]

    async def execute(self) -> Tuple[bool, str]:
        """执行设置表情回应的动作"""
        message_id = None
        if self.has_action_message:
            logger.debug(str(self.action_message))
            if isinstance(self.action_message, dict):
                message_id = self.action_message.get("message_id")
            logger.info(f"获取到的消息ID: {message_id}")
        else:
            logger.error("未提供消息ID")
            await self.store_action_info(
                action_build_into_prompt=True,
                action_prompt_display=f"执行了set_emoji_like动作：{self.action_name},失败: 未提供消息ID",
                action_done=False,
            )
            return False, "未提供消息ID"

        emoji_input = self.action_data.get("emoji")
        set_like = self.action_data.get("set", True)

        if not emoji_input:
            logger.info("未提供表情，将由LLM决定")
            try:
                emoji_input = await self.ask_llm_for_emoji()
                if not emoji_input:
                    logger.error("LLM未能选择表情")
                    return False, "LLM未能选择表情"
            except Exception as e:
                logger.error(f"请求LLM选择表情时出错: {e}")
                return False, f"请求LLM选择表情时出错: {e}"

        logger.info(f"设置表情回应: {emoji_input}, 是否设置: {set_like}")

        emoji_id = await get_emoji_id(emoji_input)
        if not emoji_id:
            logger.error(f"找不到表情: '{emoji_input}'。请从可用列表中选择。")
            await self.store_action_info(
                action_build_into_prompt=True,
                action_prompt_display=f"执行了set_emoji_like动作：{self.action_name},失败: 找不到表情: '{emoji_input}'",
                action_done=False,
            )
            return False, f"找不到表情: '{emoji_input}'。请从可用列表中选择。"

        # 4. 使用适配器API发送命令
        if not message_id:
            logger.error("未提供消息ID")
            await self.store_action_info(
                action_build_into_prompt=True,
                action_prompt_display=f"执行了set_emoji_like动作：{self.action_name},失败: 未提供消息ID",
                action_done=False,
            )
            return False, "未提供消息ID"

        try:
            # 使用适配器API发送贴表情命令
            success = await self.send_command(
                command_name="set_emoji_like", args={"message_id": message_id, "emoji_id": emoji_id, "set": set_like}, storage_message=False
            )
            if success:
                logger.info("设置表情回应成功")
                await self.store_action_info(
                    action_build_into_prompt=True,
                    action_prompt_display=f"执行了set_emoji_like动作,{emoji_input},设置表情回应: {emoji_id}, 是否设置: {set_like}",
                    action_done=True,
                )
                return True, "成功设置表情回应"
            else:
                logger.error("设置表情回应失败")
                await self.store_action_info(
                    action_build_into_prompt=True,
                    action_prompt_display=f"执行了set_emoji_like动作：{self.action_name},失败",
                    action_done=False,
                )
                return False, "设置表情回应失败"

        except Exception as e:
            logger.error(f"设置表情回应失败: {e}")
            await self.store_action_info(
                action_build_into_prompt=True,
                action_prompt_display=f"执行了set_emoji_like动作：{self.action_name},失败: {e}",
                action_done=False,
            )
            return False, f"设置表情回应失败: {e}"

    async def ask_llm_for_emoji(self) -> str | None:
        """构建Prompt并请求LLM选择一个表情"""
        from src.mood.mood_manager import mood_manager
        from src.individuality.individuality import get_individuality
        from src.chat.message_manager.message_manager import message_manager

        # 1. 获取上下文信息
        stream_context = message_manager.stream_contexts.get(self.chat_stream.stream_id)
        if not stream_context:
            logger.error(f"无法为 stream_id '{self.chat_stream.stream_id}' 找到 StreamContext")
            return None
            
        history_messages = stream_context.get_latest_messages(20)
        chat_context = build_readable_messages(
            [msg.flatten() for msg in history_messages],
            replace_bot_name=True,
            timestamp_mode="normal_no_YMD",
            truncate=True,
        )

        target_message_content = self.action_message.get("processed_plain_text", "")
        mood = mood_manager.get_mood_by_chat_id(self.chat_stream.stream_id).mood_state
        identity = await get_individuality().get_personality_block()

        # 2. 构建Prompt
        emoji_options_str = ", ".join(self.emoji_options)
        bot_name = global_config.bot.nickname or "爱莉希雅"
        prompt = f"""
# 指令：选择一个最合适的表情来回应消息

## 场景描述
你的名字是“{bot_name}”。
{identity}
你现在的心情是：{mood}

## 聊天上下文
下面是最近的聊天记录：
{chat_context}

## 你的任务
你需要针对下面的这条消息，选择一个最合适的表情来“贴”在上面，以表达你的心情和回应。
目标消息："{target_message_content}"

## 表情选项
请从以下表情中，选择一个最能代表你此刻心情的表情。你只能选择一个，并直接返回它的【名称】。
{emoji_options_str}

## 输出要求
直接输出你选择的表情【名称】，不要添加任何多余的文字、解释或标点符号。

你选择的表情名称是：
"""

        # 3. 调用LLM
        success, response, _, _ = await llm_api.generate_with_model(
            prompt, model_config.model_task_config.tool_executor
        )

        if success and response:
            # 清理LLM返回的可能存在的额外字符
            cleaned_response = re.sub(r"[\[\]\'\"]", "", response).strip()
            logger.info(f"LLM选择了表情: '{cleaned_response}'")
            return cleaned_response
        
        return None

# ===== 插件注册 =====
@register_plugin
class SetEmojiLikePlugin(BasePlugin):
    """设置消息表情回应插件"""

    # 插件基本信息
    plugin_name: str = "set_emoji_like"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表，现在使用内置API
    config_file_name: str = "config.toml"  # 配置文件名

    # 配置节描述
    config_section_descriptions = {"plugin": "插件基本信息", "components": "插件组件"}

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "name": ConfigField(type=str, default="set_emoji_like", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(type=str, default="1.1", description="配置版本"),
        },
        "components": {
            "action_set_emoji_like": ConfigField(type=bool, default=True, description="是否启用设置表情回应功能"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        if self.get_config("components.action_set_emoji_like"):
            return [
                (SetEmojiLikeAction.get_action_info(), SetEmojiLikeAction),
            ]
        return []
