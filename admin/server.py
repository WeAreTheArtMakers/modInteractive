from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, render_template, request

logger = logging.getLogger("modInteractive.admin")

BASE_DIR = Path(__file__).resolve().parents[1]

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static"),
)

_config: Optional[Any] = None
_config_data: Dict[str, Any] = {}
_config_path: Path = BASE_DIR / "config.json"


def init(config: Any, config_path: str) -> None:
    global _config, _config_data, _config_path

    _config = config
    _config_path = Path(config_path).expanduser().resolve()

    try:
        if hasattr(config, "reload"):
            config.reload()
        elif hasattr(config, "load"):
            config.load()

        data = getattr(config, "data", {})
        _config_data = dict(data) if isinstance(data, dict) else {}
    except Exception:
        logger.exception("Admin config initialization failed")
        _config_data = _read_config_file()


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config() -> Any:
    data = _read_config_file()

    if not data:
        return jsonify({"error": "Config not found or empty"}), 404

    return jsonify(data)


@app.route("/api/config/update", methods=["POST"])
def update_config() -> Any:
    global _config_data

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    try:
        if _config is not None and hasattr(_config, "update"):
            _config.update(data, save=True)
            _config_data = dict(_config.data)
        else:
            current = _read_config_file()
            merged = _deep_merge(current, data)
            _write_config_file(merged)
            _config_data = merged

        return jsonify(
            {
                "status": "ok",
                "message": "Configuration updated",
                "config": _config_data,
            }
        )

    except Exception as exc:
        logger.exception("Config update failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reload-config", methods=["POST"])
def reload_config() -> Any:
    global _config_data

    try:
        if _config is not None and hasattr(_config, "reload"):
            _config.reload()
            _config_data = dict(_config.data)
        else:
            _config_data = _read_config_file()

        return jsonify(
            {
                "status": "ok",
                "message": "Configuration reloaded",
                "config": _config_data,
            }
        )

    except Exception as exc:
        logger.exception("Config reload failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/status", methods=["GET"])
def get_status() -> Any:
    data = _current_config()
    status: Dict[str, Any] = {
        "admin": "running",
        "project_root": str(BASE_DIR),
        "config_path": str(_config_path),
        "opencv_available": False,
        "opencv_version": None,
        "camera_available": False,
        "camera_resolution": None,
        "video_exists": False,
        "video_path": None,
        "mpv_available": shutil.which("mpv") is not None,
        "mpv_path": shutil.which("mpv"),
    }

    try:
        import cv2

        status["opencv_available"] = True
        status["opencv_version"] = cv2.__version__

        camera_index = _normalize_camera_index(
            _nested_get(data, "camera.index", 0)
        )
        camera_width = _safe_int(_nested_get(data, "camera.width", 640), 640, 1)
        camera_height = _safe_int(_nested_get(data, "camera.height", 480), 480, 1)
        camera_fps = _safe_int(_nested_get(data, "camera.fps", 15), 15, 1)
        camera_backend = str(_nested_get(data, "camera.backend", "v4l2")).lower()

        if camera_backend == "v4l2" and hasattr(cv2, "CAP_V4L2"):
            cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(camera_index)

        try:
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
                cap.set(cv2.CAP_PROP_FPS, camera_fps)

                ok, frame = cap.read()

                if ok and frame is not None:
                    status["camera_available"] = True
                    status["camera_resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
                else:
                    status["camera_available"] = True
                    status["camera_resolution"] = "opened but no frame"
        finally:
            cap.release()

    except Exception as exc:
        status["camera_error"] = str(exc)

    video_path = _resolve_video_path(str(_nested_get(data, "video.path", "videos/selamlama.mp4")))
    status["video_path"] = str(video_path)
    status["video_exists"] = video_path.is_file()

    if video_path.is_file():
        status["video_size_mb"] = round(video_path.stat().st_size / (1024 * 1024), 2)

    return jsonify(status)


@app.route("/api/test-video", methods=["POST"])
def test_video() -> Any:
    data = _current_config()
    mpv_path = shutil.which(str(_nested_get(data, "video.player", "mpv")))

    if not mpv_path:
        return jsonify({"error": "mpv not installed. Install: sudo apt install mpv"}), 500

    requested_video = None
    body = request.get_json(silent=True)

    if isinstance(body, dict):
        requested_video = body.get("path")

    video_value = str(requested_video or _nested_get(data, "video.path", "videos/selamlama.mp4"))
    video_path = _resolve_video_path(video_value)

    allowed, reason = _is_allowed_video_path(video_path)

    if not allowed:
        return jsonify({"error": reason}), 403

    if not video_path.is_file():
        return jsonify({"error": f"Video not found: {video_path}"}), 404

    fullscreen = bool(_nested_get(data, "video.fullscreen", True))
    volume = _safe_int(_nested_get(data, "video.volume", 90), 90, 0, 100)

    command = [
        mpv_path,
        "--no-terminal",
        "--really-quiet",
        "--keep-open=no",
        "--osd-level=0",
        f"--volume={volume}",
    ]

    if fullscreen:
        command.extend(["--fs", "--no-border", "--ontop", "--cursor-autohide=always"])

    command.append(str(video_path))

    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
        )

        return jsonify(
            {
                "status": "ok",
                "message": "Video playback started",
                "video": str(video_path),
            }
        )

    except Exception as exc:
        logger.exception("Test video failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/logs", methods=["GET"])
def get_logs() -> Any:
    limit = _safe_int(request.args.get("limit", 100), 100, 1, 1000)
    log_file = BASE_DIR / "logs" / "modinteractive.log"

    if not log_file.exists():
        return jsonify({"logs": []})

    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        return jsonify({"logs": lines[-limit:]})

    except Exception as exc:
        logger.exception("Reading logs failed")
        return jsonify({"error": str(exc)}), 500


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    try:
        logger.info("Admin panel starting on http://%s:%d", host, port)
        app.run(
            host=host,
            port=int(port),
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except Exception:
        logger.exception("Admin panel failed to start")


def start_admin_thread(config: Any, config_path: str) -> threading.Thread:
    init(config, config_path)

    host = str(config.get("admin.host", "0.0.0.0"))
    port = _safe_int(config.get("admin.port", 8080), 8080, 1, 65535)

    thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True,
        name="modinteractive-admin-server",
    )
    thread.start()

    logger.info("Admin panel thread started on port %d", port)
    return thread


def _current_config() -> Dict[str, Any]:
    if _config is not None:
        try:
            data = getattr(_config, "data", None)
            if isinstance(data, dict):
                return dict(data)
        except Exception:
            logger.debug("Could not read live config object", exc_info=True)

    return _read_config_file()


def _read_config_file() -> Dict[str, Any]:
    try:
        if not _config_path.exists():
            return {}

        data = json.loads(_config_path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            return data

        return {}

    except Exception:
        logger.exception("Could not read config file")
        return {}


def _write_config_file(data: Dict[str, Any]) -> None:
    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)

    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def _nested_get(data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    value: Any = data

    for key in key_path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def _resolve_video_path(value: str) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = BASE_DIR / path

    return path.resolve()


def _is_allowed_video_path(path: Path) -> Tuple[bool, str]:
    videos_dir = (BASE_DIR / "videos").resolve()

    try:
        path.relative_to(videos_dir)
        return True, ""
    except ValueError:
        return False, f"Only files under videos directory are allowed: {videos_dir}"


def _normalize_camera_index(value: Any) -> Any:
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        stripped = value.strip()

        if stripped.isdigit():
            return int(stripped)

        return stripped

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_int(
    value: Any,
    default: int,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    if minimum is not None and number < minimum:
        number = minimum

    if maximum is not None and number > maximum:
        number = maximum

    return number
