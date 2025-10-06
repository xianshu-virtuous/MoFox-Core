from src.common.logger import get_logger
from src.plugin_system.base.base_tool import BaseTool
from src.plugin_system.base.component_types import ComponentType

logger = get_logger("tool_api")


def get_tool_instance(tool_name: str) -> BaseTool | None:
    """获取公开工具实例"""
    from src.plugin_system.core import component_registry

    # 获取插件配置
    tool_info = component_registry.get_component_info(tool_name, ComponentType.TOOL)
    if tool_info:
        plugin_config = component_registry.get_plugin_config(tool_info.plugin_name)
    else:
        plugin_config = None

    tool_class: type[BaseTool] = component_registry.get_component_class(tool_name, ComponentType.TOOL)  # type: ignore
    if tool_class:
        return tool_class(plugin_config)

    # 如果不是常规工具，检查是否是MCP工具
    # MCP工具不需要返回实例，会在execute_tool_call中特殊处理
    return None


def get_llm_available_tool_definitions():
    """获取LLM可用的工具定义列表

    Returns:
        List[Tuple[str, Dict[str, Any]]]: 工具定义列表，为[("tool_name", 定义)]
    """
    from src.plugin_system.core import component_registry

    llm_available_tools = component_registry.get_llm_available_tools()
    tool_definitions = [(name, tool_class.get_tool_definition()) for name, tool_class in llm_available_tools.items()]

    # 添加MCP工具
    try:
        from src.plugin_system.utils.mcp_tool_provider import mcp_tool_provider

        mcp_tools = mcp_tool_provider.get_mcp_tool_definitions()
        tool_definitions.extend(mcp_tools)
        if mcp_tools:
            logger.debug(f"已添加 {len(mcp_tools)} 个MCP工具到可用工具列表")
    except Exception as e:
        logger.debug(f"获取MCP工具失败（可能未配置）: {e}")

    return tool_definitions
