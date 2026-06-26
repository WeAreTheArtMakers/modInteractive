"""Application controller for modInteractive kiosk system.

Coordinates config loading, camera access, motion detection,
video playback, and graceful shutdown in a simple async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from typing import Optional

import cv2
import numpy as np

from core.config import Config
from core.detector import Detector
from core.player import Player

logger = logging.getLogger("modInteractive.app")


class Application:
    """Main application for the interactive kiosk system.

    Runs an event loop that captures camera frames, detects motion/persons,
    and triggers video playback.  Manages cooldowns, state, and cleanup.
    """

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
        self._camera: Optional[cv2.VideoCapture] = None

        # Core components
        self._detector = Detector(
            sensitivity=self._config.get("motion_sensitivity", 500),
            confidence=self._config.get("detection_confidence", 0.5),
            mode=self._config.get("detection_mode", "motion"),
        )
        self._player = Player(
            player=self._config.get("player", "mpv"),
            fullscreen=self._config.get("fullscreen", True),
            volume=self._config.get("player_volume", 90),
        )

        self._check_environment()

    def _check_environment(self) -> None:
        """Check system requirements and log status."""
        logger.info("=" * 60)
        logger.info("modInteractive - Interactive Kiosk System")
        logger.info("=" * 60)

        # Config check
        logger.info("[CHECK] Configuration loaded: OK")

        # Video file check
        video = self._config.video_path
        if os.path.exists(video):
            logger.info("[OK] Video file found: %s", video)
        else:
            logger.warning("[WARNING] Video file not found: %s", video)

        # Player check
        if self._player.is_available:
            logger.info("[OK] Player '%s' is available", self._player.player_name)
        else:
            logger.warning(
                "[WARNING] Player '%s' not found. Install: sudo apt install %s",
                self._player.player_name,
                self._player.player_name,
            )

        # Log directory check
        log_dir = "logs"
        if os.access(log_dir, os.W_OK) if os.path.exists(log_dir) else True:
            logger.info("[OK] Log directory accessible")
        else:
            logger.warning("[WARNING] Log directory not writable: %s", log_dir)

        logger.info("-" * 60)

    def _open_camera(self) -> bool:
        """Open the camera device.

        Returns:
            True if camera opened successfully
        """
        camera_index = self._config.camera_index
        try:
            self._camera = cv2.VideoCapture(camera_index)

            if not self._camera.isOpened():
                logger.error("Failed to open camera (index: %d)", camera_index)
                self._camera = None
                return False

            # Set camera properties
            width = self._config.get("camera_width", 640)
            height = self._config.get("camera_height", 480)
            fps = self._config.get("camera_fps", 15)

            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._camera.set(cv2.CAP_PROP_FPS, fps)

            # Set buffer to 1 for low latency
            self._camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            logger.info(
                "Camera opened: index=%d, %dx%d @ %d fps",
                camera_index, width, height, fps,
            )
            logger.info("[OK] Camera is available")
            return True

        except Exception as e:
            logger.error("Camera initialization error: %s", e)
            self._camera = None
            return False

    def _close_camera(self) -> None:
        """Release the camera resource."""
        if self._camera is not None:
            try:
                self._camera.release()
                logger.info("Camera released")
            except Exception as e:
                logger.error("Error releasing camera: %s", e)
            finally:
                self._camera = None

    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from the camera.

        Returns:
            Frame as numpy array, or None on failure
        """
        if self._camera is None:
            return None

        try:
            ret, frame = self._camera.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame from camera")
                return None
            return frame
        except Exception as e:
            logger.error("Error reading frame: %s", e)
            return None

    async def _handle_detection(self, frame: np.ndarray) -> None:
        """Process a frame for detection.

        If detection triggers and no cooldown is active, starts video playback.

        Args:
            frame: OpenCV BGR image frame
        """
        if not self._config.detection_enabled:
            return

        # Check cooldown
        now = time.time()
        if now < self._cooldown_until:
            return

        # Run detection
        detected, confidence, metadata = self._detector.detect(frame)

        if detected and not self._playing_video:
            logger.info(
                "🎯 Detection: method=%s, confidence=%.2f, pixels=%d",
                metadata.get("method", "?"),
                confidence,
                metadata.get("motion_pixels", 0),
            )
            await self._play_video()

    async def _play_video(self) -> None:
        """Play the configured video and wait for completion."""
        video_path = self._config.video_path

        if not os.path.exists(video_path):
            logger.error("Cannot play: video file not found: %s", video_path)
            return

        if not self._player.is_available:
            logger.error("Cannot play: player '%s' not available", self._player.player_name)
            return

        self._playing_video = True
        logger.info("▶️ Starting video playback: %s", video_path)

        # Start playback in subprocess
        if not self._player.play(video_path):
            self._playing_video = False
            return

        # Wait for completion in a non-blocking way
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._player.wait_for_completion)

        logger.info("⏹️ Video playback finished")
        self._playing_video = False

        # Set cooldown
        cooldown = self._config.cooldown_seconds
        self._cooldown_until = time.time() + cooldown
        logger.info("⏳ Cooldown: %d seconds", cooldown)

    async def run(self) -> None:
        """Main application loop.

        Captures camera frames, detects motion, and manages playback.
        Runs until stop() is called or an unrecoverable error occurs.
        """
        self._running = True

        # Open camera
        camera_ok = self._open_camera()
        if not camera_ok:
            logger.error(
                "Cannot start: camera not available. "
                "Check camera connection and permissions."
            )
            self._running = False
            return

        logger.info("Application is running. Press Ctrl+C to stop.")
        logger.info("Waiting for detection...")

        frame_count = 0

        try:
            while self._running:
                # Read frame
                frame = self._read_frame()
                if frame is None:
                    # Try to reconnect camera
                    logger.warning("Camera frame lost, attempting reconnect...")
                    self._close_camera()
                    await asyncio.sleep(2)
                    if not self._open_camera():
                        logger.error("Camera reconnect failed")
                        await asyncio.sleep(5)
                    continue

                frame_count += 1

                # Process detection (skip frames for performance)
                if frame_count % 3 == 0:
                    await self._handle_detection(frame)

                # Small sleep to control loop speed
                await asyncio.sleep(0.03)  # ~30 FPS loop

        except asyncio.CancelledError:
            logger.info("Application task cancelled")
        except Exception as e:
            logger.error("Unexpected error in main loop: %s", e, exc_info=True)
        finally:
            await self.shutdown()

    def stop(self) -> None:
        """Signal the application to stop."""
        self._running = False
        logger.info("Stop signal received")

    async def shutdown(self) -> None:
        """Clean shutdown of all components."""
        logger.info("Shutting down...")

        # Stop video playback
        if self._playing_video:
            self._player.stop()
            self._playing_video = False

        # Release camera
        self._close_camera()

        logger.info("Shutdown complete")

    @property
    def is_running(self) -> bool:
        """Check if application is running."""
        return self._running

    @property
    def is_playing(self) -> bool:
        """Check if video is currently playing."""
        return self._playing_video