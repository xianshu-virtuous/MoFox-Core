"""
插件热重载模块

使用 Watchdog 监听插件目录变化，自动重载插件
"""

import os
import time
from pathlib import Path
from threading import Thread
from typing import Dict, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.common.logger import get_logger
from .plugin_manager import plugin_manager

logger = get_logger("plugin_hot_reload")


class PluginFileHandler(FileSystemEventHandler):
    """插件文件变化处理器"""

    def __init__(self, hot_reload_manager):
        super().__init__()
        self.hot_reload_manager = hot_reload_manager
        self.pending_reloads: Set[str] = set()  # 待重载的插件名称
        self.last_reload_time: Dict[str, float] = {}  # 上次重载时间
        self.debounce_delay = 1.0  # 防抖延迟（秒）

    def on_modified(self, event):
        """文件修改事件"""
        if not event.is_directory and (event.src_path.endswith('.py') or event.src_path.endswith('.toml')):
            self._handle_file_change(event.src_path, "modified")

    def on_created(self, event):
        """文件创建事件"""
        if not event.is_directory and (event.src_path.endswith('.py') or event.src_path.endswith('.toml')):
            self._handle_file_change(event.src_path, "created")

    def on_deleted(self, event):
        """文件删除事件"""
        if not event.is_directory and (event.src_path.endswith('.py') or event.src_path.endswith('.toml')):
            self._handle_file_change(event.src_path, "deleted")

    def _handle_file_change(self, file_path: str, change_type: str):
        """处理文件变化"""
        try:
            # 获取插件名称
            plugin_name = self._get_plugin_name_from_path(file_path)
            if not plugin_name:
                return

            current_time = time.time()
            last_time = self.last_reload_time.get(plugin_name, 0)

            # 防抖处理，避免频繁重载
            if current_time - last_time < self.debounce_delay:
                return

            file_name = Path(file_path).name
            logger.info(f"📁 检测到插件文件变化: {file_name} ({change_type})")

            # 如果是删除事件，处理关键文件删除
            if change_type == "deleted":
                if file_name == "plugin.py":
                    if plugin_name in plugin_manager.loaded_plugins:
                        logger.info(f"🗑️ 插件主文件被删除，卸载插件: {plugin_name}")
                        self.hot_reload_manager._unload_plugin(plugin_name)
                    return
                elif file_name == "manifest.toml":
                    if plugin_name in plugin_manager.loaded_plugins:
                        logger.info(f"🗑️ 插件配置文件被删除，卸载插件: {plugin_name}")
                        self.hot_reload_manager._unload_plugin(plugin_name)
                    return

            # 对于修改和创建事件，都进行重载
            # 添加到待重载列表
            self.pending_reloads.add(plugin_name)
            self.last_reload_time[plugin_name] = current_time

            # 延迟重载，避免文件正在写入时重载
            reload_thread = Thread(
                target=self._delayed_reload,
                args=(plugin_name,),
                daemon=True
            )
            reload_thread.start()

        except Exception as e:
            logger.error(f"❌ 处理文件变化时发生错误: {e}")

    def _delayed_reload(self, plugin_name: str):
        """延迟重载插件"""
        try:
            time.sleep(self.debounce_delay)

            if plugin_name in self.pending_reloads:
                self.pending_reloads.remove(plugin_name)
                self.hot_reload_manager._reload_plugin(plugin_name)

        except Exception as e:
            logger.error(f"❌ 延迟重载插件 {plugin_name} 时发生错误: {e}")

    def _get_plugin_name_from_path(self, file_path: str) -> str:
        """从文件路径获取插件名称"""
        try:
            path = Path(file_path)

            # 检查是否在监听的插件目录中
            plugin_root = Path(self.hot_reload_manager.watch_directory)
            if not path.is_relative_to(plugin_root):
                return ""

            # 获取插件目录名（插件名）
            relative_path = path.relative_to(plugin_root)
            plugin_name = relative_path.parts[0]

            # 确认这是一个有效的插件目录（检查是否有 plugin.py 或 manifest.toml）
            plugin_dir = plugin_root / plugin_name
            if plugin_dir.is_dir() and ((plugin_dir / "plugin.py").exists() or (plugin_dir / "manifest.toml").exists()):
                return plugin_name

            return ""

        except Exception:
            return ""


class PluginHotReloadManager:
    """插件热重载管理器"""

    def __init__(self, watch_directory: str = None):
        print("fuck")
        print(os.getcwd())
        self.watch_directory = os.path.join(os.getcwd(), "plugins")
        self.observer = None
        self.file_handler = None
        self.is_running = False

        # 确保监听目录存在
        if not os.path.exists(self.watch_directory):
            os.makedirs(self.watch_directory, exist_ok=True)
            logger.info(f"创建插件监听目录: {self.watch_directory}")

    def start(self):
        """启动热重载监听"""
        if self.is_running:
            logger.warning("插件热重载已经在运行中")
            return

        try:
            self.observer = Observer()
            self.file_handler = PluginFileHandler(self)

            self.observer.schedule(
                self.file_handler,
                self.watch_directory,
                recursive=True
            )

            self.observer.start()
            self.is_running = True

            logger.info("🚀 插件热重载已启动，监听目录: plugins")

        except Exception as e:
            logger.error(f"❌ 启动插件热重载失败: {e}")
            self.is_running = False

    def stop(self):
        """停止热重载监听"""
        if not self.is_running:
            return

        if self.observer:
            self.observer.stop()
            self.observer.join()

        self.is_running = False

    def _reload_plugin(self, plugin_name: str):
        """重载指定插件"""
        try:
            logger.info(f"🔄 开始重载插件: {plugin_name}")

            if plugin_manager.reload_plugin(plugin_name):
                logger.info(f"✅ 插件重载成功: {plugin_name}")
            else:
                logger.error(f"❌ 插件重载失败: {plugin_name}")

        except Exception as e:
            logger.error(f"❌ 重载插件 {plugin_name} 时发生错误: {e}")

    def _unload_plugin(self, plugin_name: str):
        """卸载指定插件"""
        try:
            logger.info(f"🗑️ 开始卸载插件: {plugin_name}")

            if plugin_manager.unload_plugin(plugin_name):
                logger.info(f"✅ 插件卸载成功: {plugin_name}")
            else:
                logger.error(f"❌ 插件卸载失败: {plugin_name}")

        except Exception as e:
            logger.error(f"❌ 卸载插件 {plugin_name} 时发生错误: {e}")

    def reload_all_plugins(self):
        """重载所有插件"""
        try:
            logger.info("🔄 开始重载所有插件...")

            # 获取当前已加载的插件列表
            loaded_plugins = list(plugin_manager.loaded_plugins.keys())

            success_count = 0
            fail_count = 0

            for plugin_name in loaded_plugins:
                if plugin_manager.reload_plugin(plugin_name):
                    success_count += 1
                else:
                    fail_count += 1

            logger.info(f"✅ 插件重载完成: 成功 {success_count} 个，失败 {fail_count} 个")

        except Exception as e:
            logger.error(f"❌ 重载所有插件时发生错误: {e}")

    def get_status(self) -> dict:
        """获取热重载状态"""
        return {
            "is_running": self.is_running,
            "watch_directory": self.watch_directory,
            "loaded_plugins": len(plugin_manager.loaded_plugins),
            "failed_plugins": len(plugin_manager.failed_plugins),
        }


# 全局热重载管理器实例
hot_reload_manager = PluginHotReloadManager()
