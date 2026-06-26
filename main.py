"""modInteractive v2.0.0 - Pi5 AI Kiosk"""
from __future__ import annotations
import asyncio, logging, os, signal, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pi5 Environment
if "QT_QPA_PLATFORM" not in os.environ:
    wayland = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms/libqwayland.so"
    os.environ["QT_QPA_PLATFORM"] = "wayland" if os.path.exists(wayland) else "xcb"
if os.environ.get("QT_QPA_PLATFORM") == "xcb":
    os.environ.setdefault("DISPLAY", ":0")
    os.environ.setdefault("XAUTHORITY", os.path.expanduser("~/.Xauthority"))
if "XDG_RUNTIME_DIR" not in os.environ:
    d = f"/run/user/{os.getuid()}"
    if os.path.exists(d):
        os.environ["XDG_RUNTIME_DIR"] = d

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(Path("logs") / "modinteractive.log")])
logging.getLogger("ultralytics").setLevel(logging.WARNING)
logging.getLogger("cv2").setLevel(logging.WARNING)
logger = logging.getLogger("modInteractive")

def signal_handler(signum, frame):
    logger.info(f"Signal {signum}, shutting down..."); sys.exit(0)

async def main():
    logger.info("="*60)
    logger.info("modInteractive v2.0.0 - AI Kiosk System")
    logger.info(f"Qt: {os.environ.get('QT_QPA_PLATFORM','?')}, "
                f"Display: {os.environ.get('DISPLAY','?')}")
    logger.info("="*60)
    # Pi5 touch screen
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.setAttribute(Qt.AA_EnableTouchAdaptor)
    except: pass
    app = None
    try:
        from app import Application
        app = Application(config_path="config.json")
        await app.start()
        while True: await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt): logger.info("Shutdown")
    except Exception as e: logger.error(f"Fatal: {e}", exc_info=True)
    finally:
        if app: await app.stop()
    logger.info("Shutdown complete")

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs("logs", exist_ok=True); os.makedirs("videos", exist_ok=True); os.makedirs("models", exist_ok=True)
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
