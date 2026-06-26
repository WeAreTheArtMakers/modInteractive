"""System health check module for modInteractive.

Runs diagnostics for configuration, log directory, video player,
camera, video file, OpenCV, admin port, and virtualenv setup.
"""

from **future** import annotations

import importlib
import logging
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

from core.config import Config

logger = logging.getLogger("modInteractive.healthcheck")

HealthResult = Tuple[str, str, str]

class HealthCheck: 
def __init__(self, config: Config) -> None:
    """Initialize health check.

    Args:
        config: Application configuration.
    """
    self._config = config
    self._results: List[HealthResult] = []

def run_all(self) -> List[HealthResult]:
    """Run all health checks.

    Returns:
        List of status, check name, and detail tuples.
    """
    self._results = []

    self._check_config()
    self._check_log_directory()
    self._check_player()
    self._check_opencv()
    self._check_camera()
    self._check_video_file()
    self._check_admin_port()
    self._check_venv()

    return list(self._results)

def print_report(self) -> None:
    """Print formatted health check report to stdout."""
    if not self._results:
        self.run_all()

    max_len = max((len(check) for _status, check, _detail in self._results), default=20)

    print("=" * 70)
    print(" modInteractive - System Health Check")
    print("=" * 70)

    has_fail = False
    has_warning = False

    for status, check, detail in self._results:
        label = f"[{status}]".ljust(10)
        padding = " " * (max_len - len(check) + 2)
        print(f" {label} {check}{padding}{detail}")

        if status == "FAIL":
            has_fail = True
        elif status == "WARNING":
            has_warning = True

    print("-" * 70)

    if has_fail:
        print(" Some checks FAILED. Fix the failed items before production use.")
    elif has_warning:
        print(" Checks completed with warnings. Review warnings before deployment.")
    else:
        print(" All checks passed.")

    print("=" * 70)

@property
def results(self) -> List[HealthResult]:
    """Return health check results."""
    return list(self._results)

@property
def has_failures(self) -> bool:
    """Return True if any health check failed."""
    return any(status == "FAIL" for status, _check, _detail in self._results)

@property
def has_warnings(self) -> bool:
    """Return True if any health check produced a warning."""
    return any(status == "WARNING" for status, _check, _detail in self._results)

def exit_code(self) -> int:
    """Return suggested process exit code.

    Returns:
        1 if failures exist, otherwise 0.
    """
    return 1 if self.has_failures else 0

def _ok(self, check: str, detail: str = "") -> None:
    """Record a passed check."""
    self._results.append(("OK", check, detail))

def _warn(self, check: str, detail: str = "") -> None:
    """Record a warning."""
    self._results.append(("WARNING", check, detail))

def _fail(self, check: str, detail: str = "") -> None:
    """Record a failed check."""
    self._results.append(("FAIL", check, detail))

def _check_config(self) -> None:
    """Check configuration loads correctly."""
    try:
        self._config.load()
        data = self._config.data

        if not isinstance(data, dict) or not data:
            self._fail("Config loaded", "Configuration is empty or invalid")
            return

        config_path = getattr(self._config, "path", "config.json")
        camera_index = self._config.get("camera.index", "?")
        video_path = self._config.get("video.path", "videos/selamlama.mp4")

        self._ok(
            "Config loaded",
            f"path={config_path}, camera.index={camera_index}, video.path={video_path}",
        )

    except Exception as exc:
        self._fail("Config loaded", str(exc))

def _check_log_directory(self) -> None:
    """Check log directory is writable."""
    try:
        base_dir = getattr(self._config, "base_dir", Path.cwd())
        log_dir = Path(base_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        test_file = log_dir / ".healthcheck_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)

        self._ok("Log directory writable", str(log_dir.resolve()))

    except OSError as exc:
        self._fail("Log directory writable", str(exc))
    except Exception as exc:
        self._fail("Log directory writable", str(exc))

def _check_player(self) -> None:
    """Check if configured video player is available."""
    player = str(self._config.get("video.player", "mpv")).strip() or "mpv"
    player_path = shutil.which(player)

    if player_path:
        self._ok(f"{player} found", player_path)
    else:
        install_hint = "sudo apt install mpv" if player == "mpv" else f"Install player: {player}"
        self._fail(f"{player} found", install_hint)

def _check_opencv(self) -> None:
    """Check OpenCV import and basic functionality."""
    try:
        cv2 = importlib.import_module("cv2")
        np = importlib.import_module("numpy")

        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)

        if gray.shape == (100, 100):
            self._ok("OpenCV", f"version {cv2.__version__}")
        else:
            self._fail("OpenCV", "Basic cvtColor test failed")

    except ImportError as exc:
        self._fail("OpenCV", f"Import failed: {exc}")
    except Exception as exc:
        self._fail("OpenCV", str(exc))

def _check_camera(self) -> None:
    """Check if camera can be opened and can read one frame."""
    try:
        cv2 = importlib.import_module("cv2")
    except ImportError as exc:
        self._fail("Camera opened", f"OpenCV import failed: {exc}")
        return

    raw_index = self._config.get("camera.index", 0)
    camera_index = self._normalize_camera_index(raw_index)

    width = self._safe_int(self._config.get("camera.width", 640), 640, minimum=1)
    height = self._safe_int(self._config.get("camera.height", 480), 480, minimum=1)
    fps = self._safe_int(self._config.get("camera.fps", 15), 15, minimum=1)
    backend = str(self._config.get("camera.backend", "v4l2")).lower().strip()

    cap = None

    try:
        if backend == "v4l2" and hasattr(cv2, "CAP_V4L2"):
            cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(camera_index)

        if cap is None or not cap.isOpened():
            self._fail("Camera opened", f"Cannot open camera at index/device {camera_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        ok, frame = cap.read()

        if not ok or frame is None:
            self._warn("Camera opened", "Camera opened but frame read failed")
            return

        actual_height, actual_width = frame.shape[:2]
        device_detail = self._camera_device_detail(camera_index)

        self._ok(
            "Camera opened",
            f"{device_detail} frame={actual_width}x{actual_height}, requested={width}x{height}@{fps}",
        )

    except Exception as exc:
        self._fail("Camera opened", str(exc))

    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                logger.debug("Camera release failed during health check", exc_info=True)

def _check_video_file(self) -> None:
    """Check if configured video file exists."""
    try:
        video_path = self._resolve_config_path("video.path", "videos/selamlama.mp4")

        if not video_path.exists():
            self._warn("Video found", f"Not found: {video_path}")
            return

        if not video_path.is_file():
            self._fail("Video found", f"Path is not a file: {video_path}")
            return

        size_mb = video_path.stat().st_size / (1024 * 1024)

        if size_mb <= 0:
            self._fail("Video found", f"File is empty: {video_path}")
            return

        self._ok("Video found", f"{video_path} ({size_mb:.1f} MB)")

    except Exception as exc:
        self._fail("Video found", str(exc))

def _check_admin_port(self) -> None:
    """Check if admin panel port can be bound."""
    if not self._config.get("admin.enabled", True):
        self._ok("Admin panel", "Disabled in config")
        return

    host = str(self._config.get("admin.host", "0.0.0.0")).strip() or "0.0.0.0"
    port = self._safe_int(self._config.get("admin.port", 8080), 8080, minimum=1, maximum=65535)

    bind_host = host

    if host in {"0.0.0.0", "::"}:
        bind_host = "0.0.0.0"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_host, port))

        self._ok("Admin panel", f"Port {port} is available on {host}")

    except OSError as exc:
        self._warn("Admin panel", f"Port {port} may already be in use: {exc}")
    except Exception as exc:
        self._warn("Admin panel", f"Port check failed: {exc}")

def _check_venv(self) -> None:
    """Check virtual environment path for systemd service."""
    expected_venv_python = Path("/opt/modInteractive/venv/bin/python")
    old_venv_python = Path("/opt/modInteractive/.venv/bin/python")

    if expected_venv_python.is_file():
        self._ok("Virtualenv path", str(expected_venv_python))
        return

    if old_venv_python.is_file():
        self._warn(
            "Virtualenv path",
            f"{old_venv_python} exists, but expected {expected_venv_python}",
        )
        return

    if hasattr(sys, "real_prefix") or sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        self._ok("Virtualenv path", f"Running inside venv: {sys.prefix}")
        return

    self._warn("Virtualenv path", "Not installed yet or not running inside a virtualenv")

def _resolve_config_path(self, key_path: str, default: str) -> Path:
    """Resolve a config path relative to the config file directory."""
    if hasattr(self._config, "resolve_path"):
        return self._config.resolve_path(key_path, default)

    raw_path = str(self._config.get(key_path, default))
    path = Path(raw_path).expanduser()

    if not path.is_absolute():
        base_dir = getattr(self._config, "base_dir", Path.cwd())
        path = Path(base_dir) / path

    return path.resolve()

def _normalize_camera_index(self, raw_index: Any) -> Any:
    """Normalize camera index while allowing device paths."""
    if isinstance(raw_index, int):
        return raw_index

    if isinstance(raw_index, str):
        value = raw_index.strip()

        if value.isdigit():
            return int(value)

        return value

    try:
        return int(raw_index)
    except (TypeError, ValueError):
        return 0

def _camera_device_detail(self, camera_index: Any) -> str:
    """Return human-friendly camera device detail."""
    if isinstance(camera_index, int):
        device_path = Path(f"/dev/video{camera_index}")

        if device_path.exists():
            return str(device_path)

        return f"index={camera_index}"

    return str(camera_index)

def _safe_int(
    self,
    value: Any,
    default: int,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    """Convert value to int with optional bounds."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    if minimum is not None and number < minimum:
        number = minimum

    if maximum is not None and number > maximum:
        number = maximum

    return number