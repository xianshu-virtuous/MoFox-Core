"""
消息管理模块
管理每个聊天流的上下文信息，包含历史记录和未读消息，定期检查并处理新消息
"""
import asyncio
import time
import traceback
from typing import Dict, Optional, Any

from src.common.logger import get_logger
from src.common.data_models.database_data_model import DatabaseMessages
from src.common.data_models.message_manager_data_model import StreamContext, MessageManagerStats, StreamStats
from src.chat.affinity_flow.afc_manager import afc_manager

logger = get_logger("message_manager")


class MessageManager:
    """消息管理器"""

    def __init__(self, check_interval: float = 2.0):
        self.stream_contexts: Dict[str, StreamContext] = {}
        self.check_interval = check_interval  # 检查间隔（秒）
        self.is_running = False
        self.manager_task: Optional[asyncio.Task] = None

        # 统计信息
        self.stats = MessageManagerStats()

    async def start(self):
        """启动消息管理器"""
        if self.is_running:
            logger.warning("消息管理器已经在运行")
            return

        self.is_running = True
        self.manager_task = asyncio.create_task(self._manager_loop())
        logger.info("消息管理器已启动")

    async def stop(self):
        """停止消息管理器"""
        if not self.is_running:
            return

        self.is_running = False

        # 停止所有流处理任务
        for context in self.stream_contexts.values():
            if context.processing_task and not context.processing_task.done():
                context.processing_task.cancel()

        # 停止管理器任务
        if self.manager_task and not self.manager_task.done():
            self.manager_task.cancel()

        logger.info("消息管理器已停止")

    def add_message(self, stream_id: str, message: DatabaseMessages):
        """添加消息到指定聊天流"""
        # 获取或创建流上下文
        if stream_id not in self.stream_contexts:
            self.stream_contexts[stream_id] = StreamContext(stream_id=stream_id)
            self.stats.total_streams += 1

        context = self.stream_contexts[stream_id]
        context.add_message(message)

        logger.debug(f"添加消息到聊天流 {stream_id}: {message.message_id}")

    async def _manager_loop(self):
        """管理器主循环"""
        while self.is_running:
            try:
                await self._check_all_streams()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息管理器循环出错: {e}")
                traceback.print_exc()

    async def _check_all_streams(self):
        """检查所有聊天流"""
        active_streams = 0
        total_unread = 0

        for stream_id, context in self.stream_contexts.items():
            if not context.is_active:
                continue

            active_streams += 1

            # 检查是否有未读消息
            unread_messages = context.get_unread_messages()
            if unread_messages:
                total_unread += len(unread_messages)

                # 如果没有处理任务，创建一个
                if not context.processing_task or context.processing_task.done():
                    context.processing_task = asyncio.create_task(
                        self._process_stream_messages(stream_id)
                    )

        # 更新统计
        self.stats.active_streams = active_streams
        self.stats.total_unread_messages = total_unread

    async def _process_stream_messages(self, stream_id: str):
        """处理指定聊天流的消息"""
        if stream_id not in self.stream_contexts:
            return

        context = self.stream_contexts[stream_id]

        try:
            # 获取未读消息
            unread_messages = context.get_unread_messages()
            if not unread_messages:
                return

            logger.debug(f"开始处理聊天流 {stream_id} 的 {len(unread_messages)} 条未读消息")

            # 获取上下文消息
            context_messages = context.get_context_messages()

            # 批量处理消息
            messages_data = []
            for msg in unread_messages:
                message_data = {
                    "message_info": {
                        "platform": msg.user_info.platform,
                        "user_info": {
                            "user_id": msg.user_info.user_id,
                            "user_nickname": msg.user_info.user_nickname,
                            "user_cardname": msg.user_info.user_cardname,
                            "platform": msg.user_info.platform
                        },
                        "group_info": {
                            "group_id": msg.group_info.group_id,
                            "group_name": msg.group_info.group_name,
                            "group_platform": msg.group_info.group_platform
                        } if msg.group_info else None
                    },
                    "processed_plain_text": msg.processed_plain_text,
                    "context_messages": [ctx_msg.flatten() for ctx_msg in context_messages],
                    "unread_messages": unread_messages  # 传递原始对象而不是字典
                }
                messages_data.append(message_data)

            # 发送到AFC处理器
            if messages_data:
                results = await afc_manager.process_messages_batch(stream_id, messages_data)

                # 处理结果，标记消息为已读
                for i, result in enumerate(results):
                    if result.get("success", False):
                        msg_id = unread_messages[i].message_id
                        context.mark_message_as_read(msg_id)
                        self.stats.total_processed_messages += 1
                        logger.debug(f"消息 {msg_id} 处理完成，标记为已读")

            logger.debug(f"聊天流 {stream_id} 消息处理完成")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"处理聊天流 {stream_id} 消息时出错: {e}")
            traceback.print_exc()

    def deactivate_stream(self, stream_id: str):
        """停用聊天流"""
        if stream_id in self.stream_contexts:
            context = self.stream_contexts[stream_id]
            context.is_active = False

            # 取消处理任务
            if context.processing_task and not context.processing_task.done():
                context.processing_task.cancel()

            logger.info(f"停用聊天流: {stream_id}")

    def activate_stream(self, stream_id: str):
        """激活聊天流"""
        if stream_id in self.stream_contexts:
            self.stream_contexts[stream_id].is_active = True
            logger.info(f"激活聊天流: {stream_id}")

    def get_stream_stats(self, stream_id: str) -> Optional[StreamStats]:
        """获取聊天流统计"""
        if stream_id not in self.stream_contexts:
            return None

        context = self.stream_contexts[stream_id]
        return StreamStats(
            stream_id=stream_id,
            is_active=context.is_active,
            unread_count=len(context.get_unread_messages()),
            history_count=len(context.history_messages),
            last_check_time=context.last_check_time,
            has_active_task=context.processing_task and not context.processing_task.done()
        )

    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计"""
        return {
            "total_streams": self.stats.total_streams,
            "active_streams": self.stats.active_streams,
            "total_unread_messages": self.stats.total_unread_messages,
            "total_processed_messages": self.stats.total_processed_messages,
            "uptime": self.stats.uptime,
            "start_time": self.stats.start_time
        }

    def cleanup_inactive_streams(self, max_inactive_hours: int = 24):
        """清理不活跃的聊天流"""
        current_time = time.time()
        max_inactive_seconds = max_inactive_hours * 3600

        inactive_streams = []
        for stream_id, context in self.stream_contexts.items():
            if (current_time - context.last_check_time > max_inactive_seconds and
                not context.get_unread_messages()):
                inactive_streams.append(stream_id)

        for stream_id in inactive_streams:
            self.deactivate_stream(stream_id)
            del self.stream_contexts[stream_id]
            logger.info(f"清理不活跃聊天流: {stream_id}")


# 创建全局消息管理器实例
message_manager = MessageManager()