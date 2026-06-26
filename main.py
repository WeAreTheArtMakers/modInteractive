"""modInteractive - AI-Powered Kiosk System.

Entry point for the modInteractive kiosk application.
Raspberry Pi 5 optimized with AI-based person detection and video playback.

Environment setup for Pi5:
- QT_QPA_PLATFORM=wayland (PiOS Bookworm default)
- DISPLAY=:0 (X11 fallback)
- Font fallback for Pi5 (DejaVu Sans)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Pi5 Environment Setup ──
# Set Qt platform for Pi5 (Wayland preferred, X11 fallback)
if "QT_QPA_PLATFORM" not in os.environ:
    if os.path.exists("/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms/libqwayland.so"):
        os.environ["QT_QPA_PLATFORM"] = "wayland"
    else:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        os.environ.setdefault("DISPLAY", ":0")
        os.environ.setdefault("XAUTHORITY", os.path.expanduser("~/.Xauthority"))

# Set XDG_RUNTIME_DIR for Wayland
if "XDG_RUNTIME_DIR" not in os.environ:
    runtime_dir = f"/run/user/{os.getuid()}" if os.name == "posix" else "/tmp"
    if os.path.exists(runtime_dir):
        os.environ["XDG_RUNTIME_DIR"] = runtime_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "modinteractive.log"),
    ],
)

# Reduce OpenCV and Ultralytics logging noise
logging.getLogger("ultralytics").setLevel(logging.WARNING)
logging.getLogger("cv2").setLevel(logging.WARNING)

logger = logging.getLogger("modInteractive")


def signal_handler(signum: int, frame) -> None:
    """Handle system signals for graceful shutdown.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info(f"Received signal {signum}, initiating shutdown...")
    sys.exit(0)


async def main() -> None:
    """Main entry point for modInteractive."""
    logger.info("=" * 60)
    logger.info("modInteractive v2.0.0 - AI Kiosk System")
    logger.info(f"Qt Platform: {os.environ.get('QT_QPA_PLATFORM', 'default')}")
    logger.info(f"Display: {os.environ.get('DISPLAY', 'none')}")
    logger.info("=" * 60)

    app = None
    try:
        from app import Application
        app = Application(config_path="config.json")

        await app.start()

        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if app:
            await app.stop()

    logger.info("modInteractive shutdown complete")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    os.makedirs("logs", exist_ok=True)
    os.makedirs("videos", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
