"""Detection module for modInteractive.

Provides motion detection via OpenCV background subtraction.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("modInteractive.detector")


class Detector:
    """Motion detector using OpenCV MOG2 background subtraction."""

    def __init__(
        self,
        sensitivity: float = 500.0,
        min_area: float = 1500.0,
        warmup_frames: int = 30,
    ) -> None:
        """Initialize detector.

        Args:
            sensitivity: Motion sensitivity (lower = more sensitive)
            min_area: Minimum motion area to trigger (pixels)
            warmup_frames: Frames to learn background before detecting
        """
        self._sensitivity: float = max(100.0, float(sensitivity))
        self._min_area: float = max(500.0, float(min_area))
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=16, detectShadows=True
        )
        self._last_detection_time: float = 0.0
        self._frame_count: int = 0
        self._warmup_frames: int = warmup_frames
        self._is_warmed_up: bool = False
        self._previous_gray: Optional[np.ndarray] = None

        logger.info(
            "Detector initialized: sensitivity=%.1f, min_area=%.1f",
            self._sensitivity, self._min_area,
        )

    def warmup(self, frame: np.ndarray) -> None:
        """Feed frames to background model without detecting.

        Args:
            frame: OpenCV BGR image frame
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        self._bg_subtractor.apply(frame)
        self._frame_count += 1
        self._previous_gray = gray

    def set_sensitivity(self, value: float) -> None:
        """Set motion sensitivity.

        Args:
            value: Sensitivity value (lower = more sensitive)
        """
        self._sensitivity = max(100.0, float(value))

    def set_min_area(self, value: float) -> None:
        """Set minimum motion area threshold.

        Args:
            value: Minimum area in pixels
        """
        self._min_area = max(500.0, float(value))

    def detect(self, frame: np.ndarray) -> Tuple[bool, float, int, Dict[str, Any]]:
        """Detect motion in a frame.

        Args:
            frame: OpenCV BGR image frame

        Returns:
            Tuple of (detected, confidence, motion_pixels, metadata)
        """
        self._frame_count += 1

        if not self._is_warmed_up:
            if self._frame_count < self._warmup_frames:
                self.warmup(frame)
                return False, 0.0, 0, {}
            self._is_warmed_up = True
            logger.info("Detector warmup complete (%d frames)",
                        self._warmup_frames)

        # Motion detection with frame differencing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        delta = cv2.absdiff(self._previous_gray, gray)
        self._previous_gray = gray

        # Apply background subtraction as second check
        fg_mask = self._bg_subtractor.apply(frame)
        fg_mask = cv2.medianBlur(fg_mask, 5)

        # Threshold both
        _, delta_thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)
        _, fg_thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Combine: motion detected in both methods
        combined = cv2.bitwise_and(delta_thresh, fg_thresh)

        # Morphological noise removal
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

        # Count motion pixels
        motion_pixels = cv2.countNonZero(combined)

        metadata: Dict[str, Any] = {
            "motion_pixels": motion_pixels,
            "sensitivity": self._sensitivity,
            "min_area": self._min_area,
        }

        # Check against sensitivity AND minimum area
        if motion_pixels > self._sensitivity:
            # Find contours to check actual area
            contours, _ = cv2.findContours(
                combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            max_area = 0.0
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > max_area:
                    max_area = area

            metadata["max_contour_area"] = max_area

            if max_area > self._min_area:
                now = time.time()
                self._last_detection_time = now
                confidence = min(1.0, motion_pixels / (self._sensitivity * 5))
                return True, confidence, motion_pixels, metadata

        return False, 0.0, motion_pixels, metadata

    def reset_background(self) -> None:
        """Reset the background model."""
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=16, detectShadows=True
        )
        self._is_warmed_up = False
        self._frame_count = 0
        self._previous_gray = None
        logger.info("Background model reset")

    @property
    def frame_count(self) -> int:
        """Get total frames processed."""
        return self._frame_count

    @property
    def last_detection_time(self) -> float:
        """Get timestamp of last detection."""
        return self._last_detection_time

    @property
    def is_warmed_up(self) -> bool:
        """Check if detector has completed warmup."""
        return self._is_warmed_up