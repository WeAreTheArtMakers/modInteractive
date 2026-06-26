"""Core services for modInteractive kiosk system."""

from core.config import Config
from core.logger import setup_logger
from core.detector import Detector
from core.player import Player

__all__ = ["Config", "setup_logger", "Detector", "Player"]