from src.plugin_system.base.plugin_metadata import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="Affinity Flow Chatter",
    description="Built-in chatter plugin for affinity flow with interest scoring and relationship building",
    usage="This plugin is automatically triggered by the system.",
    version="1.0.0",
    author="MoFox",
    keywords=["chatter", "affinity", "conversation"],
    categories=["Chat", "AI"],
    extra={"is_built_in": True},
)
