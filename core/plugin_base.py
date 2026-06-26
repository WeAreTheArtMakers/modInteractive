"""Plugin system base for modInteractive.

Supports plugins for detection engines, playback engines, and UI modules.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class PluginType:
    """Plugin type constants."""
    DETECTION = "detection"
    PLAYBACK = "playback"
    UI = "ui"


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""
    name: str
    version: str
    plugin_type: str
    description: str
    author: str = "unknown"
    path: str = ""
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


class BasePlugin(ABC):
    """Abstract base class for all plugins."""

    def __init__(self, event_bus: EventBus, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize plugin.

        Args:
            event_bus: System event bus
            config: Plugin configuration
        """
        self._event_bus = event_bus
        self._config = config or {}
        self._running = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin resources.

        Returns:
            True if initialization succeeded
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown and cleanup plugin resources."""
        ...

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Get plugin information."""
        ...

    @property
    def is_running(self) -> bool:
        """Check if plugin is running."""
        return self._running

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get plugin configuration value.

        Args:
            key: Configuration key
            default: Default value

        Returns:
            Configuration value
        """
        return self._config.get(key, default)


class PluginManager:
    """Manages discovery, loading, and lifecycle of plugins."""

    def __init__(self, event_bus: EventBus, plugin_paths: Optional[List[str]] = None) -> None:
        """Initialize plugin manager.

        Args:
            event_bus: System event bus
            plugin_paths: Directories to scan for plugins
        """
        self._event_bus = event_bus
        self._plugin_paths = plugin_paths or []
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_infos: Dict[str, PluginInfo] = {}

    def add_plugin_path(self, path: str) -> None:
        """Add directory to plugin search paths.

        Args:
            path: Directory path for plugins
        """
        abs_path = os.path.abspath(path)
        if abs_path not in self._plugin_paths:
            self._plugin_paths.append(abs_path)
            logger.info(f"Added plugin path: {abs_path}")

    def discover_plugins(self) -> List[PluginInfo]:
        """Discover available plugins in search paths.

        Returns:
            List of discovered plugin info
        """
        discovered = []

        for path in self._plugin_paths:
            if not os.path.exists(path):
                continue

            for file in os.listdir(path):
                if file.endswith(".py") and not file.startswith("__"):
                    plugin_path = os.path.join(path, file)
                    try:
                        module_name = file[:-3]
                        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)

                            for name, obj in inspect.getmembers(module):
                                if (inspect.isclass(obj) and
                                    issubclass(obj, BasePlugin) and
                                    obj is not BasePlugin):

                                    if hasattr(obj, 'plugin_info'):
                                        info = obj.plugin_info
                                    else:
                                        info = PluginInfo(
                                            name=name,
                                            version="1.0.0",
                                            plugin_type=self._detect_plugin_type(obj),
                                            description=obj.__doc__ or "",
                                            path=plugin_path,
                                        )
                                    discovered.append(info)
                                    self._plugin_infos[info.name] = info
                                    logger.info(f"Discovered plugin: {info.name} ({info.plugin_type})")
                    except Exception as e:
                        logger.error(f"Failed to load plugin {file}: {e}")

        return discovered

    async def load_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Load and initialize a specific plugin.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Initialized plugin instance or None
        """
        if plugin_name in self._plugins:
            return self._plugins[plugin_name]

        info = self._plugin_infos.get(plugin_name)
        if not info:
            logger.error(f"Plugin not found: {plugin_name}")
            return None

        try:
            spec = importlib.util.spec_from_file_location(plugin_name, info.path)
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load plugin: {plugin_name}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BasePlugin) and
                    obj is not BasePlugin):

                    plugin = obj(self._event_bus, info.config)
                    success = await plugin.initialize()
                    if success:
                        self._plugins[plugin_name] = plugin
                        logger.info(f"Plugin loaded: {plugin_name}")
                        return plugin
                    else:
                        logger.error(f"Plugin initialization failed: {plugin_name}")
                        return None

        except Exception as e:
            logger.error(f"Plugin load error: {e}")
            return None

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unloaded successfully
        """
        plugin = self._plugins.pop(plugin_name, None)
        if plugin:
            await plugin.shutdown()
            logger.info(f"Plugin unloaded: {plugin_name}")
            return True
        return False

    async def load_all_plugins(self, plugin_types: Optional[List[str]] = None) -> Dict[str, BasePlugin]:
        """Load all discovered plugins.

        Args:
            plugin_types: Optional filter by plugin types

        Returns:
            Dictionary of loaded plugins
        """
        self.discover_plugins()

        for name, info in self._plugin_infos.items():
            if plugin_types and info.plugin_type not in plugin_types:
                continue
            if not info.enabled:
                continue
            await self.load_plugin(name)

        return dict(self._plugins)

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a loaded plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(name)

    def get_plugins_by_type(self, plugin_type: str) -> Dict[str, BasePlugin]:
        """Get all loaded plugins of a specific type.

        Args:
            plugin_type: Plugin type to filter by

        Returns:
            Dictionary of matching plugins
        """
        result = {}
        for name, plugin in self._plugins.items():
            info = self._plugin_infos.get(name)
            if info and info.plugin_type == plugin_type:
                result[name] = plugin
        return result

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        for name in list(self._plugins.keys()):
            await self.unload_plugin(name)

    @staticmethod
    def _detect_plugin_type(plugin_class: Type) -> str:
        """Detect plugin type from class inheritance or naming.

        Args:
            plugin_class: Plugin class to analyze

        Returns:
            Detected plugin type
        """
        name = plugin_class.__name__.lower()
        if 'detection' in name or 'detect' in name:
            return PluginType.DETECTION
        elif 'playback' in name or 'player' in name:
            return PluginType.PLAYBACK
        elif 'ui' in name or 'panel' in name or 'widget' in name:
            return PluginType.UI
        return PluginType.DETECTION