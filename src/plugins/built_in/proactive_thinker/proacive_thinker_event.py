from typing import List, Union, Type, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)
from src.plugin_system import (
    EventType,
    BaseEventHandler,
    HandlerResult,
)


class ProactiveThinkerEventHandler(BaseEventHandler):
    """主动思考需要的启动时触发的事件处理器"""

    handler_name: str = "proactive_thinker_on_start"
    handler_description: str = "主动思考插件的启动事件处理器"
    init_subscribe: List[Union[EventType, str]] = [EventType.ON_START]

    async def execute(self, kwargs: dict | None) -> "HandlerResult":
        """执行事件处理"""
        logger.info("ProactiveThinkerPlugin on_start event triggered.")
        # 返回 (是否执行成功, 是否需要继续处理, 可选的返回消息)
        return HandlerResult(success=True, continue_process=True, message=None)
