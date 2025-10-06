from src.plugin_system.base.plugin_metadata import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="Emoji插件 (Emoji Actions)",
    description="可以发送和管理Emoji",
    usage="该插件提供 `emoji` action。",
    version="1.0.0",
    author="SengokuCola",
    license="GPL-v3.0-or-later",
    repository_url="https://github.com/MaiM-with-u/maibot",
    keywords=["emoji", "action", "built-in"],
    categories=["Emoji"],
    extra={
        "is_built_in": True,
        "plugin_type": "action_provider",
    },
)
