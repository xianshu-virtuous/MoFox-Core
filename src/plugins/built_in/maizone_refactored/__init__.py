from src.plugin_system.base.plugin_metadata import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="MaiZone（麦麦空间）- 重构版",
    description="（重构版）让你的麦麦发QQ空间说说、评论、点赞，支持AI配图、定时发送和自动监控功能",
    usage="该插件提供 `send_feed` 和 `read_feed` action，以及 `send_feed` command。",
    version="3.0.0",
    author="MoFox-Studio",
    license="GPL-v3.0",
    repository_url="https://github.com/MoFox-Studio",
    keywords=["QQ空间", "说说", "动态", "评论", "点赞", "自动化", "AI配图"],
    categories=["社交", "自动化", "QQ空间"],
    extra={
        "is_built_in": False,
        "plugin_type": "social",
    },
)
