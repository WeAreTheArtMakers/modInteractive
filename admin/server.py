"""Admin web server for modInteractive.

Provides a web-based configuration and monitoring interface.
Runs as an optional component - main system is not affected if admin fails.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

logger = logging.getLogger("modInteractive.admin")

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)

_config_data: Dict[str, Any] = {}
_config_path: str = ""


def init(config: Any, config_path: str) -> None:
    """Initialize admin server with config.

    Args:
        config: Config object
        config_path: Path to config file
    """
    global _config_data, _config_path
    _config_data = config.data
    _config_path = config_path


@app.route("/")
def index() -> str:
    """Render admin panel."""
    return render_template("index.html")


@app.route("/api/config")
def get_config() -> Any:
    """Get current configuration.

    Returns:
        JSON configuration
    """
    config_file = Path(_config_path)
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Config not found"}), 404


@app.route("/api/config/update", methods=["POST"])
def update_config() -> Any:
    """Update configuration.

    Returns:
        Success status
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        config_file = Path(_config_path)
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        return jsonify({"status": "ok", "message": "Configuration updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def get_status() -> Any:
    """Get system status.

    Returns:
        JSON status information
    """
    import cv2

    status = {
        "opencv_version": cv2.__version__,
        "camera_available": False,
        "video_exists": False,
        "mpv_available": False,
    }

    # Check camera
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            status["camera_available"] = True
            ret, frame = cap.read()
            if ret and frame is not None:
                status["camera_resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
            cap.release()
    except Exception:
        pass

    # Check video
    video_path = _config_data.get("video", {}).get("path", "videos/selamlama.mp4")
    status["video_exists"] = os.path.exists(video_path)

    # Check mpv
    import shutil
    status["mpv_available"] = shutil.which("mpv") is not None

    return jsonify(status)


@app.route("/api/test-video", methods=["POST"])
def test_video() -> Any:
    """Test video playback using mpv.

    Returns:
        Success status
    """
    import shutil
    import subprocess

    mpv_path = shutil.which("mpv")
    if not mpv_path:
        return jsonify({"error": "mpv not installed"}), 500

    video_path = _config_data.get("video", {}).get("path", "videos/selamlama.mp4")
    abs_path = os.path.abspath(video_path)

    if not os.path.exists(abs_path):
        return jsonify({"error": f"Video not found: {abs_path}"}), 404

    fullscreen = _config_data.get("video", {}).get("fullscreen", True)

    try:
        cmd = [mpv_path]
        if fullscreen:
            cmd.append("--fs")
        cmd.append("--keep-open=no")
        cmd.append("--really-quiet")
        cmd.append(abs_path)

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return jsonify({"status": "ok", "message": f"Playing: {abs_path}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs")
def get_logs() -> Any:
    """Get recent log entries.

    Returns:
        JSON log entries
    """
    log_file = Path("logs") / "modinteractive.log"
    if not log_file.exists():
        return jsonify({"logs": []})

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        # Return last 100 lines
        return jsonify({"logs": lines[-100:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run Flask admin server in a separate thread.

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    try:
        logger.info("Admin panel starting on http://%s:%d", host, port)
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error("Admin panel failed to start: %s", e)


def start_admin_thread(config: Any, config_path: str) -> threading.Thread:
    """Start admin server in a background thread.

    Args:
        config: Config object
        config_path: Path to config file

    Returns:
        Admin server thread
    """
    init(config, config_path)

    host = config.get("admin.host", "0.0.0.0")
    port = config.get("admin.port", 8080)

    thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True,
        name="admin-server",
    )
    thread.start()
    logger.info("Admin panel thread started on port %d", port)
    return thread