from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional


class Player:
    def __init__(self, player: str = "mpv", fullscreen: bool = True, volume: int = 90) -> None:
        self.player_name = player or "mpv"
        self.fullscreen = bool(fullscreen)
        self.volume = max(0, min(100, int(volume)))
        self._process: Optional[subprocess.Popen] = None
        self._standby_process: Optional[subprocess.Popen] = None
        self._last_path: Optional[str] = None
        self._ipc_path = "/tmp/modinteractive-mpv.sock"

    @property
    def is_available(self) -> bool:
        return shutil.which(self.player_name) is not None

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume)))
        self._mpv_command(["set_property", "volume", self.volume])

    def _env(self) -> dict:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        return env

    def _is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _wait_for_ipc(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if Path(self._ipc_path).exists():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(0.5)
                        client.connect(self._ipc_path)
                    return True
                except OSError:
                    pass
            time.sleep(0.05)
        return False

    def _mpv_command(self, command: list[Any]) -> Any:
        if not Path(self._ipc_path).exists():
            return None

        payload = json.dumps({"command": command}).encode("utf-8") + b"\n"

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1.0)
                client.connect(self._ipc_path)
                client.sendall(payload)
                data = client.recv(65536)
        except OSError:
            return None

        try:
            response = json.loads(data.decode("utf-8"))
        except Exception:
            return None

        return response.get("data")

    def _get_property(self, name: str) -> Any:
        return self._mpv_command(["get_property", name])

    def _start_persistent_mpv(self, path: str) -> bool:
        if not self.is_available:
            return False

        if not os.path.exists(path):
            return False

        self.stop()

        try:
            Path(self._ipc_path).unlink(missing_ok=True)
        except Exception:
            pass

        cmd = [
            self.player_name,
            "--no-terminal",
            "--force-window=yes",
            "--no-border",
            "--idle=yes",
            "--keep-open=yes",
            "--pause=yes",
            "--start=0",
            "--loop-file=no",
            f"--volume={self.volume}",
            f"--input-ipc-server={self._ipc_path}",
        ]

        if self.fullscreen:
            cmd.append("--fs")

        cmd.append(path)

        self._process = subprocess.Popen(
            cmd,
            env=self._env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        if not self._wait_for_ipc():
            return False

        self._last_path = path
        self._mpv_command(["seek", 0, "absolute"])
        self._mpv_command(["set_property", "pause", True])
        return True

    def show_standby(self, path: str) -> bool:
        if not self._is_running() or self._last_path != path:
            return self._start_persistent_mpv(path)

        self._mpv_command(["set_property", "pause", True])
        self._mpv_command(["seek", 0, "absolute"])
        self._mpv_command(["set_property", "pause", True])
        return True

    def stop_standby(self) -> None:
        # Persistent mpv must stay open, otherwise desktop becomes visible.
        return None

    def play(self, path: str) -> bool:
        if not self._is_running() or self._last_path != path:
            if not self._start_persistent_mpv(path):
                return False

        self._last_path = path

        # Same fullscreen mpv window, no close/reopen.
        self._mpv_command(["set_property", "pause", True])
        self._mpv_command(["seek", 0, "absolute"])
        self._mpv_command(["set_property", "pause", False])
        return True

    def wait_for_completion(self) -> int:
        if not self._is_running():
            return 1

        duration = self._get_property("duration")
        if not isinstance(duration, (int, float)) or duration <= 0:
            duration = None

        started = time.time()

        while self._is_running():
            eof = self._get_property("eof-reached")
            pos = self._get_property("time-pos")

            if eof is True:
                break

            if duration and isinstance(pos, (int, float)) and pos >= max(0.0, duration - 0.20):
                break

            # Safety fallback for broken duration reporting.
            if duration and time.time() - started > duration + 5:
                break

            time.sleep(0.10)

        # Return to first frame without closing mpv window.
        self._mpv_command(["set_property", "pause", True])
        self._mpv_command(["seek", 0, "absolute"])
        self._mpv_command(["set_property", "pause", True])

        return 0

    def stop_playback(self) -> None:
        if self._is_running():
            self._mpv_command(["set_property", "pause", True])
            self._mpv_command(["seek", 0, "absolute"])

    def stop(self) -> None:
        proc = self._process
        self._process = None
        self._standby_process = None

        if proc is None:
            return

        if proc.poll() is not None:
            return

        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

        try:
            Path(self._ipc_path).unlink(missing_ok=True)
        except Exception:
            pass
