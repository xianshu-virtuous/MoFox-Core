"""
MCP (Model Context Protocol) 连接器
负责连接MCP服务器，获取和执行工具
"""

from typing import Any

import aiohttp

from src.common.logger import get_logger

logger = get_logger("MCP连接器")


class MCPConnector:
    """MCP服务器连接器"""

    def __init__(self, server_url: str, api_key: str | None = None, timeout: int = 30):
        """
        初始化MCP连接器

        Args:
            server_url: MCP服务器URL
            api_key: API密钥（可选）
            timeout: 超时时间（秒）
        """
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
        self._tools_cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl: int = 300  # 工具列表缓存5分钟

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_headers(self) -> dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_tools(self, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """
        获取MCP服务器提供的工具列表

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            Dict[str, Dict]: 工具字典，key为工具名，value为工具定义
        """
        import time

        # 检查缓存
        if not force_refresh and self._tools_cache and (time.time() - self._cache_timestamp) < self._cache_ttl:
            logger.debug("使用缓存的MCP工具列表")
            return self._tools_cache

        logger.info(f"正在从MCP服务器获取工具列表: {self.server_url}")

        try:
            session = await self._get_session()
            url = f"{self.server_url}/tools/list"

            async with session.post(url, headers=self._build_headers(), json={}) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"获取MCP工具列表失败: HTTP {response.status} - {error_text}")
                    return {}

                data = await response.json()

                # 解析工具列表
                tools = {}
                tool_list = data.get("tools", [])

                for tool_def in tool_list:
                    tool_name = tool_def.get("name")
                    if not tool_name:
                        continue

                    tools[tool_name] = {
                        "name": tool_name,
                        "description": tool_def.get("description", ""),
                        "input_schema": tool_def.get("inputSchema", {}),
                    }

                logger.info(f"成功获取 {len(tools)} 个MCP工具")
                self._tools_cache = tools
                self._cache_timestamp = time.time()

                return tools

        except aiohttp.ClientError as e:
            logger.error(f"连接MCP服务器失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"获取MCP工具列表时发生错误: {e}")
            return {}

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        调用MCP服务器上的工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            Dict: 工具执行结果
        """
        logger.info(f"调用MCP工具: {tool_name}")
        logger.debug(f"工具参数: {arguments}")

        try:
            session = await self._get_session()
            url = f"{self.server_url}/tools/call"

            payload = {"name": tool_name, "arguments": arguments}

            async with session.post(url, headers=self._build_headers(), json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"MCP工具调用失败: HTTP {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text}",
                        "content": f"调用MCP工具 {tool_name} 失败",
                    }

                result = await response.json()

                # 提取内容
                content = result.get("content", [])
                if isinstance(content, list) and len(content) > 0:
                    # MCP返回的是content数组
                    text_content = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_content.append(item.get("text", ""))
                        else:
                            text_content.append(str(item))

                    result_text = "\n".join(text_content) if text_content else str(content)
                else:
                    result_text = str(content)

                logger.info(f"MCP工具 {tool_name} 执行成功")
                return {"success": True, "content": result_text, "raw_result": result}

        except aiohttp.ClientError as e:
            logger.error(f"调用MCP工具失败（网络错误）: {e}")
            return {"success": False, "error": str(e), "content": f"网络错误：无法调用工具 {tool_name}"}
        except Exception as e:
            logger.error(f"调用MCP工具时发生错误: {e}")
            return {"success": False, "error": str(e), "content": f"调用工具 {tool_name} 时发生错误"}

    async def list_resources(self) -> list[dict[str, Any]]:
        """
        获取MCP服务器提供的资源列表

        Returns:
            List[Dict]: 资源列表
        """
        logger.info(f"正在从MCP服务器获取资源列表: {self.server_url}")

        try:
            session = await self._get_session()
            url = f"{self.server_url}/resources/list"

            async with session.post(url, headers=self._build_headers(), json={}) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"获取MCP资源列表失败: HTTP {response.status} - {error_text}")
                    return []

                data = await response.json()
                resources = data.get("resources", [])

                logger.info(f"成功获取 {len(resources)} 个MCP资源")
                return resources

        except Exception as e:
            logger.error(f"获取MCP资源列表时发生错误: {e}")
            return []

    async def read_resource(self, resource_uri: str) -> dict[str, Any]:
        """
        读取MCP资源

        Args:
            resource_uri: 资源URI

        Returns:
            Dict: 资源内容
        """
        logger.info(f"读取MCP资源: {resource_uri}")

        try:
            session = await self._get_session()
            url = f"{self.server_url}/resources/read"

            payload = {"uri": resource_uri}

            async with session.post(url, headers=self._build_headers(), json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"读取MCP资源失败: HTTP {response.status} - {error_text}")
                    return {"success": False, "error": error_text}

                result = await response.json()
                logger.info(f"成功读取MCP资源: {resource_uri}")
                return {"success": True, "content": result.get("contents", [])}

        except Exception as e:
            logger.error(f"读取MCP资源时发生错误: {e}")
            return {"success": False, "error": str(e)}
