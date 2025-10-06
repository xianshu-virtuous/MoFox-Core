from src.plugin_system.base.plugin_metadata import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="权限管理插件（Permission Management）",
    description="通过系统API管理权限",
    usage="该插件提供 `permission_management` command。",
    version="1.0.0",
    author="MoFox-Studio",
    license="GPL-v3.0-or-later",
    repository_url="https://github.com/MoFox-Studio",
    keywords=["plugins", "permission", "management", "built-in"],
    extra={
        "is_built_in": True,
        "plugin_type": "permission",
    },
)
