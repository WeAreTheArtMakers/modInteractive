"""Logging setup for modInteractive kiosk system.

Provides dual logging: console (stdout) and rotating file in logs/ directory.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    log_dir: str = "logs",
    log_file: str = "modinteractive.log",
    level: str = "INFO",
    max_bytes: int = 5_242_880,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure and return the root logger for modInteractive.

    Sets up logging to both console and a rotating file handler.

    Args:
        log_dir: Directory for log files
        log_file: Log file name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep

    Returns:
        Configured root logger
    """
    # Create log directory if needed
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"WARNING: Cannot create log directory {log_dir}: {e}", file=sys.stderr)
        log_path = Path(".")

    # Resolve numeric log level
    numeric_level: int = getattr(logging, level.upper(), logging.INFO)

    # Root logger for modInteractive
    logger = logging.getLogger("modInteractive")
    logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates on reconfiguration
    logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (rotating)
    file_path = log_path / log_file
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning("Cannot create log file %s: %s", file_path, e)

    # Suppress noisy library loggers
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("cv2").setLevel(logging.WARNING)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a named child logger of modInteractive.

    Args:
        name: Optional sub-logger name

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"modInteractive.{name}")
    return logging.getLogger("modInteractive")