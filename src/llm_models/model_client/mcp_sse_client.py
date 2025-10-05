"""
MCP (Model Context Protocol) SSE (Server-Sent Events) 客户端实现
支持通过SSE协议与MCP服务器进行通信
"""

import asyncio
import io
from collections.abc import Callable
from typing import Any

import aiohttp
import orjson
from json_repair import repair_json

from src.common.logger import get_logger
from src.config.api_ada_configs import APIProvider, ModelInfo

from ..exceptions import (
    NetworkConnectionError,
    ReqAbortException,
    RespNotOkException,
)
from ..payload_content.message import Message, RoleType
from ..payload_content.resp_format import RespFormat
from ..payload_content.tool_option import ToolCall, ToolOption
from .base_client import APIResponse, BaseClient, UsageRecord, client_registry

logger = get_logger("MCP-SSE客户端")


def _convert_messages_to_mcp(messages: list[Message]) -> list[dict[str, Any]]:
    """
    将消息列表转换为MCP协议格式
    :param messages: 消息列表
    :return: MCP格式的消息列表
    """
    mcp_messages = []

    for message in messages:
        mcp_msg: dict[str, Any] = {
            "role": message.role.value,
        }

        # 处理内容
        if isinstance(message.content, str):
            mcp_msg["content"] = message.content
        elif isinstance(message.content, list):
            # 处理多模态内容
            content_parts = []
            for item in message.content:
                if isinstance(item, tuple):
                    # 图片内容
                    content_parts.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": f"image/{item[0].lower()}",
                            "data": item[1],
                        },
                    })
                elif isinstance(item, str):
                    # 文本内容
                    content_parts.append({"type": "text", "text": item})
            mcp_msg["content"] = content_parts

        # 添加工具调用ID（如果是工具消息）
        if message.role == RoleType.Tool and message.tool_call_id:
            mcp_msg["tool_call_id"] = message.tool_call_id

        mcp_messages.append(mcp_msg)

    return mcp_messages


def _convert_tools_to_mcp(tool_options: list[ToolOption]) -> list[dict[str, Any]]:
    """
    将工具选项转换为MCP协议格式
    :param tool_options: 工具选项列表
    :return: MCP格式的工具列表
    """
    mcp_tools = []

    for tool in tool_options:
        mcp_tool = {
            "name": tool.name,
            "description": tool.description,
        }

        if tool.params:
            properties = {}
            required = []

            for param in tool.params:
                properties[param.name] = {
                    "type": param.param_type.value,
                    "description": param.description,
                }

                if param.enum_values:
                    properties[param.name]["enum"] = param.enum_values

                if param.required:
                    required.append(param.name)

            mcp_tool["input_schema"] = {
                "type": "object",
                "properties": properties,
                "required": required,
            }

        mcp_tools.append(mcp_tool)

    return mcp_tools


async def _parse_sse_stream(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    interrupt_flag: asyncio.Event | None = None,
) -> tuple[APIResponse, tuple[int, int, int] | None]:
    """
    解析SSE流式响应
    :param session: aiohttp会话
    :param url: 请求URL
    :param payload: 请求负载
    :param headers: 请求头
    :param interrupt_flag: 中断标志
    :return: API响应和使用记录
    """
    content_buffer = io.StringIO()
    reasoning_buffer = io.StringIO()
    tool_calls_buffer: list[tuple[str, str, dict[str, Any]]] = []
    usage_record = None

    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RespNotOkException(
                    response.status, f"MCP SSE请求失败: {error_text}"
                )

            # 解析SSE流
            async for line in response.content:
                if interrupt_flag and interrupt_flag.is_set():
                    raise ReqAbortException("请求被外部信号中断")

                decoded_line = line.decode("utf-8").strip()

                # 跳过空行和注释
                if not decoded_line or decoded_line.startswith(":"):
                    continue

                # 解析SSE事件
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]  # 移除"data: "前缀

                    # 跳过[DONE]标记
                    if data_str == "[DONE]":
                        break

                    try:
                        event_data = orjson.loads(data_str)
                    except orjson.JSONDecodeError:
                        logger.warning(f"无法解析SSE数据: {data_str}")
                        continue

                    # 处理不同类型的事件
                    event_type = event_data.get("type")

                    if event_type == "content_block_start":
                        # 内容块开始
                        block = event_data.get("content_block", {})
                        if block.get("type") == "text":
                            pass  # 准备接收文本内容
                        elif block.get("type") == "tool_use":
                            # 工具调用开始
                            tool_calls_buffer.append(
                                (
                                    block.get("id", ""),
                                    block.get("name", ""),
                                    {},
                                )
                            )

                    elif event_type == "content_block_delta":
                        # 内容块增量
                        delta = event_data.get("delta", {})
                        delta_type = delta.get("type")

                        if delta_type == "text_delta":
                            # 文本增量
                            text = delta.get("text", "")
                            content_buffer.write(text)

                        elif delta_type == "input_json_delta":
                            # 工具调用参数增量
                            if tool_calls_buffer:
                                partial_json = delta.get("partial_json", "")
                                # 累积JSON片段
                                current_args = tool_calls_buffer[-1][2]
                                if "_json_buffer" not in current_args:
                                    current_args["_json_buffer"] = ""
                                current_args["_json_buffer"] += partial_json

                    elif event_type == "content_block_stop":
                        # 内容块结束
                        if tool_calls_buffer:
                            # 解析完整的工具调用参数
                            last_call = tool_calls_buffer[-1]
                            if "_json_buffer" in last_call[2]:
                                json_str = last_call[2].pop("_json_buffer")
                                try:
                                    parsed_args = orjson.loads(repair_json(json_str))
                                    tool_calls_buffer[-1] = (
                                        last_call[0],
                                        last_call[1],
                                        parsed_args if isinstance(parsed_args, dict) else {},
                                    )
                                except orjson.JSONDecodeError as e:
                                    logger.error(f"解析工具调用参数失败: {e}")

                    elif event_type == "message_delta":
                        # 消息元数据更新
                        delta = event_data.get("delta", {})
                        stop_reason = delta.get("stop_reason")
                        if stop_reason:
                            logger.debug(f"消息结束原因: {stop_reason}")

                        # 提取使用统计
                        usage = event_data.get("usage", {})
                        if usage:
                            usage_record = (
                                usage.get("input_tokens", 0),
                                usage.get("output_tokens", 0),
                                usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                            )

                    elif event_type == "message_stop":
                        # 消息结束
                        break

    except aiohttp.ClientError as e:
        raise NetworkConnectionError() from e
    except Exception as e:
        logger.error(f"解析SSE流时发生错误: {e}")
        raise

    # 构建响应
    response = APIResponse()

    if content_buffer.tell() > 0:
        response.content = content_buffer.getvalue()

    if reasoning_buffer.tell() > 0:
        response.reasoning_content = reasoning_buffer.getvalue()

    if tool_calls_buffer:
        response.tool_calls = [
            ToolCall(call_id, func_name, args)
            for call_id, func_name, args in tool_calls_buffer
        ]

    # 关闭缓冲区
    content_buffer.close()
    reasoning_buffer.close()

    return response, usage_record


@client_registry.register_client_class("mcp_sse")
class MCPSSEClient(BaseClient):
    """
    MCP SSE客户端实现
    支持通过Server-Sent Events协议与MCP服务器通信
    """

    def __init__(self, api_provider: APIProvider):
        super().__init__(api_provider)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.api_provider.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """关闭客户端会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_response(
        self,
        model_info: ModelInfo,
        message_list: list[Message],
        tool_options: list[ToolOption] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: RespFormat | None = None,
        stream_response_handler: Callable[[Any, asyncio.Event | None], tuple[APIResponse, tuple[int, int, int]]]
        | None = None,
        async_response_parser: Callable[[Any], tuple[APIResponse, tuple[int, int, int]]] | None = None,
        interrupt_flag: asyncio.Event | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> APIResponse:
        """
        获取对话响应
        :param model_info: 模型信息
        :param message_list: 对话消息列表
        :param tool_options: 工具选项
        :param max_tokens: 最大token数
        :param temperature: 温度参数
        :param response_format: 响应格式
        :param stream_response_handler: 流式响应处理器
        :param async_response_parser: 异步响应解析器
        :param interrupt_flag: 中断标志
        :param extra_params: 额外参数
        :return: API响应
        """
        session = await self._get_session()

        # 构建请求负载
        payload: dict[str, Any] = {
            "model": model_info.model_identifier,
            "messages": _convert_messages_to_mcp(message_list),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # MCP SSE始终使用流式
        }

        # 添加工具
        if tool_options:
            payload["tools"] = _convert_tools_to_mcp(tool_options)

        # 添加额外参数
        if extra_params:
            payload.update(extra_params)

        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_provider.get_api_key()}",
        }

        # 发送请求并解析响应
        url = f"{self.api_provider.base_url}/v1/messages"

        try:
            response, usage_record = await _parse_sse_stream(
                session, url, payload, headers, interrupt_flag
            )
        except Exception as e:
            logger.error(f"MCP SSE请求失败: {e}")
            raise

        # 添加使用记录
        if usage_record:
            response.usage = UsageRecord(
                model_name=model_info.name,
                provider_name=model_info.api_provider,
                prompt_tokens=usage_record[0],
                completion_tokens=usage_record[1],
                total_tokens=usage_record[2],
            )

        return response

    async def get_embedding(
        self,
        model_info: ModelInfo,
        embedding_input: str,
        extra_params: dict[str, Any] | None = None,
    ) -> APIResponse:
        """
        获取文本嵌入
        MCP协议暂不支持嵌入功能
        :param model_info: 模型信息
        :param embedding_input: 嵌入输入文本
        :return: 嵌入响应
        """
        raise NotImplementedError("MCP SSE客户端暂不支持嵌入功能")

    async def get_audio_transcriptions(
        self,
        model_info: ModelInfo,
        audio_base64: str,
        extra_params: dict[str, Any] | None = None,
    ) -> APIResponse:
        """
        获取音频转录
        MCP协议暂不支持音频转录功能
        :param model_info: 模型信息
        :param audio_base64: base64编码的音频数据
        :return: 音频转录响应
        """
        raise NotImplementedError("MCP SSE客户端暂不支持音频转录功能")

    def get_support_image_formats(self) -> list[str]:
        """
        获取支持的图片格式
        :return: 支持的图片格式列表
        """
        return ["jpg", "jpeg", "png", "webp", "gif"]
