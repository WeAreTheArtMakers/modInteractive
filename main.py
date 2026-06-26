"""modInteractive v1.0.0 - Interactive Kiosk Application for Raspberry Pi.

Entry point for the kiosk system.  Sets up logging, handles signals,
and runs the main application loop.

Usage:
    python main.py              # Normal run
    python main.py --check      # System check mode
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from app import Application
from core.config import Config
from core.logger import setup_logger

# Ensure project root is in path
PROJECT_ROOT: str = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="modInteractive - Interactive Kiosk Application"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run system checks and exit",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )
    return parser.parse_args()


def run_checks(config_path: str) -> None:
    """Run system checks and print status report.

    Args:
        config_path: Path to configuration file
    """
    print("=" * 60)
    print("modInteractive - System Check")
    print("=" * 60)

    # 1. Config check
    config = Config(config_path)
    config.load()
    print("[OK] Configuration loaded: %s" % config_path)

    # 2. Log directory check
    log_dir = Path("logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        print("[OK] Log directory is writable: logs/")
    except OSError as e:
        print("[FAIL] Log directory not writable: %s" % e)

    # 3. Video file check
    video = config.video_path
    if os.path.exists(video):
        print("[OK] Video file found: %s" % video)
    else:
        print("[WARNING] Video file not found: %s" % video)

    # 4. Player check
    from core.player import Player
    player = Player(
        player=config.get("player", "mpv"),
        fullscreen=False,
    )
    if player.is_available:
        print("[OK] Player '%s' is available" % player.player_name)
    else:
        print("[WARNING] Player '%s' not found" % player.player_name)

    # 5. Camera check
    import cv2
    try:
        cam = cv2.VideoCapture(config.camera_index)
        if cam.isOpened():
            ret, frame = cam.read()
            if ret and frame is not None:
                print("[OK] Camera (index %d) is available" % config.camera_index)
                print("    Resolution: %dx%d" % (frame.shape[1], frame.shape[0]))
            else:
                print("[WARNING] Camera opened but cannot read frames")
            cam.release()
        else:
            print("[FAIL] Cannot open camera (index %d)" % config.camera_index)
    except Exception as e:
        print("[FAIL] Camera error: %s" % e)

    # 6. Python version
    print("[OK] Python %s" % sys.version.split()[0])

    print("-" * 60)
    print("System check complete")


def main() -> None:
    """Main entry point.

    Parses arguments, configures logging, sets up signal handlers,
    and runs the application.
    """
    args = parse_args()

    # Run checks and exit if requested
    if args.check:
        run_checks(args.config)
        sys.exit(0)

    # Setup logging
    logger = setup_logger(
        log_dir="logs",
        log_file="modinteractive.log",
        level="INFO",
    )

    logger.info("=" * 60)
    logger.info("modInteractive v1.0.0 - Interactive Kiosk Application")
    logger.info("=" * 60)

    # Create required directories
    try:
        os.makedirs("logs", exist_ok=True)
        os.makedirs("videos", exist_ok=True)
    except OSError as e:
        logger.error("Cannot create directories: %s", e)
        sys.exit(1)

    # Create application instance
    app = Application(config_path=args.config)

    # Signal handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(signum: int, frame: object) -> None:
        """Handle termination signals gracefully."""
        logger.info("Signal %d received, shutting down...", signum)
        app.stop()
        loop.call_soon_threadsafe(loop.stop)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run application
    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        # Cleanup
        if not loop.is_closed():
            loop.run_until_complete(app.shutdown())
            loop.close()

    logger.info("Application exited")
    sys.exit(0)


if __name__ == "__main__":
    main()