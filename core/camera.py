"""Camera module for modInteractive.

Handles OpenCV camera initialization, frame capture,
reconnection, and warmup.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("modInteractive.camera")


class Camera:
    """OpenCV camera wrapper with reconnection support."""

    def __init__(
        self,
        index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 15,
        warmup_frames: int = 30,
    ) -> None:
        """Initialize camera configuration.

        Args:
            index: Camera device index
            width: Capture width in pixels
            height: Capture height in pixels
            fps: Target frames per second
            warmup_frames: Number of frames to discard on startup
        """
        self._index: int = index
        self._width: int = width
        self._height: int = height
        self._fps: int = fps
        self._warmup_frames: int = warmup_frames
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_open: bool = False
        self._frame_count: int = 0
        self._error_count: int = 0

    def open(self) -> bool:
        """Open the camera device.

        Returns:
            True if camera opened successfully
        """
        if self._is_open:
            return True

        try:
            self._cap = cv2.VideoCapture(self._index)

            if not self._cap.isOpened():
                logger.error("Cannot open camera at index %d", self._index)
                self._cap = None
                return False

            # Set camera properties
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS, self._fps)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Warmup: discard initial frames for auto-exposure adjustment
            logger.info("Camera warmup: discarding %d frames...",
                        self._warmup_frames)
            for i in range(self._warmup_frames):
                self._cap.read()

            self._is_open = True
            self._frame_count = 0
            self._error_count = 0

            actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            logger.info(
                "Camera opened: index=%d, %dx%d @ %d fps",
                self._index, actual_width, actual_height, self._fps,
            )
            return True

        except Exception as e:
            logger.error("Camera open error: %s", e)
            self._cap = None
            return False

    def read(self) -> Optional[np.ndarray]:
        """Read a single frame from the camera.

        Returns:
            Frame as numpy array (BGR), or None on failure
        """
        if not self._is_open or self._cap is None:
            return None

        try:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._error_count += 1
                logger.warning("Camera read failed (%d errors)",
                               self._error_count)
                return None

            self._frame_count += 1
            self._error_count = 0
            return frame

        except Exception as e:
            self._error_count += 1
            logger.error("Camera read error: %s", e)
            return None

    def close(self) -> None:
        """Release the camera device."""
        if self._cap is not None:
            try:
                self._cap.release()
                logger.info("Camera released")
            except Exception as e:
                logger.error("Camera release error: %s", e)
            finally:
                self._cap = None
                self._is_open = False

    def reopen(self) -> bool:
        """Close and reopen the camera.

        Returns:
            True if reopen succeeded
        """
        self.close()
        time.sleep(1)
        return self.open()

    @property
    def is_open(self) -> bool:
        """Check if camera is currently open."""
        return self._is_open

    @property
    def frame_count(self) -> int:
        """Get total frames read."""
        return self._frame_count

    @property
    def error_count(self) -> int:
        """Get consecutive read errors."""
        return self._error_count

    @property
    def index(self) -> int:
        """Get camera device index."""
        return self._index