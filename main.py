"""modInteractive - AI-Powered Kiosk System.

Entry point for the modInteractive kiosk application.
Raspberry Pi 5 optimized with AI-based person detection and video playback.
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "modinteractive.log"),
    ],
)

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
    logger.info("=" * 60)

    app = None
    try:
        # Import and create application
        from app import Application
        app = Application(config_path="config.json")

        # Start the application
        await app.start()

        # Keep running until shutdown
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
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("videos", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    # Run the async event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
