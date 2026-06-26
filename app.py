"""Application controller for modInteractive.

Coordinates config loading, camera access, motion detection,
video playback, and graceful shutdown in a simple async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import numpy as np

from core.config import Config
from core.camera import Camera
from core.detector import Detector
from core.player import Player

logger = logging.getLogger("modInteractive.app")


def _start_admin_thread(config: Config, config_path: str) -> Optional[object]:
    """Start admin panel in background thread if enabled.

    Operates independently: if the panel fails, the main motion detection
    and video playback system continues unaffected.

    Args:
        config: Application config
        config_path: Path to config file

    Returns:
        Admin thread object or None
    """
    if not config.get("admin.enabled", True):
        logger.info("Admin panel disabled in config")
        return None

    try:
        from admin.server import start_admin_thread as _start
        thread = _start(config, config_path)
        logger.info("Admin panel started on port %d",
                     config.get("admin.port", 8080))
        return thread
    except ImportError:
        logger.info("Admin panel skipped (flask not installed)")
    except Exception:
        logger.exception("Admin panel failed to start, continuing without admin")

    return None


class Application:
    """Main application for the interactive kiosk system."""

    def __init__(self, config_path: str = "config.json") -> None:
        """Initialize application.

        Args:
            config_path: Path to configuration file
        """
        self._config = Config(config_path)
        self._config.load()

        self._running: bool = False
        self._playing_video: bool = False
        self._cooldown_until: float = 0.0
        self._error_count: int = 0

        # Camera
        self._camera = Camera(
            index=self._config.get("camera.index", 0),
            width=self._config.get("camera.width", 640),
            height=self._config.get("camera.height", 480),
            fps=self._config.get("camera.fps", 15),
            warmup_frames=self._config.get("detection.warmup_seconds", 2) * 15,
        )

        # Detector
        self._detector = Detector(
            sensitivity=self._config.get("detection.motion_sensitivity", 500),
            min_area=self._config.get("detection.min_motion_area", 1500),
            warmup_frames=self._config.get("detection.warmup_seconds", 2) * 15,
        )

        # Player
        self._player = Player(
            player=self._config.get("video.player", "mpv"),
            fullscreen=self._config.get("video.fullscreen", True),
            volume=self._config.get("video.volume", 90),
        )

        self._status_checks()

    def _status_checks(self) -> None:
        """Log system status at startup."""
        logger.info("=" * 60)
        logger.info("modInteractive - Motion Triggered Video Display")
        logger.info("=" * 60)

        video = os.path.abspath(self._config.get("video.path", "videos/selamlama.mp4"))
        if os.path.exists(video):
            logger.info("[OK] Video file: %s", video)
        else:
            logger.warning("[WARN] Video file not found: %s", video)

        if self._player.is_available:
            logger.info("[OK] Player: %s", self._player.player_name)
        else:
            logger.warning("[WARN] Player '%s' not found (install: sudo apt install mpv)",
                           self._player.player_name)

        admin_port = self._config.get("admin.port", 8080)
        if self._config.get("admin.enabled", True):
            logger.info("[OK] Admin panel: port %d", admin_port)

        logger.info("Detection mode: %s", self._config.get("detection.mode", "motion"))
        logger.info("Cooldown: %d seconds", self._config.get("detection.cooldown_seconds", 10))
        logger.info("-" * 60)

    async def run(self) -> None:
        """Main application loop."""
        self._running = True

        # Open camera
        if not self._camera.open():
            logger.error("Cannot start: camera not available")
            self._running = False
            return

        logger.info("Application running. Press Ctrl+C to stop.")
        logger.info("Waiting for motion...")

        frame_count = 0
        frame_skip = self._config.get("detection.frame_skip", 3)

        try:
            while self._running:
                frame = self._camera.read()
                if frame is None:
                    self._error_count += 1
                    if self._error_count > 30:
                        logger.error("Too many camera errors, attempting reconnect...")
                        self._camera.close()
                        await asyncio.sleep(3)
                        if not self._camera.open():
                            logger.error("Camera reconnect failed")
                            await asyncio.sleep(10)
                            continue
                        self._error_count = 0
                    else:
                        await asyncio.sleep(0.1)
                    continue

                self._error_count = 0
                frame_count += 1

                # Process detection with frame skipping
                if (frame_count % frame_skip == 0
                        and self._config.get("detection.enabled", True)):
                    await self._handle_detection(frame)

                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("Application task cancelled")
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
        finally:
            await self.shutdown()

    async def _handle_detection(self, frame: np.ndarray) -> None:
        """Process a frame for motion detection.

        Args:
            frame: OpenCV BGR image frame
        """
        now = time.time()

        # Skip if playing or in cooldown
        if self._playing_video:
            return

        if now < self._cooldown_until:
            return

        detected, confidence, pixels, metadata = self._detector.detect(frame)

        if detected:
            logger.info("MOTION: confidence=%.2f, pixels=%d, area=%.0f",
                        confidence, pixels, metadata.get("max_contour_area", 0))
            await self._play_video()

    async def _play_video(self) -> None:
        """Play the configured video and wait for completion."""
        video_path = os.path.abspath(
            self._config.get("video.path", "videos/selamlama.mp4")
        )

        if not os.path.exists(video_path):
            logger.error("Video file not found: %s", video_path)
            return

        if not self._player.is_available:
            logger.error("Player not available")
            return

        self._playing_video = True
        logger.info("PLAYING: %s", video_path)

        if not self._player.play(video_path):
            self._playing_video = False
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._player.wait_for_completion)

        logger.info("Playback finished")
        self._playing_video = False

        cooldown = self._config.get("detection.cooldown_seconds", 10)
        self._cooldown_until = time.time() + cooldown
        logger.info("Cooldown: %d seconds", cooldown)

    def stop(self) -> None:
        """Signal the application to stop."""
        self._running = False
        logger.info("Stop signal received")

    async def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("Shutting down...")
        if self._playing_video:
            self._player.stop()
        self._camera.close()
        logger.info("Shutdown complete")