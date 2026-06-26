"""Video playback module for modInteractive kiosk system.

Plays video files using mpv player via subprocess.
Supports fullscreen mode and configurable volume.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from typing import List, Optional

logger = logging.getLogger("modInteractive.player")


class Player:
    """Video player wrapper using mpv.

    Plays video files with subprocess to avoid blocking the asyncio event loop.
    All commands use list format to prevent shell injection.
    """

    def __init__(
        self,
        player: str = "mpv",
        fullscreen: bool = True,
        volume: int = 90,
    ) -> None:
        """Initialize player.

        Args:
            player: Player executable name
            fullscreen: Whether to play in fullscreen mode
            volume: Initial volume (0-100)
        """
        self._player: str = player
        self._fullscreen: bool = fullscreen
        self._volume: int = max(0, min(100, volume))
        self._process: Optional[subprocess.Popen] = None
        self._available: bool = self._check_player()

        if not self._available:
            logger.error(
                "Player '%s' not found. Please install it: sudo apt install %s",
                self._player,
                self._player,
            )

    def _check_player(self) -> bool:
        """Check if the video player is installed.

        Returns:
            True if player executable is found
        """
        return shutil.which(self._player) is not None

    def play(self, video_path: str) -> bool:
        """Play a video file.

        Args:
            video_path: Path to the video file

        Returns:
            True if playback started successfully
        """
        if not self._available:
            logger.error("Player '%s' is not available", self._player)
            return False

        if not os.path.exists(video_path):
            logger.error("Video file not found: %s", video_path)
            return False

        # Build command with list to prevent shell injection
        cmd: List[str] = [self._player]

        if self._fullscreen:
            cmd.append("--fs")

        # Volume (mpv uses 0-100 range)
        cmd.extend(["--volume", str(self._volume)])

        # Ensure mpv exits when done (no looping)
        cmd.append("--keep-open=no")

        # No OSD for kiosk mode
        cmd.append("--osd-level=0")

        # Suppress terminal output
        cmd.append("--really-quiet")

        # No cursor in fullscreen
        if self._fullscreen:
            cmd.append("--cursor-autohide=no")

        cmd.append(video_path)

        logger.info("Playing video: %s (fullscreen=%s)", video_path, self._fullscreen)

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Playback started (PID: %d)", self._process.pid)
            return True
        except OSError as e:
            logger.error("Failed to start player: %s", e)
            self._process = None
            return False

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for video playback to finish.

        Args:
            timeout: Maximum time to wait in seconds (None = no limit)

        Returns:
            True if playback completed, False if timed out or not playing
        """
        if self._process is None:
            return True

        try:
            self._process.wait(timeout=timeout)
            logger.info("Playback completed (exit code: %d)", self._process.returncode)
            self._process = None
            return True
        except subprocess.TimeoutExpired:
            logger.warning("Playback timed out after %s seconds", timeout)
            return False
        except Exception as e:
            logger.error("Playback error: %s", e)
            self._process = None
            return False

    def stop(self) -> None:
        """Stop current playback immediately."""
        if self._process is not None and self._process.poll() is None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
                logger.info("Playback stopped")
            except Exception as e:
                logger.error("Error stopping playback: %s", e)
            finally:
                self._process = None

    def set_volume(self, volume: int) -> None:
        """Set playback volume.

        Args:
            volume: Volume level (0-100)
        """
        self._volume = max(0, min(100, volume))
        logger.debug("Volume set to: %d", self._volume)

    @property
    def is_playing(self) -> bool:
        """Check if video is currently playing.

        Returns:
            True if a playback process is running
        """
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def is_available(self) -> bool:
        """Check if the player executable is installed.

        Returns:
            True if player is available
        """
        return self._available

    @property
    def player_name(self) -> str:
        """Get the player executable name."""
        return self._player