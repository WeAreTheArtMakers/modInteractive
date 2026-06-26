from **future** import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from core.camera import Camera
from core.config import Config
from core.detector import Detector
from core.player import Player

logger = logging.getLogger("modInteractive.app")

def _start_admin_thread(config: Config, config_path: str) -> Optional[object]:
if not config.get("admin.enabled", True):
logger.info("Admin panel disabled")
return None

```
try:
    from admin.server import start_admin_thread

    thread = start_admin_thread(config, config_path)
    logger.info(
        "Admin panel started at http://%s:%s",
        config.get("admin.host", "0.0.0.0"),
        config.get("admin.port", 8080),
    )
    return thread
except ImportError:
    logger.warning("Admin panel skipped because dependencies are missing")
except Exception:
    logger.exception("Admin panel failed to start")

return None
```

class Application:
def **init**(self, config_path: str = "config.json") -> None:
self._config_path = str(Path(config_path).expanduser().resolve())
self._base_dir = Path(self._config_path).parent

```
    self._config = Config(self._config_path)
    self._config.load()

    self._running = False
    self._shutting_down = False
    self._playing_video = False
    self._cooldown_until = 0.0
    self._camera_error_count = 0
    self._admin_thread: Optional[object] = None

    self._camera_fps = self._get_int("camera.fps", 15, minimum=1)
    self._warmup_seconds = self._get_int("detection.warmup_seconds", 2, minimum=0)
    self._warmup_frames = max(1, self._warmup_seconds * self._camera_fps)

    self._camera = Camera(
        index=self._camera_index(),
        width=self._get_int("camera.width", 640, minimum=1),
        height=self._get_int("camera.height", 480, minimum=1),
        fps=self._camera_fps,
        warmup_frames=self._warmup_frames,
        backend=str(self._config.get("camera.backend", "v4l2")),
    )

    self._detector = Detector(
        sensitivity=self._get_int("detection.motion_sensitivity", 500, minimum=1),
        min_area=self._get_int("detection.min_motion_area", 1500, minimum=1),
        warmup_frames=self._warmup_frames,
    )

    self._player = Player(
        player=str(self._config.get("video.player", "mpv")),
        fullscreen=bool(self._config.get("video.fullscreen", True)),
        volume=self._get_int("video.volume", 90, minimum=0, maximum=100),
    )

    self._playback_lock = asyncio.Lock()
    self._log_startup_status()

def _get_int(
    self,
    key: str,
    default: int,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    raw_value: Any = self._config.get(key, default)

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        logger.warning("Invalid integer config value for %s=%r; using %d", key, raw_value, default)
        value = default

    if minimum is not None and value < minimum:
        logger.warning("Config value %s=%d is below minimum %d; using %d", key, value, minimum, minimum)
        value = minimum

    if maximum is not None and value > maximum:
        logger.warning("Config value %s=%d is above maximum %d; using %d", key, value, maximum, maximum)
        value = maximum

    return value

def _camera_index(self) -> Any:
    raw_value = self._config.get("camera.index", 0)

    if isinstance(raw_value, int):
        return raw_value

    if isinstance(raw_value, str):
        value = raw_value.strip()

        if value.isdigit():
            return int(value)

        return value

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0

def _resolve_project_path(self, value: str) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = self._base_dir / path

    return path.resolve()

def _video_path(self) -> Path:
    return self._resolve_project_path(
        str(self._config.get("video.path", "videos/selamlama.mp4"))
    )

def _cooldown_seconds(self) -> int:
    return self._get_int("detection.cooldown_seconds", 10, minimum=0)

def _frame_skip(self) -> int:
    return self._get_int("detection.frame_skip", 3, minimum=1)

def _refresh_runtime_settings(self) -> None:
    try:
        self._detector.set_sensitivity(
            self._get_int("detection.motion_sensitivity", 500, minimum=1)
        )
        self._detector.set_min_area(
            self._get_int("detection.min_motion_area", 1500, minimum=1)
        )
        self._player.set_volume(
            self._get_int("video.volume", 90, minimum=0, maximum=100)
        )
    except Exception:
        logger.debug("Runtime settings refresh failed", exc_info=True)

def _log_startup_status(self) -> None:
    logger.info("=" * 60)
    logger.info("modInteractive - Motion Triggered HDMI Video Display")
    logger.info("=" * 60)

    video_path = self._video_path()

    if video_path.exists():
        logger.info("[OK] Video file: %s", video_path)
    else:
        logger.warning("[WARN] Video file not found: %s", video_path)

    if self._player.is_available:
        logger.info("[OK] Player: %s", self._player.player_name)
    else:
        logger.warning("[WARN] Player not found: %s", self._player.player_name)

    if self._config.get("admin.enabled", True):
        logger.info("[OK] Admin panel port: %s", self._config.get("admin.port", 8080))
    else:
        logger.info("Admin panel disabled")

    logger.info("Camera index: %s", self._camera_index())
    logger.info("Camera backend: %s", self._config.get("camera.backend", "v4l2"))
    logger.info(
        "Camera resolution: %dx%d",
        self._get_int("camera.width", 640),
        self._get_int("camera.height", 480),
    )
    logger.info("Camera FPS: %d", self._camera_fps)
    logger.info("Frame skip: %d", self._frame_skip())
    logger.info("Cooldown: %d seconds", self._cooldown_seconds())
    logger.info("-" * 60)

async def run(self) -> None:
    self._running = True
    self._admin_thread = _start_admin_thread(self._config, self._config_path)

    logger.info("Application running")

    if not await self._ensure_camera_open():
        logger.error("Application stopped before camera could be opened")
        return

    logger.info("Waiting for motion")

    frame_count = 0

    try:
        while self._running:
            frame = self._read_camera_frame()

            if frame is None:
                await self._handle_camera_read_failure()
                continue

            self._camera_error_count = 0
            frame_count += 1

            if frame_count % self._frame_skip() == 0:
                self._refresh_runtime_settings()

                if self._config.get("detection.enabled", True):
                    await self._handle_detection(frame)

            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        logger.info("Application task cancelled")
        raise
    except Exception:
        logger.exception("Unexpected application error")
    finally:
        await self.shutdown()

async def _ensure_camera_open(self) -> bool:
    retry_seconds = 5

    while self._running:
        try:
            if self._camera.open():
                logger.info("Camera opened successfully")
                return True

            logger.error("Camera not available. Retrying in %d seconds", retry_seconds)

        except Exception:
            logger.exception("Camera open failed. Retrying in %d seconds", retry_seconds)

        await asyncio.sleep(retry_seconds)

    return False

def _read_camera_frame(self) -> Optional[np.ndarray]:
    try:
        return self._camera.read()
    except Exception:
        logger.exception("Camera read raised an exception")
        return None

async def _handle_camera_read_failure(self) -> None:
    self._camera_error_count += 1

    if self._camera_error_count <= 30:
        await asyncio.sleep(0.1)
        return

    logger.error("Too many camera read errors; reconnecting camera")

    try:
        self._camera.close()
    except Exception:
        logger.exception("Camera close failed during reconnect")

    await asyncio.sleep(3)

    try:
        if self._camera.open():
            logger.info("Camera reconnected successfully")
            self._camera_error_count = 0
            return

        logger.error("Camera reconnect failed")

    except Exception:
        logger.exception("Camera reconnect raised an exception")

    await asyncio.sleep(10)

async def _handle_detection(self, frame: np.ndarray) -> None:
    now = time.time()

    if self._playing_video:
        return

    if now < self._cooldown_until:
        return

    try:
        detected, confidence, pixels, metadata = self._detector.detect(frame)
    except Exception:
        logger.exception("Motion detector failed")
        return

    if not detected:
        return

    max_area = 0.0

    if isinstance(metadata, dict):
        max_area = float(metadata.get("max_contour_area", 0.0))

    logger.info(
        "MOTION detected: confidence=%.2f, pixels=%d, max_area=%.0f",
        float(confidence),
        int(pixels),
        max_area,
    )

    await self._play_video()

async def _play_video(self) -> None:
    async with self._playback_lock:
        if self._playing_video:
            return

        video_path = self._video_path()

        if not video_path.exists():
            logger.error("Video file not found: %s", video_path)
            self._set_short_error_cooldown()
            return

        if not self._player.is_available:
            logger.error("Player not available: %s", self._player.player_name)
            self._set_short_error_cooldown()
            return

        self._playing_video = True
        logger.info("PLAYING: %s", video_path)

        try:
            if not self._player.play(str(video_path)):
                logger.error("Player failed to start video: %s", video_path)
                self._set_short_error_cooldown()
                return

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._player.wait_for_completion)

            logger.info("Playback finished")

        except Exception:
            logger.exception("Video playback failed")
            self._set_short_error_cooldown()

        finally:
            self._playing_video = False

            if self._running:
                cooldown = self._cooldown_seconds()
                self._cooldown_until = time.time() + cooldown
                logger.info("Cooldown started: %d seconds", cooldown)

def _set_short_error_cooldown(self) -> None:
    self._cooldown_until = time.time() + 5

def stop(self) -> None:
    if not self._running:
        return

    logger.info("Stop signal received")
    self._running = False

    try:
        self._player.stop()
    except Exception:
        logger.exception("Failed to stop player")

async def shutdown(self) -> None:
    if self._shutting_down:
        return

    self._shutting_down = True
    self._running = False

    logger.info("Shutting down")

    try:
        self._player.stop()
    except Exception:
        logger.exception("Failed to stop video player during shutdown")

    try:
        self._camera.close()
    except Exception:
        logger.exception("Failed to close camera during shutdown")

    logger.info("Shutdown complete")
```
