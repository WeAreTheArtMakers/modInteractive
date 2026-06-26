"""System health check module for modInteractive.

Runs diagnostics on all system components and reports status.
"""

from __future__ import annotations

import logging
import os
import socket
import shutil
from pathlib import Path

import cv2

from core.config import Config

logger = logging.getLogger("modInteractive.healthcheck")


class HealthCheck:
    """System health diagnostics."""

    def __init__(self, config: Config) -> None:
        """Initialize health check.

        Args:
            config: Application configuration
        """
        self._config = config
        self._results: list[tuple[str, str, str]] = []

    def _ok(self, check: str, detail: str = "") -> None:
        """Record a passed check.

        Args:
            check: Check name
            detail: Optional detail message
        """
        self._results.append(("OK", check, detail))

    def _warn(self, check: str, detail: str = "") -> None:
        """Record a warning.

        Args:
            check: Check name
            detail: Optional detail message
        """
        self._results.append(("WARNING", check, detail))

    def _fail(self, check: str, detail: str = "") -> None:
        """Record a failed check.

        Args:
            check: Check name
            detail: Optional detail message
        """
        self._results.append(("FAIL", check, detail))

    def run_all(self) -> list[tuple[str, str, str]]:
        """Run all health checks.

        Returns:
            List of (status, check_name, detail) tuples
        """
        self._results = []
        self._check_config()
        self._check_log_directory()
        self._check_mpv()
        self._check_camera()
        self._check_video_file()
        self._check_opencv()
        self._check_admin_port()
        self._check_venv()
        return self._results

    def _check_config(self) -> None:
        """Check configuration loads correctly."""
        try:
            cfg = self._config.data
            if cfg:
                self._ok("Config loaded",
                         f"camera.index={self._config.get('camera.index', '?')}")
            else:
                self._fail("Config loaded", "Configuration is empty")
        except Exception as e:
            self._fail("Config loaded", str(e))

    def _check_log_directory(self) -> None:
        """Check log directory is writable."""
        log_dir = Path("logs")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            test_file = log_dir / ".healthcheck_test"
            test_file.write_text("ok")
            test_file.unlink()
            self._ok("Log directory writable", str(log_dir.resolve()))
        except OSError as e:
            self._fail("Log directory writable", str(e))

    def _check_mpv(self) -> None:
        """Check if mpv player is available."""
        mpv_path = shutil.which("mpv")
        if mpv_path:
            self._ok("mpv found", mpv_path)
        else:
            self._fail("mpv found",
                       "Install: sudo apt install mpv")

    def _check_camera(self) -> None:
        """Check if camera can be opened."""
        index = self._config.get("camera.index", 0)
        try:
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    device_path = f"/dev/video{index}"
                    if os.path.exists(device_path):
                        self._ok("Camera opened",
                                 f"{device_path} ({w}x{h})")
                    else:
                        self._ok("Camera opened",
                                 f"index={index} ({w}x{h})")
                else:
                    self._warn("Camera opened",
                               "Device opened but frame read failed")
                cap.release()
            else:
                self._fail("Camera opened",
                           f"Cannot open camera at index {index}")
        except Exception as e:
            self._fail("Camera opened", str(e))

    def _check_video_file(self) -> None:
        """Check if configured video file exists."""
        video_path = self._config.get("video.path", "videos/selamlama.mp4")
        abs_path = os.path.abspath(video_path)
        if os.path.exists(abs_path):
            size_mb = os.path.getsize(abs_path) / (1024 * 1024)
            self._ok("Video found",
                     f"{abs_path} ({size_mb:.1f} MB)")
        else:
            self._warn("Video found",
                       f"Not found: {abs_path}")

    def _check_opencv(self) -> None:
        """Check OpenCV import and version."""
        try:
            version = cv2.__version__
            import numpy as np
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            success = test_img.shape == (100, 100, 3)
            if success:
                self._ok("OpenCV", f"version {version}")
            else:
                self._fail("OpenCV", "Basic functionality failed")
        except Exception as e:
            self._fail("OpenCV", str(e))

    def _check_admin_port(self) -> None:
        """Check if admin panel port is available."""
        if not self._config.get("admin.enabled", True):
            self._ok("Admin panel", "Disabled in config")
            return

        port = self._config.get("admin.port", 8080)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result != 0:
                self._ok("Admin panel",
                         f"Port {port} is available")
            else:
                self._ok("Admin panel",
                         f"Port {port} (already in use)")
        except Exception as e:
            self._warn("Admin panel",
                       f"Port check failed: {e}")

    def _check_venv(self) -> None:
        """Check virtual environment path for systemd service."""
        venv_python = "/opt/modInteractive/venv/bin/python"
        alt_venv = "/opt/modInteractive/.venv/bin/python"
        if os.path.isfile(venv_python):
            self._ok("Virtualenv path",
                     f"{venv_python} exists")
        elif os.path.isfile(alt_venv):
            self._warn("Virtualenv path",
                       f"{alt_venv} exists (expected {venv_python})")
        else:
            self._warn("Virtualenv path",
                       "Not installed yet (only matters after install)")

    def print_report(self) -> None:
        """Print formatted health check report to stdout."""
        max_len = max(len(c) for _, c, _ in self._results) if self._results else 20

        print("=" * 60)
        print(" modInteractive - System Health Check")
        print("=" * 60)

        has_fail = False
        for status, check, detail in self._results:
            label = f"[{status}]".ljust(8)
            padding = " " * (max_len - len(check) + 1)
            print(f" {label} {check}{padding}{detail}")
            if status == "FAIL":
                has_fail = True

        print("-" * 60)

        if has_fail:
            print(" Some checks FAILED. See messages above.")
        else:
            print(" All checks passed.")

        print("=" * 60)