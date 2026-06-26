"""modInteractive v1.0.0 - Motion Triggered Video Display for Raspberry Pi.

Entry point for the kiosk system. Sets up logging, handles signals,
and runs the main application loop.

Usage:
    python main.py                  # Normal run
    python main.py --check          # System health check
    python main.py --config path    # Custom config path
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
from core.healthcheck import HealthCheck
from core.logger import setup_logger

PROJECT_ROOT: str = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="modInteractive - Motion Triggered Video Display for Raspberry Pi",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run system health check and exit",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )
    return parser.parse_args()


def run_health_check(config_path: str) -> None:
    """Run system health checks.

    Args:
        config_path: Path to configuration file
    """
    config = Config(config_path)
    config.load()

    check = HealthCheck(config)
    check.run_all()
    check.print_report()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Health check mode
    if args.check:
        run_health_check(args.config)
        sys.exit(0)

    # Setup logging
    logger = setup_logger(
        log_dir="logs",
        log_file="modinteractive.log",
        level="INFO",
    )

    logger.info("=" * 60)
    logger.info("modInteractive v1.0.0 - Motion Triggered Video Display")
    logger.info("=" * 60)

    # Create required directories
    for directory in ["logs", "videos"]:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            logger.error("Cannot create directory '%s': %s", directory, e)
            sys.exit(1)

    # Create application
    app = Application(config_path=args.config)

    # Start admin panel (optional)
    try:
        from app import _start_admin_thread
        _admin_thread = _start_admin_thread(app._config, args.config)
    except Exception:
        pass

    # Signal handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(signum: int, frame: object) -> None:
        """Handle termination signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
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
        if not loop.is_closed():
            loop.run_until_complete(app.shutdown())
            loop.close()

    logger.info("Application exited")
    sys.exit(0)


if __name__ == "__main__":
    main()