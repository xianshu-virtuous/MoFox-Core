"""
Plugin State API
================

该模块提供了用于管理插件和组件状态（启用/禁用）的核心API。
从 plugin_manage_api.py 中抽离出来，专注于状态管理相关功能。

主要功能包括：
- 插件的启用/禁用
- 组件的全局和局部启用/禁用
- 批量组件状态管理
- 插件卸载
- 状态查询与验证
"""

from typing import Any

from src.common.logger import get_logger
from src.plugin_system.base.component_types import ComponentType
from src.plugin_system.core.component_registry import ComponentInfo, component_registry
from src.plugin_system.core.plugin_manager import plugin_manager

# 初始化日志记录器
logger = get_logger("plugin_state_api")


# --------------------------------------------------------------------------------
# Section 1: 插件状态管理 (Plugin State Management)
# --------------------------------------------------------------------------------
# 该部分包含控制插件整体启用/禁用状态的功能。


async def enable_plugin(plugin_name: str) -> bool:
    """
    启用一个已禁用的插件。

    如果插件已经启用，直接返回 True。
    启用插件会同时尝试加载其所有组件。

    Args:
        plugin_name (str): 要启用的插件名称。

    Returns:
        bool: 如果插件成功启用，则为 True。
    """
    plugin_instance = plugin_manager.get_plugin_instance(plugin_name)

    if not plugin_instance:
        # 插件未加载，尝试从注册表加载
        if plugin_name not in plugin_manager.list_registered_plugins():
            logger.error(f"插件 '{plugin_name}' 未注册，无法启用。")
            return False

        # 尝试加载插件
        success, _ = plugin_manager.load_registered_plugin_classes(plugin_name)
        if not success:
            logger.error(f"加载插件 '{plugin_name}' 失败。")
            return False

        logger.info(f"插件 '{plugin_name}' 已成功启用并加载。")
        return True

    # 如果插件已经启用
    if plugin_instance.enable_plugin:
        logger.info(f"插件 '{plugin_name}' 已经处于启用状态。")
        return True

    # 设置插件为启用状态
    plugin_instance.enable_plugin = True
    logger.info(f"插件 '{plugin_name}' 已启用。")
    return True


async def disable_plugin(plugin_name: str, disable_components: bool = True) -> bool:
    """
    禁用一个插件。

    禁用插件不会卸载它，只会标记为禁用状态。
    可选择是否同时禁用该插件下的所有组件。

    Args:
        plugin_name (str): 要禁用的插件名称。
        disable_components (bool): 是否同时禁用该插件下的所有组件。默认为 True。

    Returns:
        bool: 如果插件成功禁用，则为 True。
    """
    plugin_instance = plugin_manager.get_plugin_instance(plugin_name)

    if not plugin_instance:
        logger.warning(f"插件 '{plugin_name}' 未加载，无需禁用。")
        return True

    # 如果需要禁用组件
    if disable_components:
        await disable_all_plugin_components(plugin_name)

    # 设置插件为禁用状态
    plugin_instance.enable_plugin = False
    logger.info(f"插件 '{plugin_name}' 已禁用。")
    return True


async def unload_plugin(plugin_name: str) -> bool:
    """
    完全卸载一个插件。

    这会从内存中移除插件及其所有组件。与禁用不同，卸载后需要重新加载才能使用。

    Args:
        plugin_name (str): 要卸载的插件名称。

    Returns:
        bool: 如果插件成功卸载，则为 True。
    """
    if plugin_name not in plugin_manager.list_loaded_plugins():
        logger.warning(f"插件 '{plugin_name}' 未加载，无需卸载。")
        return True

    return await plugin_manager.remove_registered_plugin(plugin_name)


async def reload_plugin(plugin_name: str) -> bool:
    """
    重新加载指定的插件。

    该函数首先卸载插件，然后重新加载它。

    Args:
        plugin_name (str): 要重载的插件的名称。

    Returns:
        bool: 如果插件成功重载，则为 True。

    Raises:
        ValueError: 如果插件未在插件管理器中注册。
    """
    if plugin_name not in plugin_manager.list_registered_plugins():
        raise ValueError(f"插件 '{plugin_name}' 未注册，无法重载。")
    return await plugin_manager.reload_registered_plugin(plugin_name)


def is_plugin_enabled(plugin_name: str) -> bool:
    """
    检查插件是否处于启用状态。

    Args:
        plugin_name (str): 要检查的插件名称。

    Returns:
        bool: 如果插件已启用，则为 True；如果未加载或已禁用，则为 False。
    """
    plugin_instance = plugin_manager.get_plugin_instance(plugin_name)
    if not plugin_instance:
        return False
    return plugin_instance.enable_plugin


def get_plugin_state(plugin_name: str) -> dict[str, Any] | None:
    """
    获取插件的详细状态信息。

    Args:
        plugin_name (str): 要查询的插件名称。

    Returns:
        dict | None: 包含插件状态信息的字典，如果插件不存在则返回 None。
    """
    plugin_instance = plugin_manager.get_plugin_instance(plugin_name)
    plugin_info = component_registry.get_plugin_info(plugin_name)

    if not plugin_info:
        return None

    is_loaded = plugin_name in plugin_manager.list_loaded_plugins()
    is_enabled = plugin_instance.enable_plugin if plugin_instance else False

    # 统计组件状态
    total_components = len(plugin_info.components)
    enabled_components = sum(1 for c in plugin_info.components if c.enabled)

    return {
        "name": plugin_name,
        "is_loaded": is_loaded,
        "is_enabled": is_enabled,
        "total_components": total_components,
        "enabled_components": enabled_components,
        "disabled_components": total_components - enabled_components,
    }


# --------------------------------------------------------------------------------
# Section 2: 组件状态管理 (Component State Management)
# --------------------------------------------------------------------------------
# 这部分 API 负责控制单个组件的启用和禁用状态，支持全局和局部（临时）范围。


async def set_component_enabled(name: str, component_type: ComponentType, enabled: bool) -> bool:
    """
    在全局范围内启用或禁用一个组件。

    此更改会直接修改组件在注册表中的状态，但此状态是临时的，不会持久化到配置文件中。
    包含一个保护机制，防止禁用最后一个已启用的 Chatter 组件。

    Args:
        name (str): 要操作的组件的名称。
        component_type (ComponentType): 组件的类型。
        enabled (bool): True 表示启用, False 表示禁用。

    Returns:
        bool: 如果操作成功，则为 True。
    """
    # 特殊保护：确保系统中至少有一个 Chatter 组件处于启用状态
    if component_type == ComponentType.CHATTER and not enabled:
        enabled_chatters = component_registry.get_enabled_components_by_type(ComponentType.CHATTER)
        if len(enabled_chatters) <= 1 and name in enabled_chatters:
            logger.warning(f"操作被阻止：不能禁用最后一个启用的 Chatter 组件 ('{name}')。")
            return False

    # 根据 enabled 参数调用相应的注册表方法
    if enabled:
        return component_registry.enable_component(name, component_type)
    else:
        return await component_registry.disable_component(name, component_type)


def set_component_enabled_local(stream_id: str, name: str, component_type: ComponentType, enabled: bool) -> bool:
    """
    在一个特定的 stream_id 上下文中临时启用或禁用组件。

    此状态仅存在于内存中，并且只对指定的 stream_id 有效，不影响全局组件状态。
    同样包含对 Chatter 组件的保护机制。

    Args:
        stream_id (str): 唯一的上下文标识符，例如一个会话ID。
        name (str): 组件名称。
        component_type (ComponentType): 组件类型。
        enabled (bool): True 为启用, False 为禁用。

    Returns:
        bool: 如果操作成功，则为 True。
    """
    # 首先，验证组件是否存在
    component_info = component_registry.get_component_info(name, component_type)
    if not component_info:
        logger.error(f"尝试设置局部状态失败：未找到组件 {name} ({component_type.value})。")
        return False

    # Chatter 唯一性保护（在 stream_id 上下文中）
    if component_type == ComponentType.CHATTER and not enabled:
        enabled_chatters = component_registry.get_enabled_components_by_type(ComponentType.CHATTER, stream_id=stream_id)
        if len(enabled_chatters) <= 1 and name in enabled_chatters:
            logger.warning(f"操作被阻止：在 stream '{stream_id}' 中，不能禁用最后一个启用的 Chatter 组件 ('{name}')。")
            return False

    # 设置局部状态
    component_registry.set_local_component_state(stream_id, name, component_type, enabled)
    logger.info(f"在 stream '{stream_id}' 中，组件 {name} ({component_type.value}) 的局部状态已设置为: {enabled}")
    return True


def clear_local_component_states(stream_id: str) -> None:
    """
    清除指定会话的所有局部组件状态。

    当会话结束时应调用此方法来清理资源。

    Args:
        stream_id (str): 要清除状态的会话ID。
    """
    component_registry.clear_local_component_states(stream_id)
    logger.debug(f"已清除 stream '{stream_id}' 的所有局部组件状态。")


def is_component_enabled(name: str, component_type: ComponentType, stream_id: str | None = None) -> bool:
    """
    检查组件是否在指定上下文中启用。

    Args:
        name (str): 组件名称。
        component_type (ComponentType): 组件类型。
        stream_id (str | None): 可选的会话ID，用于检查局部状态。

    Returns:
        bool: 如果组件启用，则为 True。
    """
    return component_registry.is_component_available(name, component_type, stream_id)


def get_component_state(name: str, component_type: ComponentType) -> dict[str, Any] | None:
    """
    获取组件的详细状态信息。

    Args:
        name (str): 组件名称。
        component_type (ComponentType): 组件类型。

    Returns:
        dict | None: 包含组件状态信息的字典，如果组件不存在则返回 None。
    """
    component_info = component_registry.get_component_info(name, component_type)
    if not component_info:
        return None

    return {
        "name": component_info.name,
        "component_type": component_info.component_type.value,
        "plugin_name": component_info.plugin_name,
        "enabled": component_info.enabled,
        "description": component_info.description,
    }


# --------------------------------------------------------------------------------
# Section 3: 批量组件状态管理 (Batch Component State Management)
# --------------------------------------------------------------------------------
# 这部分 API 提供批量操作组件状态的功能。


async def enable_all_plugin_components(plugin_name: str) -> dict[str, bool]:
    """
    启用指定插件下的所有组件。

    Args:
        plugin_name (str): 插件名称。

    Returns:
        dict[str, bool]: 每个组件名称及其启用操作是否成功的字典。
    """
    plugin_info = component_registry.get_plugin_info(plugin_name)
    if not plugin_info:
        logger.error(f"未找到插件 '{plugin_name}'，无法启用其组件。")
        return {}

    results = {}
    for component_info in plugin_info.components:
        success = component_registry.enable_component(component_info.name, component_info.component_type)
        results[component_info.name] = success
        if success:
            logger.debug(f"已启用组件: {component_info.name} ({component_info.component_type.value})")
        else:
            logger.warning(f"启用组件失败: {component_info.name} ({component_info.component_type.value})")

    logger.info(f"已完成启用插件 '{plugin_name}' 的所有组件，成功: {sum(results.values())}/{len(results)}")
    return results


async def disable_all_plugin_components(plugin_name: str) -> dict[str, bool]:
    """
    禁用指定插件下的所有组件。

    包含对 Chatter 组件的保护机制。

    Args:
        plugin_name (str): 插件名称。

    Returns:
        dict[str, bool]: 每个组件名称及其禁用操作是否成功的字典。
    """
    plugin_info = component_registry.get_plugin_info(plugin_name)
    if not plugin_info:
        logger.error(f"未找到插件 '{plugin_name}'，无法禁用其组件。")
        return {}

    results = {}
    for component_info in plugin_info.components:
        # Chatter 保护检查
        if component_info.component_type == ComponentType.CHATTER:
            enabled_chatters = component_registry.get_enabled_components_by_type(ComponentType.CHATTER)
            if len(enabled_chatters) <= 1 and component_info.name in enabled_chatters:
                logger.warning(
                    f"跳过禁用最后一个 Chatter 组件 '{component_info.name}'，系统至少需要一个启用的 Chatter。"
                )
                results[component_info.name] = False
                continue

        success = await component_registry.disable_component(component_info.name, component_info.component_type)
        results[component_info.name] = success
        if success:
            logger.debug(f"已禁用组件: {component_info.name} ({component_info.component_type.value})")
        else:
            logger.warning(f"禁用组件失败: {component_info.name} ({component_info.component_type.value})")

    logger.info(f"已完成禁用插件 '{plugin_name}' 的所有组件，成功: {sum(results.values())}/{len(results)}")
    return results


async def set_components_enabled_by_type(
    plugin_name: str, component_type: ComponentType, enabled: bool
) -> dict[str, bool]:
    """
    启用或禁用指定插件下特定类型的所有组件。

    Args:
        plugin_name (str): 插件名称。
        component_type (ComponentType): 要操作的组件类型。
        enabled (bool): True 为启用，False 为禁用。

    Returns:
        dict[str, bool]: 每个组件名称及其操作是否成功的字典。
    """
    plugin_info = component_registry.get_plugin_info(plugin_name)
    if not plugin_info:
        logger.error(f"未找到插件 '{plugin_name}'。")
        return {}

    results = {}
    for component_info in plugin_info.components:
        if component_info.component_type != component_type:
            continue

        success = await set_component_enabled(component_info.name, component_type, enabled)
        results[component_info.name] = success

    action = "启用" if enabled else "禁用"
    logger.info(
        f"已完成{action}插件 '{plugin_name}' 的所有 {component_type.value} 组件，"
        f"成功: {sum(results.values())}/{len(results)}"
    )
    return results


async def batch_set_components_enabled(components: list[tuple[str, ComponentType]], enabled: bool) -> dict[str, bool]:
    """
    批量启用或禁用多个组件。

    Args:
        components (list[tuple[str, ComponentType]]): 要操作的组件列表，
            每个元素为 (组件名称, 组件类型) 元组。
        enabled (bool): True 为启用，False 为禁用。

    Returns:
        dict[str, bool]: 每个组件名称及其操作是否成功的字典。
    """
    results = {}
    for name, component_type in components:
        success = await set_component_enabled(name, component_type, enabled)
        results[name] = success

    action = "启用" if enabled else "禁用"
    logger.info(f"批量{action}操作完成，成功: {sum(results.values())}/{len(results)}")
    return results


# --------------------------------------------------------------------------------
# Section 4: 状态查询与统计 (State Querying & Statistics)
# --------------------------------------------------------------------------------
# 这部分 API 提供状态查询和统计功能。


def get_all_plugin_states() -> dict[str, dict[str, Any]]:
    """
    获取所有已加载插件的状态信息。

    Returns:
        dict: 插件名称到状态信息的映射。
    """
    result = {}
    for plugin_name in plugin_manager.list_loaded_plugins():
        state = get_plugin_state(plugin_name)
        if state:
            result[plugin_name] = state
    return result


def get_components_by_state(
    component_type: ComponentType | None = None,
    enabled: bool | None = None,
    plugin_name: str | None = None,
) -> list[ComponentInfo]:
    """
    根据条件筛选组件。

    Args:
        component_type (ComponentType | None): 按组件类型筛选。
        enabled (bool | None): 按启用状态筛选。
        plugin_name (str | None): 按插件名称筛选。

    Returns:
        list[ComponentInfo]: 符合条件的组件信息列表。
    """
    results = []

    # 确定要搜索的组件类型
    types_to_search = [component_type] if component_type else list(ComponentType)

    for comp_type in types_to_search:
        components = component_registry.get_components_by_type(comp_type)
        for info in components.values():
            # 按启用状态筛选
            if enabled is not None and info.enabled != enabled:
                continue
            # 按插件名称筛选
            if plugin_name is not None and info.plugin_name != plugin_name:
                continue
            results.append(info)

    return results


def get_disabled_components(plugin_name: str | None = None) -> list[ComponentInfo]:
    """
    获取所有被禁用的组件。

    Args:
        plugin_name (str | None): 可选，仅获取指定插件的禁用组件。

    Returns:
        list[ComponentInfo]: 禁用组件的信息列表。
    """
    return get_components_by_state(enabled=False, plugin_name=plugin_name)


def get_enabled_components(plugin_name: str | None = None) -> list[ComponentInfo]:
    """
    获取所有已启用的组件。

    Args:
        plugin_name (str | None): 可选，仅获取指定插件的启用组件。

    Returns:
        list[ComponentInfo]: 启用组件的信息列表。
    """
    return get_components_by_state(enabled=True, plugin_name=plugin_name)


def get_state_statistics() -> dict[str, Any]:
    """
    获取整体状态统计信息。

    Returns:
        dict: 包含插件和组件状态统计的字典。
    """
    loaded_plugins = plugin_manager.list_loaded_plugins()
    registered_plugins = plugin_manager.list_registered_plugins()
    failed_plugins = list(plugin_manager.failed_plugins.keys())

    # 统计启用/禁用的插件数量
    enabled_plugins = sum(1 for name in loaded_plugins if is_plugin_enabled(name))

    # 统计各类型组件数量
    component_stats = {}
    total_enabled = 0
    total_disabled = 0

    for comp_type in ComponentType:
        all_components = component_registry.get_components_by_type(comp_type)
        enabled_count = sum(1 for info in all_components.values() if info.enabled)
        disabled_count = len(all_components) - enabled_count

        component_stats[comp_type.value] = {
            "total": len(all_components),
            "enabled": enabled_count,
            "disabled": disabled_count,
        }
        total_enabled += enabled_count
        total_disabled += disabled_count

    return {
        "plugins": {
            "loaded": len(loaded_plugins),
            "registered": len(registered_plugins),
            "failed": len(failed_plugins),
            "enabled": enabled_plugins,
            "disabled": len(loaded_plugins) - enabled_plugins,
        },
        "components": {
            "total": total_enabled + total_disabled,
            "enabled": total_enabled,
            "disabled": total_disabled,
            "by_type": component_stats,
        },
    }


# --------------------------------------------------------------------------------
# Section 5: 工具函数 (Utility Functions)
# --------------------------------------------------------------------------------
# 这部分提供辅助工具函数。


def validate_component_exists(name: str, component_type: ComponentType) -> bool:
    """
    验证组件是否存在于注册表中。

    Args:
        name (str): 组件名称。
        component_type (ComponentType): 组件类型。

    Returns:
        bool: 如果组件存在，则为 True。
    """
    return component_registry.get_component_info(name, component_type) is not None


def get_plugin_component_summary(plugin_name: str) -> dict[str, Any] | None:
    """
    获取插件的组件摘要信息。

    Args:
        plugin_name (str): 插件名称。

    Returns:
        dict | None: 包含组件摘要的字典，如果插件不存在则返回 None。
    """
    plugin_info = component_registry.get_plugin_info(plugin_name)
    if not plugin_info:
        return None

    # 按类型统计组件
    by_type = {}
    for comp_type in ComponentType:
        components = [c for c in plugin_info.components if c.component_type == comp_type]
        if components:
            enabled = sum(1 for c in components if c.enabled)
            by_type[comp_type.value] = {
                "total": len(components),
                "enabled": enabled,
                "disabled": len(components) - enabled,
                "names": [c.name for c in components],
            }

    return {
        "plugin_name": plugin_name,
        "total_components": len(plugin_info.components),
        "by_type": by_type,
    }
