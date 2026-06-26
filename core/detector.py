"""Detection module for modInteractive kiosk system.

Provides motion detection via OpenCV background subtraction,
with optional YOLO-based person detection for future expansion.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("modInteractive.detector")


class Detector:
    """Motion and person detector using OpenCV.

    Uses MOG2 background subtraction for motion detection.
    YOLO detection mode is planned for future enhancement.
    """

    def __init__(
        self,
        sensitivity: float = 500.0,
        confidence: float = 0.5,
        mode: str = "motion",
    ) -> None:
        """Initialize detector.

        Args:
            sensitivity: Motion sensitivity (lower = more sensitive)
            confidence: Detection confidence threshold
            mode: Detection mode ('motion' or 'yolo')
        """
        self._sensitivity: float = sensitivity
        self._confidence: float = confidence
        self._mode: str = mode
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=16, detectShadows=True
        )
        self._yolo_model: Any = None
        self._last_detection_time: float = 0.0
        self._frame_count: int = 0

        logger.info(
            "Detector initialized: mode=%s, sensitivity=%.1f, confidence=%.2f",
            self._mode,
            self._sensitivity,
            self._confidence,
        )

    def set_sensitivity(self, value: float) -> None:
        """Set motion sensitivity.

        Args:
            value: Sensitivity value (lower = more sensitive)
        """
        self._sensitivity = max(100.0, float(value))
        logger.debug("Motion sensitivity set to: %.1f", self._sensitivity)

    def set_confidence(self, value: float) -> None:
        """Set detection confidence threshold.

        Args:
            value: Confidence threshold (0.0 to 1.0)
        """
        self._confidence = max(0.1, min(1.0, float(value)))
        logger.debug("Detection confidence set to: %.2f", self._confidence)

    def detect(self, frame: np.ndarray) -> Tuple[bool, float, Dict[str, Any]]:
        """Detect motion or person in a frame.

        Args:
            frame: OpenCV BGR image frame

        Returns:
            Tuple of (detected, confidence, metadata)
        """
        self._frame_count += 1
        detected: bool = False
        confidence: float = 0.0
        metadata: Dict[str, Any] = {}

        if self._mode == "yolo":
            detected, confidence, metadata = self._detect_yolo(frame)
        else:
            detected, confidence, metadata = self._detect_motion(frame)

        if detected:
            self._last_detection_time = time.time()
            metadata["method"] = self._mode
            logger.debug(
                "Detection: method=%s, confidence=%.2f",
                self._mode,
                confidence,
            )

        return detected, confidence, metadata

    def _detect_motion(
        self, frame: np.ndarray
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Detect motion using background subtraction.

        Args:
            frame: OpenCV BGR image frame

        Returns:
            Tuple of (detected, confidence, metadata)
        """
        # Apply background subtractor
        fg_mask = self._bg_subtractor.apply(frame)

        # Noise removal
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        # Count changed pixels
        motion_pixels = cv2.countNonZero(fg_mask)

        metadata: Dict[str, Any] = {
            "motion_pixels": motion_pixels,
            "threshold": self._sensitivity,
        }

        if motion_pixels > self._sensitivity:
            # Calculate a pseudo-confidence based on motion amount
            confidence = min(1.0, motion_pixels / (self._sensitivity * 10))
            return True, confidence, metadata

        return False, 0.0, metadata

    def _detect_yolo(
        self, frame: np.ndarray
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Detect persons using YOLO model.

        Args:
            frame: OpenCV BGR image frame

        Returns:
            Tuple of (detected, confidence, metadata)
        """
        if self._yolo_model is None:
            try:
                from ultralytics import YOLO
                self._yolo_model = YOLO("models/yolov8n.pt")
                logger.info("YOLO model loaded")
            except ImportError:
                logger.warning(
                    "YOLO not available, falling back to motion detection"
                )
                return self._detect_motion(frame)
            except Exception as e:
                logger.error("Failed to load YOLO model: %s", e)
                return self._detect_motion(frame)

        try:
            results = self._yolo_model(frame, verbose=False)
            detections = results[0].boxes

            if len(detections) == 0:
                return False, 0.0, {}

            # Filter for persons (class 0 in COCO)
            persons = detections[detections.cls == 0]
            if len(persons) == 0:
                return False, 0.0, {}

            # Get highest confidence person detection
            confs = persons.conf.cpu().numpy()
            best_idx = int(confs.argmax())
            best_confidence = float(confs[best_idx])

            if best_confidence >= self._confidence:
                metadata: Dict[str, Any] = {
                    "persons_detected": len(persons),
                    "boxes": persons.xyxy.cpu().numpy().tolist(),
                }
                return True, best_confidence, metadata

        except Exception as e:
            logger.error("YOLO detection error: %s", e)

        return False, 0.0, {}

    def reset_background(self) -> None:
        """Reset the background model for motion detection."""
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=16, detectShadows=True
        )
        logger.info("Background model reset")

    @property
    def frame_count(self) -> int:
        """Get total frames processed."""
        return self._frame_count

    @property
    def last_detection_time(self) -> float:
        """Get timestamp of last detection."""
        return self._last_detection_time