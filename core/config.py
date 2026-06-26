"""Configuration management for modInteractive kiosk system.

Handles loading, validating, and providing access to JSON configuration.
Creates default config if file is missing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("modInteractive.config")

# Default configuration
DEFAULT_CONFIG: Dict[str, Any] = {
    "video_path": "videos/selamlama.mp4",
    "camera_index": 0,
    "camera_width": 640,
    "camera_height": 480,
    "camera_fps": 15,
    "detection_enabled": True,
    "detection_mode": "motion",
    "detection_confidence": 0.5,
    "motion_sensitivity": 500,
    "cooldown_seconds": 10,
    "fullscreen": True,
    "log_level": "INFO",
    "log_max_bytes": 5_242_880,
    "log_backup_count": 3,
    "player": "mpv",
    "player_volume": 90,
}


class Config:
    """Application configuration loaded from JSON file."""

    def __init__(self, config_path: str = "config.json") -> None:
        self._config_path: str = config_path
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._loaded: bool = False

    def load(self) -> None:
        """Load configuration from JSON file.

        Creates default config if file doesn't exist.
        Merges missing keys with defaults.
        """
        config_file = Path(self._config_path)

        if not config_file.exists():
            logger.warning("Config file not found: %s", self._config_path)
            logger.info("Creating default configuration: %s", self._config_path)
            self._save_defaults(config_file)
            self._loaded = True
            return

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                file_data: Dict[str, Any] = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in config file: %s - %s", self._config_path, e)
            logger.warning("Falling back to default configuration")
            return
        except OSError as e:
            logger.error("Cannot read config file: %s - %s", self._config_path, e)
            logger.warning("Falling back to default configuration")
            return

        # Merge: file values override defaults, but missing keys get defaults
        self._data = {**DEFAULT_CONFIG, **file_data}
        self._loaded = True
        logger.info("Configuration loaded from: %s", self._config_path)

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

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if not self._loaded:
            self.load()
        return self._data.get(key, default)

    @property
    def data(self) -> Dict[str, Any]:
        """Get all configuration data."""
        if not self._loaded:
            self.load()
        return dict(self._data)

    @property
    def video_path(self) -> str:
        """Get resolved video path."""
        path = self.get("video_path", "videos/selamlama.mp4")
        return os.path.abspath(path)

    @property
    def camera_index(self) -> int:
        """Get camera device index."""
        return self.get("camera_index", 0)

    @property
    def detection_enabled(self) -> bool:
        """Check if detection is enabled."""
        return self.get("detection_enabled", True)

    @property
    def detection_mode(self) -> str:
        """Get detection mode (motion or yolo)."""
        return self.get("detection_mode", "motion")

    @property
    def fullscreen(self) -> bool:
        """Check if fullscreen mode is enabled."""
        return self.get("fullscreen", True)

    @property
    def cooldown_seconds(self) -> int:
        """Get cooldown between detections in seconds."""
        return self.get("cooldown_seconds", 10)

    def check(self) -> None:
        """Run configuration checks and log warnings."""
        video = self.video_path
        if not os.path.exists(video):
            logger.warning("Video file not found: %s", video)
        else:
            logger.info("Video file found: %s", video)

        logger.info("Detection mode: %s", self.detection_mode)
        logger.info("Camera index: %d", self.camera_index)
        logger.info("Cooldown: %d seconds", self.cooldown_seconds)
        logger.info("Fullscreen: %s", self.fullscreen)