from __future__ import annotations

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
        self._player = str(player or "mpv").strip()
        self._fullscreen = bool(fullscreen)
        self._volume = self._clamp_volume(volume)
        self._player_path = shutil.which(self._player)
        self._available = self._player_path is not None
        self._process: Optional[subprocess.Popen] = None
        self._started_at = 0.0

        if self._available:
            logger.info("Video player found: %s", self._player_path)
        else:
            logger.warning("Video player not found: %s", self._player)

    def play(self, video_path: str) -> bool:
        path = Path(video_path).expanduser().resolve()

        if not self._available:
            logger.error("Player is not available: %s", self._player)
            return False

        if not path.is_file():
            logger.error("Video file not found: %s", path)
            return False

        if self.is_playing:
            self.stop()

        command = self._build_command(str(path))

        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
            self._started_at = time.time()
            logger.info("Video player started: %s", path)
            return True

        except Exception:
            logger.exception("Could not start video player")
            self._process = None
            self._started_at = 0.0
            return False

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        if self._process is None:
            return True

        try:
            return_code = self._process.wait(timeout=timeout)
            logger.info("Video player exited with code %s", return_code)
            return return_code == 0
        except subprocess.TimeoutExpired:
            logger.warning("Video player timeout expired")
            return False
        finally:
            if self._process is not None and self._process.poll() is not None:
                self._process = None
                self._started_at = 0.0

    def stop(self) -> None:
        process = self._process

        if process is None:
            return

        if process.poll() is not None:
            self._process = None
            self._started_at = 0.0
            return

        logger.info("Stopping video player")

        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()

            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            logger.warning("Video player did not stop; killing")

            try:
                if os.name == "posix":
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()

                process.wait(timeout=2)
            except Exception:
                logger.debug("Killing video player failed", exc_info=True)
        except ProcessLookupError:
            pass
        except Exception:
            logger.exception("Failed to stop video player")
        finally:
            self._process = None
            self._started_at = 0.0

    def set_volume(self, value: int) -> None:
        self._volume = self._clamp_volume(value)

    def _build_command(self, video_path: str) -> List[str]:
        command = [
            self._player_path or self._player,
            "--no-terminal",
            "--really-quiet",
            "--keep-open=no",
            "--osd-level=0",
            "--no-input-default-bindings",
            f"--volume={self._volume}",
        ]

        if self._fullscreen:
            command.extend(["--fs", "--no-border", "--ontop", "--cursor-autohide=always"])

        command.append(video_path)
        return command

    def _clamp_volume(self, value: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = 90

        return max(0, min(100, number))

    @property
    def is_playing(self) -> bool:
        if self._process is None:
            return False

        if self._process.poll() is not None:
            self._process = None
            self._started_at = 0.0
            return False

        return True

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def player_name(self) -> str:
        return self._player

    @property
    def player_path(self) -> Optional[str]:
        return self._player_path

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen

    @property
    def playback_duration(self) -> float:
        if not self._started_at:
            return 0.0

        return max(0.0, time.time() - self._started_at)
