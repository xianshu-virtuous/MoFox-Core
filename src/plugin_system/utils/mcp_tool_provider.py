"""
MCP工具提供器 - 简化版
直接集成到工具系统，无需复杂的插件架构
"""

from typing import Any

from src.common.logger import get_logger
from src.plugin_system.utils.mcp_connector import MCPConnector

logger = get_logger("MCP工具提供器")


class MCPToolProvider:
    """MCP工具提供器单例"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not MCPToolProvider._initialized:
            self.connectors: dict[str, MCPConnector] = {}
            self.mcp_tools: dict[str, dict[str, Any]] = {}
            """格式: {tool_full_name: {"connector": connector, "original_name": name, "definition": def}}"""
            MCPToolProvider._initialized = True

    async def initialize(self, mcp_servers: list[dict]):
        """
        初始化MCP服务器连接

        Args:
            mcp_servers: MCP服务器配置列表
        """
        logger.info(f"初始化MCP工具提供器，共{len(mcp_servers)}个服务器")

        for server_config in mcp_servers:
            await self._connect_server(server_config)

        logger.info(f"MCP工具提供器初始化完成，共注册{len(self.mcp_tools)}个工具")

    async def _connect_server(self, config: dict):
        """连接单个MCP服务器"""
        name = config.get("name", "unnamed")
        url = config.get("url")
        api_key = config.get("api_key")
        enabled = config.get("enabled", True)

        if not enabled or not url:
            return

        logger.info(f"连接MCP服务器: {name} ({url})")

        connector = MCPConnector(url, api_key, config.get("timeout", 30))
        self.connectors[name] = connector

        try:
            tools = await connector.list_tools()

            for tool_name, tool_def in tools.items():
                # 使用服务器名作前缀
                full_name = f"{name}_{tool_name}"
                self.mcp_tools[full_name] = {
                    "connector": connector,
                    "original_name": tool_name,
                    "definition": tool_def,
                    "server_name": name,
                }

            logger.info(f"从{name}获取{len(tools)}个工具")

        except Exception as e:
            logger.error(f"连接MCP服务器{name}失败: {e}")

    def get_mcp_tool_definitions(self) -> list[tuple[str, dict[str, Any]]]:
        """
        获取所有MCP工具定义（适配Bot的工具格式）

        Returns:
            List[Tuple[str, dict]]: [(tool_name, tool_definition), ...]
        """
        definitions = []

        for full_name, tool_info in self.mcp_tools.items():
            mcp_def = tool_info["definition"]
            input_schema = mcp_def.get("input_schema", {})

            # 转换为Bot的工具格式
            bot_tool_def = {
                "name": full_name,
                "description": mcp_def.get("description", f"MCP工具: {full_name}"),
                "parameters": self._convert_schema_to_parameters(input_schema),
            }

            definitions.append((full_name, bot_tool_def))

        return definitions

    def _convert_schema_to_parameters(self, schema: dict) -> list[tuple]:
        """
        将MCP的JSON Schema转换为Bot的参数格式

        Args:
            schema: MCP的inputSchema

        Returns:
            Bot的parameters格式
        """
        from src.plugin_system.base.component_types import ToolParamType

        parameters = []
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        type_mapping = {
            "string": ToolParamType.STRING,
            "integer": ToolParamType.INTEGER,
            "number": ToolParamType.FLOAT,
            "boolean": ToolParamType.BOOLEAN,
        }

        for param_name, param_def in properties.items():
            param_type = type_mapping.get(param_def.get("type", "string"), ToolParamType.STRING)
            description = param_def.get("description", "")
            is_required = param_name in required
            enum_values = param_def.get("enum", None)

            parameters.append((param_name, param_type, description, is_required, enum_values))

        return parameters

    async def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        调用MCP工具

        Args:
            tool_name: 工具全名（包含前缀）
            arguments: 参数

        Returns:
            工具执行结果
        """
        if tool_name not in self.mcp_tools:
            return {"content": f"MCP工具{tool_name}不存在"}

        tool_info = self.mcp_tools[tool_name]
        connector = tool_info["connector"]
        original_name = tool_info["original_name"]

        logger.info(f"调用MCP工具: {tool_name}")

        result = await connector.call_tool(original_name, arguments)

        if result.get("success"):
            return {"content": result.get("content", "")}
        else:
            return {"content": f"工具执行失败: {result.get('error', '未知错误')}"}

    async def close(self):
        """关闭所有连接"""
        for name, connector in self.connectors.items():
            try:
                await connector.close()
            except Exception as e:
                logger.error(f"关闭MCP连接{name}失败: {e}")


# 全局单例
mcp_tool_provider = MCPToolProvider()
