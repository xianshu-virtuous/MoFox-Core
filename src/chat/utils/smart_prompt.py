"""
智能Prompt系统 - 完全重构版本
基于原有DefaultReplyer的完整功能集成
"""
import asyncio
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Literal, Tuple
import re

from src.chat.utils.prompt_builder import global_prompt_manager, Prompt
from src.common.logger import get_logger
from src.config.config import global_config
from src.chat.utils.chat_message_builder import (
    build_readable_messages,
    get_raw_msg_before_timestamp_with_chat,
    build_readable_messages_with_id,
    replace_user_references_sync,
)
from src.person_info.person_info import get_person_info_manager

logger = get_logger("smart_prompt")


@dataclass
class SmartPromptParameters:
    """完整的智能提示词参数系统"""
    
    # 从原有DefaultReplyer提取的所有必需参数
    chat_id: str = ""
    is_group_chat: bool = False
    sender: str = ""
    target: str = ""
    reply_to: str = ""
    extra_info: str = ""
    available_actions: Dict[str, Any] = field(default_factory=dict)
    
    # 原有构建函数所需的参数
    chat_target_info: Optional[Dict[str, Any]] = None
    message_list_before_now_long: List[Dict[str, Any]] = field(default_factory=list)
    message_list_before_short: List[Dict[str, Any]] = field(default_factory=list)
    chat_talking_prompt_short: str = ""
    target_user_info: Optional[Dict[str, Any]] = None
    expression_habits_block: str = ""
    relation_info: str = ""
    memory_block: str = ""
    tool_info: str = ""
    prompt_info: str = ""
    cross_context_block: str = ""
    keywords_reaction_prompt: str = ""
    extra_info_block: str = ""
    time_block: str = ""
    identity_block: str = ""
    schedule_block: str = ""
    moderation_prompt_block: str = ""
    reply_target_block: str = ""
    mood_prompt: str = ""
    action_descriptions: str = ""
    
    # 行为配置
    current_prompt_mode: Literal["s4u", "normal", "minimal"] = "s4u"
    enable_tool: bool = True
    enable_memory: bool = True
    enable_expression: bool = True
    enable_relation: bool = True
    enable_cross_context: bool = True
    enable_knowledge: bool = True
    
    # 性能和缓存控制
    enable_cache: bool = True
    cache_ttl: int = 300
    max_context_messages: int = 50
    
    # 调试选项
    debug_mode: bool = False
    
    def validate(self) -> List[str]:
        """参数验证"""
        errors = []
        if not isinstance(self.chat_id, str):
            errors.append("chat_id必须是字符串类型")
        if not isinstance(self.reply_to, str):
            errors.append("reply_to必须是字符串类型")
        return errors


@dataclass
class ChatContext:
    """聊天上下文信息"""
    chat_id: str = ""
    platform: str = ""
    is_group: bool = False
    user_id: str = ""
    user_nickname: str = ""
    group_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class SmartPromptBuilder:
    """重构的智能提示词构建器 - 使用原有DefaultReplyer逻辑"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        
    async def build_context_data(self, params: SmartPromptParameters) -> Dict[str, Any]:
        """并行构建完整的上下文数据"""
        
        # 从缓存检查
        cache_key = self._get_cache_key(params)
        if params.enable_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached.get('timestamp', 0) < params.cache_ttl:
                return cached['data'].copy()
        
        # 构建基础的数据字典
        context_data = {}
        
        # 1. 构建聊天历史 - 根据模式不同
        if params.current_prompt_mode == "s4u":
            await self._build_s4u_chat_context(context_data, params)
        else:
            await self._build_normal_chat_context(context_data, params)
        
        # 2. 集成各个构建模块
        context_data.update({
            'expression_habits_block': params.expression_habits_block,
            'memory_block': params.memory_block,
            'relation_info_block': params.relation_info,
            'tool_info_block': params.tool_info,
            'knowledge_prompt': params.prompt_info,
            'cross_context_block': params.cross_context_block,
            'keywords_reaction_prompt': params.keywords_reaction_prompt,
            'extra_info_block': params.extra_info_block,
            'time_block': params.time_block or f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            'identity': params.identity_block,
            'schedule_block': params.schedule_block,
            'moderation_prompt': params.moderation_prompt_block,
            'reply_target_block': params.reply_target_block,
            'mood_state': params.mood_prompt,
            'action_descriptions': params.action_descriptions,
        })
        
        # 缓存数据
        if params.enable_cache:
            self._cache[cache_key] = {
                'data': context_data,
                'timestamp': time.time()
            }
        
        return context_data
    
    def _get_cache_key(self, params: SmartPromptParameters) -> str:
        """生成缓存键"""
        return f"{params.chat_id}_{params.current_prompt_mode}_{hash(params.reply_to)}"
    
    async def _build_s4u_chat_context(self, context_data: Dict[str, Any], params: SmartPromptParameters) -> None:
        """构建S4U模式的聊天上下文"""
        if not params.message_list_before_now_long:
            return
            
        # 使用原有的分离逻辑
        core_dialogue, background_dialogue = self._build_s4u_separated_history(
            params.message_list_before_now_long, 
            params.target_user_info
        )
        
        context_data['core_dialogue_prompt'] = core_dialogue
        context_data['background_dialogue_prompt'] = background_dialogue
        
    async def _build_normal_chat_context(self, context_data: Dict[str, Any], params: SmartPromptParameters) -> None:
        """构建normal模式的聊天上下文"""
        if not params.chat_talking_prompt_short:
            return
            
        context_data['chat_info'] = f"""群里的聊天内容：
{params.chat_talking_prompt_short}"""
    
    def _build_s4u_separated_history(
        self, 
        message_list_before_now: List[Dict[str, Any]], 
        target_user_info: Optional[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """复制原有的分离对话逻辑"""
        core_dialogue_list = []
        background_dialogue_list = []
        bot_id = str(global_config.bot.qq_account)
        
        # 获取目标用户ID
        target_user_id = ""
        if target_user_info:
            target_user_id = str(target_user_info.get("user_id", ""))
        
        # 过滤消息：分离bot和目标用户的对话 vs 其他用户的对话
        for msg_dict in message_list_before_now:
            try:
                msg_user_id = str(msg_dict.get("user_id", ""))
                reply_to = msg_dict.get("reply_to", "")
                reply_to_user_id = self._parse_reply_target_id(reply_to)
                
                if (msg_user_id == bot_id and reply_to_user_id == target_user_id) or msg_user_id == target_user_id:
                    core_dialogue_list.append(msg_dict)
                else:
                    background_dialogue_list.append(msg_dict)
            except Exception as e:
                logger.error(f"处理消息记录时出错: {msg_dict}, 错误: {e}")
        
        # 构建背景对话
        background_dialogue_prompt = ""
        if background_dialogue_list:
            latest_25_msgs = background_dialogue_list[-int(global_config.chat.max_context_size * 0.5):]
            background_dialogue_prompt_str = build_readable_messages(
                latest_25_msgs,
                replace_bot_name=True,
                timestamp_mode="normal",
                truncate=True,
            )
            background_dialogue_prompt = f"这是其他用户的发言：\n{background_dialogue_prompt_str}"
        
        # 构建核心对话
        core_dialogue_prompt = ""
        if core_dialogue_list:
            core_dialogue_list = core_dialogue_list[-int(global_config.chat.max_context_size * 2):]
            core_dialogue_prompt_str = build_readable_messages(
                core_dialogue_list,
                replace_bot_name=True,
                merge_messages=False,
                timestamp_mode="normal",
                read_mark=0.0,
                truncate=True,
                show_actions=True,
            )
            core_dialogue_prompt = core_dialogue_prompt_str
        
        return core_dialogue_prompt, background_dialogue_prompt
    
    def _parse_reply_target_id(self, reply_to: str) -> str:
        """解析回复目标中的用户ID"""
        if not reply_to:
            return ""
        return ""  # 简化实现，实际需要从reply_to中提取
    
    @property
    def _cached_data(self) -> dict:
        """缓存存储"""
        if not hasattr(self, '_cache_store'):
            self._cache_store = {}
        return self._cache_store


class SmartPrompt:
    """重构的智能提示词核心类"""
    
    def __init__(
        self,
        template_name: Optional[str] = None,
        parameters: Optional[SmartPromptParameters] = None,
    ):
        self.parameters = parameters or SmartPromptParameters()
        self.template_name = template_name or self._get_default_template()
        self.builder = SmartPromptBuilder()
        
    def _get_default_template(self) -> str:
        """根据模式选择默认模板"""
        if self.parameters.current_prompt_mode == "s4u":
            return "s4u_style_prompt"
        elif self.parameters.current_prompt_mode == "normal":
            return "normal_style_prompt"
        else:
            return "default_expressor_prompt"
    
    async def build_prompt(self) -> str:
        """构建最终的Prompt文本"""
        # 参数验证
        errors = self.parameters.validate()
        if errors:
            raise ValueError(f"参数验证失败: {', '.join(errors)}")
        
        try:
            # 构建基础上下文的完整映射
            context_data = await self.builder.build_context_data(self.parameters)
            
            # 获取模板
            template = await global_prompt_manager.get_prompt_async(self.template_name)
            
            # 根据模式传递不同的参数
            if self.parameters.current_prompt_mode == "s4u":
                return await self._build_s4u_prompt(template, context_data)
            elif self.parameters.current_prompt_mode == "normal":
                return await self._build_normal_prompt(template, context_data)
            else:
                return await self._build_default_prompt(template, context_data)
                
        except Exception as e:
            logger.error(f"构建Prompt失败: {e}")
            # 返回一个基础Prompt
            return f"用户说：{self.parameters.reply_to}。请回复。"
    
    async def _build_s4u_prompt(self, template: Prompt, context_data: Dict[str, Any]) -> str:
        """构建S4U模式的完整Prompt"""
        params = {
            **context_data,
            'expression_habits_block': context_data.get('expression_habits_block', ''),
            'tool_info_block': context_data.get('tool_info_block', ''),
            'knowledge_prompt': context_data.get('knowledge_prompt', ''),
            'memory_block': context_data.get('memory_block', ''),
            'relation_info_block': context_data.get('relation_info_block', ''),
            'extra_info_block': context_data.get('extra_info_block', ''),
            'cross_context_block': context_data.get('cross_context_block', ''),
            'identity': context_data.get('identity', ''),
            'action_descriptions': context_data.get('action_descriptions', ''),
            'sender_name': self.parameters.sender,
            'mood_state': context_data.get('mood_state', ''),
            'background_dialogue_prompt': context_data.get('background_dialogue_prompt', ''),
            'time_block': context_data.get('time_block', ''),
            'core_dialogue_prompt': context_data.get('core_dialogue_prompt', ''),
            'reply_target_block': context_data.get('reply_target_block', ''),
            'reply_style': global_config.personality.reply_style,
            'keywords_reaction_prompt': context_data.get('keywords_reaction_prompt', ''),
            'moderation_prompt': context_data.get('moderation_prompt', ''),
        }
        return await global_prompt_manager.format_prompt(self.template_name, **params)
    
    async def _build_normal_prompt(self, template: Prompt, context_data: Dict[str, Any]) -> str:
        """构建Normal模式的完整Prompt"""
        params = {
            **context_data,
            'expression_habits_block': context_data.get('expression_habits_block', ''),
            'tool_info_block': context_data.get('tool_info_block', ''),
            'knowledge_prompt': context_data.get('knowledge_prompt', ''),
            'memory_block': context_data.get('memory_block', ''),
            'relation_info_block': context_data.get('relation_info_block', ''),
            'extra_info_block': context_data.get('extra_info_block', ''),
            'cross_context_block': context_data.get('cross_context_block', ''),
            'identity': context_data.get('identity', ''),
            'action_descriptions': context_data.get('action_descriptions', ''),
            'schedule_block': context_data.get('schedule_block', ''),
            'time_block': context_data.get('time_block', ''),
            'chat_info': context_data.get('chat_info', ''),
            'reply_target_block': context_data.get('reply_target_block', ''),
            'config_expression_style': global_config.personality.reply_style,
            'mood_state': context_data.get('mood_state', ''),
            'keywords_reaction_prompt': context_data.get('keywords_reaction_prompt', ''),
            'moderation_prompt': context_data.get('moderation_prompt', ''),
        }
        return await global_prompt_manager.format_prompt(self.template_name, **params)
    
    async def _build_default_prompt(self, template: Prompt, context_data: Dict[str, Any]) -> str:
        """构建默认模式的Prompt"""
        params = {
            'expression_habits_block': context_data.get('expression_habits_block', ''),
            'relation_info_block': context_data.get('relation_info_block', ''),
            'chat_target': "",
            'time_block': context_data.get('time_block', ''),
            'chat_info': context_data.get('chat_info', ''),
            'identity': context_data.get('identity', ''),
            'chat_target_2': "",
            'reply_target_block': context_data.get('reply_target_block', ''),
            'raw_reply': self.parameters.target,
            'reason': "",
            'mood_state': context_data.get('mood_state', ''),
            'reply_style': global_config.personality.reply_style,
            'keywords_reaction_prompt': context_data.get('keywords_reaction_prompt', ''),
            'moderation_prompt': context_data.get('moderation_prompt', ''),
        }
        return await global_prompt_manager.format_prompt(self.template_name, **params)


# 工厂函数 - 简化创建
def create_smart_prompt(
    reply_to: str = "",
    extra_info: str = "",
    **kwargs
) -> SmartPrompt:
    """快速创建智能Prompt实例的工厂函数"""
    
    parameters = SmartPromptParameters(
        reply_to=reply_to,
        extra_info=extra_info,
        **kwargs
    )
    
    return SmartPrompt(parameters=parameters)