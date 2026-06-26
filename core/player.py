
from **future** import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("modInteractive.player")

class Player:


def __init__(
    self,
    player: str = "mpv",
    fullscreen: bool = True,
    volume: int = 90,
) -> None:
    """Initialize player.

    Args:
        player: Player executable name, usually mpv.
        fullscreen: Whether to play in fullscreen mode.
        volume: Initial volume between 0 and 100.
    """
    self._player = str(player or "mpv").strip()
    self._fullscreen = bool(fullscreen)
    self._volume = self._clamp_volume(volume)
    self._process: Optional[subprocess.Popen[bytes]] = None
    self._last_started_at: Optional[float] = None

    self._player_path = shutil.which(self._player)
    self._available = self._player_path is not None

    if self._available:
        logger.info("Video player found: %s", self._player_path)
    else:
        logger.error(
            "Player '%s' not found. Install it with: sudo apt install %s",
            self._player,
            self._player,
        )

def play(self, video_path: str) -> bool:
    """Play a video file.

    Args:
        video_path: Path to the video file.

    Returns:
        True if playback started successfully, False otherwise.
    """
    if not self._available or self._player_path is None:
        logger.error("Player '%s' is not available", self._player)
        return False

    resolved_video = Path(video_path).expanduser().resolve()

    if not resolved_video.exists():
        logger.error("Video file not found: %s", resolved_video)
        return False

    if not resolved_video.is_file():
        logger.error("Video path is not a file: %s", resolved_video)
        return False

    if self.is_playing:
        logger.warning("A video is already playing; stopping previous playback")
        self.stop()

    cmd = self._build_command(str(resolved_video))

    logger.info(
        "Starting video playback: %s fullscreen=%s volume=%d",
        resolved_video,
        self._fullscreen,
        self._volume,
    )

    try:
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
        )
        self._last_started_at = time.time()
        logger.info("Playback started with PID %d", self._process.pid)
        return True

    except FileNotFoundError:
        logger.error("Player executable not found: %s", self._player_path)
    except PermissionError:
        logger.error("Permission denied while starting player: %s", self._player_path)
    except OSError as exc:
        logger.error("Failed to start player: %s", exc)

    self._process = None
    self._last_started_at = None
    return False

def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
    """Wait for current playback to finish.

    Args:
        timeout: Maximum wait time in seconds. None means wait forever.

    Returns:
        True if playback finished normally, False on timeout/error.
    """
    if self._process is None:
        return True

    try:
        return_code = self._process.wait(timeout=timeout)
        duration = self.playback_duration

        if return_code == 0:
            logger.info("Playback completed successfully in %.1f seconds", duration)
        else:
            logger.warning(
                "Playback ended with non-zero exit code %d after %.1f seconds",
                return_code,
                duration,
            )

        self._process = None
        self._last_started_at = None
        return True

    except subprocess.TimeoutExpired:
        logger.warning("Playback timed out after %s seconds", timeout)
        return False
    except Exception:
        logger.exception("Playback wait failed")
        self._process = None
        self._last_started_at = None
        return False

def stop(self) -> None:
    """Stop current playback immediately."""
    process = self._process

    if process is None:
        return

    if process.poll() is not None:
        self._process = None
        self._last_started_at = None
        return

    logger.info("Stopping playback PID %d", process.pid)

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            logger.warning("Player did not terminate; killing process")

            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()

            process.wait(timeout=3)

        logger.info("Playback stopped")

    except ProcessLookupError:
        logger.info("Player process already exited")
    except Exception:
        logger.exception("Error stopping playback")
    finally:
        self._process = None
        self._last_started_at = None

def set_volume(self, volume: int) -> None:
    """Set playback volume for future playback.

    Args:
        volume: Volume level between 0 and 100.
    """
    self._volume = self._clamp_volume(volume)
    logger.info("Player volume set to %d", self._volume)

def _build_command(self, video_path: str) -> List[str]:
    """Build mpv command.

    Args:
        video_path: Absolute video file path.

    Returns:
        Command list suitable for subprocess.Popen.
    """
    command: List[str] = [self._player_path or self._player]

    command.extend(
        [
            "--no-terminal",
            "--really-quiet",
            "--keep-open=no",
            "--osd-level=0",
            "--no-input-default-bindings",
            f"--volume={self._volume}",
        ]
    )

    if self._fullscreen:
        command.extend(
            [
                "--fs",
                "--no-border",
                "--ontop",
                "--cursor-autohide=always",
            ]
        )

    command.append(video_path)
    return command

def _clamp_volume(self, volume: int) -> int:
    """Clamp volume to 0-100.

    Args:
        volume: Raw volume value.

    Returns:
        Safe volume value.
    """
    try:
        numeric_volume = int(volume)
    except (TypeError, ValueError):
        numeric_volume = 90

    return max(0, min(100, numeric_volume))

@property
def is_playing(self) -> bool:
    """Return True if video is currently playing."""
    return self._process is not None and self._process.poll() is None

@property
def is_available(self) -> bool:
    """Return True if player executable is installed."""
    return self._available

@property
def player_name(self) -> str:
    """Return player executable name."""
    return self._player

@property
def player_path(self) -> Optional[str]:
    """Return resolved player executable path."""
    return self._player_path

@property
def volume(self) -> int:
    """Return configured volume."""
    return self._volume

@property
def fullscreen(self) -> bool:
    """Return fullscreen setting."""
    return self._fullscreen

@property
def playback_duration(self) -> float:
    """Return current or last playback duration in seconds."""
    if self._last_started_at is None:
        return 0.0

    return max(0.0, time.time() - self._last_started_at)
