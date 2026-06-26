"""Configuration management for modInteractive.

Handles loading, validating, and providing access to JSON configuration.
Creates default config if file is missing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("modInteractive.config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "system": {
        "log_level": "INFO",
        "project_name": "modInteractive"
    },
    "camera": {
        "index": 0,
        "width": 640,
        "height": 480,
        "fps": 15,
        "backend": "v4l2"
    },
    "detection": {
        "enabled": True,
        "mode": "motion",
        "motion_sensitivity": 500,
        "min_motion_area": 1500,
        "frame_skip": 3,
        "warmup_seconds": 2,
        "cooldown_seconds": 10
    },
    "video": {
        "path": "videos/selamlama.mp4",
        "fullscreen": True,
        "volume": 90,
        "player": "mpv"
    },
    "admin": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 8080
    }
}


class Config:
    """Application configuration loaded from JSON file."""

    def __init__(self, config_path: str = "config.json") -> None:
        self._config_path: str = config_path
        self._data: Dict[str, Any] = {}
        self._loaded: bool = False

    def load(self) -> None:
        """Load configuration from JSON file.

        Creates default config if file is missing.
        Merges missing keys with defaults recursively.
        """
        config_file = Path(self._config_path)

        if not config_file.exists():
            logger.warning("Config file not found: %s", self._config_path)
            logger.info("Creating default configuration: %s", self._config_path)
            self._data = dict(DEFAULT_CONFIG)
            self._save_defaults(config_file)
            self._loaded = True
            return

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                file_data: Dict[str, Any] = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in config file: %s - %s",
                         self._config_path, e)
            logger.warning("Falling back to default configuration")
            self._data = dict(DEFAULT_CONFIG)
            return
        except OSError as e:
            logger.error("Cannot read config file: %s - %s",
                         self._config_path, e)
            logger.warning("Falling back to default configuration")
            self._data = dict(DEFAULT_CONFIG)
            return

        # Deep merge: file values override defaults
        self._data = self._deep_merge(dict(DEFAULT_CONFIG), file_data)
        self._loaded = True
        logger.info("Configuration loaded from: %s", self._config_path)

    def _deep_merge(self, base: Dict[str, Any],
                    override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result: Dict[str, Any] = dict(base)
        for key, value in override.items():
            if (key in result and isinstance(result[key], dict)
                    and isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _save_defaults(self, path: Path) -> None:
        """Write default configuration to disk."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
                f.write("\n")
            logger.info("Default configuration saved to: %s", path)
        except OSError as e:
            logger.error("Cannot create default config: %s", e)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a nested configuration value using dot notation.

        Args:
            key_path: Dot-separated key path (e.g. 'camera.index')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if not self._loaded:
            self.load()

        parts = key_path.split(".")
        value: Any = self._data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key_path: str, value: Any) -> None:
        """Set a nested configuration value using dot notation.

        Args:
            key_path: Dot-separated key path (e.g. 'video.path')
            value: Value to set
        """
        if not self._loaded:
            self.load()

        parts = key_path.split(".")
        target = self._data
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        self._save()

    def _save(self) -> None:
        """Write current configuration to disk."""
        try:
            path = Path(self._config_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            logger.error("Cannot save config: %s", e)

    @property
    def data(self) -> Dict[str, Any]:
        """Get all configuration data."""
        if not self._loaded:
            self.load()
        return dict(self._data)

    def check(self) -> None:
        """Run configuration health checks."""
        logger.info("Configuration check:")
        logger.info("  Camera index: %d", self.get("camera.index", 0))
        logger.info("  Detection enabled: %s", self.get("detection.enabled", True))
        logger.info("  Detection mode: %s", self.get("detection.mode", "motion"))
        logger.info("  Cooldown: %d seconds", self.get("detection.cooldown_seconds", 10))

        video = self.get("video.path", "videos/selamlama.mp4")
        abs_video = os.path.abspath(video)
        if os.path.exists(abs_video):
            logger.info("  Video file: found (%s)", abs_video)
        else:
            logger.warning("  Video file: NOT FOUND (%s)", abs_video)

        admin_enabled = self.get("admin.enabled", True)
        if admin_enabled:
            logger.info("  Admin panel: enabled on port %d",
                        self.get("admin.port", 8080))
        else:
            logger.info("  Admin panel: disabled")