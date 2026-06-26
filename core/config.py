from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("modInteractive.config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "system": {
        "log_level": "INFO",
        "project_name": "modInteractive",
        "version": "1.1.0",
    },
    "trigger": {
        "source": "camera",
    },
    "camera": {
        "index": 0,
        "width": 640,
        "height": 480,
        "fps": 15,
        "backend": "v4l2",
    },
    "pir": {
        "gpio_pin": 17,
        "active_high": True,
        "pull_up": False,
        "bounce_time_ms": 500,
        "settle_seconds": 30,
        "poll_interval": 0.05,
    },
    "detection": {
        "enabled": True,
        "mode": "motion",
        "motion_sensitivity": 500,
        "min_motion_area": 1500,
        "frame_skip": 3,
        "warmup_seconds": 2,
        "cooldown_seconds": 10,
    },
    "video": {
        "path": "videos/selamlama.mp4",
        "fullscreen": True,
        "volume": 90,
        "player": "mpv",
    },
    "admin": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 8080,
    },
}


class Config:
    def __init__(self, config_path: str = "config.json") -> None:
        self._config_path = str(Path(config_path).expanduser().resolve())
        self._path = Path(self._config_path)
        self._data: Dict[str, Any] = {}
        self._loaded = False

    @property
    def path(self) -> str:
        return self._config_path

    @property
    def base_dir(self) -> Path:
        return self._path.parent

    @property
    def data(self) -> Dict[str, Any]:
        if not self._loaded:
            self.load()
        return copy.deepcopy(self._data)

    def load(self) -> None:
        if not self._path.exists():
            logger.warning("Config file not found: %s", self._path)
            self._data = self._default_data()
            self._validate_and_normalize()
            self._loaded = True
            self.save()
            return

        try:
            file_data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in config file: %s - %s", self._path, exc)
            self._data = self._default_data()
            self._validate_and_normalize()
            self._loaded = True
            return
        except OSError as exc:
            logger.error("Cannot read config file: %s - %s", self._path, exc)
            self._data = self._default_data()
            self._validate_and_normalize()
            self._loaded = True
            return

        if not isinstance(file_data, dict):
            logger.error("Config root must be a JSON object: %s", self._path)
            self._data = self._default_data()
            self._validate_and_normalize()
            self._loaded = True
            return

        self._data = self._deep_merge(self._default_data(), file_data)
        self._validate_and_normalize()
        self._loaded = True
        logger.info("Configuration loaded from: %s", self._path)

    def reload(self) -> None:
        self._loaded = False
        self.load()

    def save(self) -> bool:
        if not self._loaded:
            if not self._data:
                self._data = self._default_data()
            self._validate_and_normalize()
            self._loaded = True

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info("Configuration saved to: %s", self._path)
            return True
        except OSError as exc:
            logger.error("Cannot save config file: %s - %s", self._path, exc)
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        if not self._loaded:
            self.load()

        if not key_path:
            return default

        value: Any = self._data
        for part in key_path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any, save: bool = True) -> None:
        if not key_path:
            raise ValueError("key_path cannot be empty")

        if not self._loaded:
            self.load()

        self._assign(key_path, value)
        self._validate_and_normalize()

        if save:
            self.save()

    def update(self, values: Dict[str, Any], save: bool = True) -> None:
        if not isinstance(values, dict):
            raise TypeError("values must be a dictionary")

        if not self._loaded:
            self.load()

        self._data = self._deep_merge(self._data, values)
        self._validate_and_normalize()

        if save:
            self.save()

    def update_from_flat(self, values: Dict[str, Any], save: bool = True) -> None:
        if not isinstance(values, dict):
            raise TypeError("values must be a dictionary")

        if not self._loaded:
            self.load()

        for key_path, value in values.items():
            self._assign(str(key_path), value)

        self._validate_and_normalize()

        if save:
            self.save()

    def resolve_path(self, key_path: str, default: str = "") -> Path:
        raw_value = str(self.get(key_path, default)).strip()
        path = Path(raw_value).expanduser()

        if not path.is_absolute():
            path = self.base_dir / path

        return path.resolve()

    def check(self) -> None:
        if not self._loaded:
            self.load()

        logger.info("Configuration check")
        logger.info("Config path: %s", self._path)
        logger.info("Trigger source: %s", self.get("trigger.source", "camera"))
        logger.info("Camera index: %s", self.get("camera.index", 0))
        logger.info("PIR GPIO pin: %s", self.get("pir.gpio_pin", 17))
        logger.info(
            "Camera resolution: %sx%s",
            self.get("camera.width", 640),
            self.get("camera.height", 480),
        )
        logger.info("Camera FPS: %s", self.get("camera.fps", 15))
        logger.info("Camera backend: %s", self.get("camera.backend", "v4l2"))
        logger.info("Detection enabled: %s", self.get("detection.enabled", True))
        logger.info("Detection mode: %s", self.get("detection.mode", "motion"))
        logger.info("Cooldown: %s seconds", self.get("detection.cooldown_seconds", 10))

        video_path = self.resolve_path("video.path", "videos/selamlama.mp4")

        if video_path.exists():
            logger.info("Video file: found (%s)", video_path)
        else:
            logger.warning("Video file: NOT FOUND (%s)", video_path)

        if self.get("admin.enabled", True):
            logger.info("Admin panel: enabled on port %s", self.get("admin.port", 8080))
        else:
            logger.info("Admin panel: disabled")

    def _default_data(self) -> Dict[str, Any]:
        return copy.deepcopy(DEFAULT_CONFIG)

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _validate_and_normalize(self) -> None:
        self._ensure_section("system")
        self._ensure_section("trigger")
        self._ensure_section("camera")
        self._ensure_section("pir")
        self._ensure_section("detection")
        self._ensure_section("video")
        self._ensure_section("admin")

        self._set_string("trigger.source", "camera", allowed={"camera", "pir"})

        self._set_camera_index("camera.index", 0)
        self._set_int("camera.width", 640, minimum=1, maximum=3840)
        self._set_int("camera.height", 480, minimum=1, maximum=2160)
        self._set_int("camera.fps", 15, minimum=1, maximum=60)
        self._set_string("camera.backend", "v4l2", allowed={"auto", "v4l2"})

        self._set_int("pir.gpio_pin", 17, minimum=0, maximum=27)
        self._set_bool("pir.active_high", True)
        self._set_bool("pir.pull_up", False)
        self._set_int("pir.bounce_time_ms", 500, minimum=0, maximum=5000)
        self._set_int("pir.settle_seconds", 30, minimum=0, maximum=120)
        self._set_float("pir.poll_interval", 0.05, minimum=0.01, maximum=5.0)

        self._set_bool("detection.enabled", True)
        self._set_string("detection.mode", "motion", allowed={"motion"})
        self._set_int("detection.motion_sensitivity", 500, minimum=1, maximum=100000)
        self._set_int("detection.min_motion_area", 1500, minimum=1, maximum=100000)
        self._set_int("detection.frame_skip", 3, minimum=1, maximum=30)
        self._set_int("detection.warmup_seconds", 2, minimum=0, maximum=60)
        self._set_int("detection.cooldown_seconds", 10, minimum=0, maximum=600)

        self._set_string("video.path", "videos/selamlama.mp4")
        self._set_bool("video.fullscreen", True)
        self._set_int("video.volume", 90, minimum=0, maximum=100)
        self._set_string("video.player", "mpv")

        self._set_bool("admin.enabled", True)
        self._set_string("admin.host", "0.0.0.0")
        self._set_int("admin.port", 8080, minimum=1, maximum=65535)

        self._set_string("system.log_level", "INFO", allowed={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
        self._set_string("system.project_name", "modInteractive")
        self._set_string("system.version", "1.1.0")

    def _ensure_section(self, section: str) -> None:
        if not isinstance(self._data.get(section), dict):
            self._data[section] = {}

    def _set_camera_index(self, key_path: str, default: int) -> None:
        raw_value = self.get(key_path, default)

        if isinstance(raw_value, int):
            value: Any = max(0, raw_value)
        elif isinstance(raw_value, str):
            stripped = raw_value.strip()

            if stripped.isdigit():
                value = max(0, int(stripped))
            elif stripped:
                value = stripped
            else:
                value = default
        else:
            try:
                value = max(0, int(raw_value))
            except (TypeError, ValueError):
                value = default

        self._assign(key_path, value)

    def _set_int(
        self,
        key_path: str,
        default: int,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
    ) -> None:
        raw_value = self.get(key_path, default)

        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            logger.warning("Invalid integer config value %s=%r; using %d", key_path, raw_value, default)
            value = default

        if minimum is not None and value < minimum:
            value = minimum

        if maximum is not None and value > maximum:
            value = maximum

        self._assign(key_path, value)

    def _set_float(
        self,
        key_path: str,
        default: float,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None,
    ) -> None:
        raw_value = self.get(key_path, default)

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            logger.warning("Invalid float config value %s=%r; using %.2f", key_path, raw_value, default)
            value = default

        if minimum is not None and value < minimum:
            value = minimum

        if maximum is not None and value > maximum:
            value = maximum

        self._assign(key_path, value)

    def _set_bool(self, key_path: str, default: bool) -> None:
        raw_value = self.get(key_path, default)

        if isinstance(raw_value, bool):
            value = raw_value
        elif isinstance(raw_value, str):
            value = raw_value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        elif isinstance(raw_value, (int, float)):
            value = bool(raw_value)
        else:
            value = default

        self._assign(key_path, value)

    def _set_string(
        self,
        key_path: str,
        default: str,
        allowed: Optional[set[str]] = None,
    ) -> None:
        value = str(self.get(key_path, default)).strip()

        if not value:
            value = default

        if allowed is not None:
            normalized = value.upper() if key_path == "system.log_level" else value.lower()

            if normalized not in allowed:
                logger.warning("Invalid config value %s=%r; using %s", key_path, value, default)
                normalized = default

            value = normalized

        self._assign(key_path, value)

    def _assign(self, key_path: str, value: Any) -> None:
        parts = key_path.split(".")
        target = self._data

        for part in parts[:-1]:
            if not isinstance(target.get(part), dict):
                target[part] = {}
            target = target[part]

        target[parts[-1]] = value
