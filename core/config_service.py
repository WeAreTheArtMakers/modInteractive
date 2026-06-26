"""Configuration service with hot-reload support.

Manages JSON-based configuration with live reload capability.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import Event, EventBus, SystemEvents

logger = logging.getLogger(__name__)


class ConfigService:
    """Configuration management service with hot-reload."""

    def __init__(
        self,
        event_bus: EventBus,
        config_path: str = "config.json",
    ) -> None:
        """Initialize config service.

        Args:
            event_bus: System event bus
            config_path: Path to configuration file
        """
        self._event_bus = event_bus
        self._config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._watcher_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._last_mtime: float = 0.0
        self._reload_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start config service and load configuration."""
        await self.load()
        self._running = True
        self._watcher_task = asyncio.create_task(self._watch_config())
        logger.info(f"Config service started: {self._config_path}")

    async def stop(self) -> None:
        """Stop config service."""
        self._running = False
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
        logger.info("Config service stopped")

    async def load(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns:
            Loaded configuration dictionary
        """
        if not self._config_path.exists():
            logger.warning(f"Config file not found: {self._config_path}, using defaults")
            self._config = self._get_default_config()
            await self.save()
            return self._config

        try:
            with open(self._config_path, "r") as f:
                self._config = json.load(f)
            self._last_mtime = os.path.getmtime(self._config_path)
            logger.info("Configuration loaded successfully")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}")
            self._config = self._get_default_config()

        return self._config

    async def save(self) -> bool:
        """Save current configuration to file.

        Returns:
            True if save succeeded
        """
        try:
            with open(self._config_path, "w") as f:
                json.dump(self._config, f, indent=2)
            self._last_mtime = os.path.getmtime(self._config_path)
            logger.info("Configuration saved")
            return True
        except IOError as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key.

        Args:
            key: Dot-separated configuration key (e.g., 'detection.confidence')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-separated key.

        Args:
            key: Dot-separated configuration key
            value: Value to set
        """
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration.

        Returns:
            Complete configuration dictionary
        """
        return dict(self._config)

    def on_reload(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback for config reload events.

        Args:
            callback: Function to call on config reload
        """
        self._reload_callbacks.append(callback)

    async def _watch_config(self) -> None:
        """Watch configuration file for changes."""
        while self._running:
            try:
                if self._config_path.exists():
                    mtime = os.path.getmtime(self._config_path)
                    if mtime > self._last_mtime:
                        logger.info("Configuration file changed, reloading")
                        await self._reload()
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Config watcher error: {e}")
                await asyncio.sleep(5)

    async def _reload(self) -> None:
        """Reload configuration and notify listeners."""
        async with self._lock:
            old_config = dict(self._config)
            await self.load()
            if self._config != old_config:
                await self._event_bus.publish(
                    Event(
                        event_type=SystemEvents.CONFIG_CHANGED,
                        source="config_service",
                        data={"old": old_config, "new": self._config},
                    )
                )
                for callback in self._reload_callbacks:
                    try:
                        callback(self._config)
                    except Exception as e:
                        logger.error(f"Config reload callback error: {e}")

    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Get default configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "system": {
                "name": "modInteractive",
                "version": "2.0.0",
                "log_level": "INFO",
                "log_retention_days": 7,
                "auto_start": True,
                "watchdog_timeout": 10,
            },
            "camera": {
                "device_id": 0,
                "resolution": {"width": 640, "height": 480},
                "fps": 15,
                "brightness": 0,
                "contrast": 0,
                "auto_reconnect": True,
                "reconnect_interval": 3,
            },
            "detection": {
                "mode": "hybrid",
                "confidence_threshold": 0.55,
                "cooldown_seconds": 8,
                "frame_skip": 3,
                "motion_sensitivity": 0.03,
                "enable_roi": False,
                "roi": {"x": 0, "y": 0, "width": 1, "height": 1},
                "model_path": "models/yolov8n.pt",
            },
            "video": {
                "fade_in_duration": 0.8,
                "fade_out_duration": 0.8,
                "volume": 90,
                "fullscreen": True,
                "playback_mode": "single",
                "loop_videos": False,
                "playlist": ["videos/selamlama.mp4"],
            },
            "ui": {
                "theme": "dark",
                "language": "en",
                "touchscreen_mode": True,
                "show_preview": True,
            },
            "plugins": {
                "enabled": [],
                "paths": ["plugins/detection", "plugins/playback", "plugins/ui"],
            },
        }
