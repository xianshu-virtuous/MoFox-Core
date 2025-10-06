from src.plugin_system.base.plugin_metadata import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="MoFox-Bot主动思考",
    description="主动思考插件",
    usage="该插件由系统自动触发。",
    version="1.0.0",
    author="MoFox-Studio",
    license="GPL-v3.0-or-later",
    repository_url="https://github.com/MoFox-Studio",
    keywords=["主动思考", "自己发消息"],
    categories=["Chat", "Integration"],
    extra={"is_built_in": True, "plugin_type": "functional"},
)
