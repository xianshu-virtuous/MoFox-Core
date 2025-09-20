"""
消息管理模块
管理每个聊天流的上下文信息，包含历史记录和未读消息，定期检查并处理新消息
"""

from .message_manager import MessageManager, message_manager
from src.common.data_models.message_manager_data_model import (
    StreamContext,
    MessageStatus,
    MessageManagerStats,
    StreamStats,
)

__all__ = ["MessageManager", "message_manager", "StreamContext", "MessageStatus", "MessageManagerStats", "StreamStats"]
