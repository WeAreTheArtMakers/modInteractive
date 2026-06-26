from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("modInteractive.detector")


class Detector:
    def __init__(
        self,
        sensitivity: float = 500.0,
        min_area: float = 1500.0,
        warmup_frames: int = 30,
    ) -> None:
        self._sensitivity = max(1.0, float(sensitivity))
        self._min_area = max(1.0, float(min_area))
        self._warmup_frames = max(0, int(warmup_frames))
        self._bg_subtractor = self._create_background_subtractor()
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        self._frame_count = 0
        self._warmup_count = 0
        self._is_warmed_up = self._warmup_frames == 0
        self._previous_gray: Optional[np.ndarray] = None
        self._last_detection_time = 0.0
        self._last_motion_pixels = 0
        self._last_max_area = 0.0

        logger.info(
            "Detector initialized: sensitivity=%.1f, min_area=%.1f, warmup_frames=%d",
            self._sensitivity,
            self._min_area,
            self._warmup_frames,
        )

    def detect(self, frame: np.ndarray) -> Tuple[bool, float, int, Dict[str, Any]]:
        self._frame_count += 1

        if not self._is_valid_frame(frame):
            logger.warning("Detector received invalid frame")
            return False, 0.0, 0, self._metadata()

        gray = self._prepare_gray(frame)

        if not self._is_warmed_up:
            self._warmup(frame, gray)
            return False, 0.0, 0, self._metadata(warming_up=True)

        if self._previous_gray is None:
            self._previous_gray = gray
            return False, 0.0, 0, self._metadata()

        delta_mask = self._frame_difference_mask(gray)
        bg_mask = self._background_subtraction_mask(frame)
        combined_mask = cv2.bitwise_and(delta_mask, bg_mask)
        combined_mask = self._clean_mask(combined_mask)

        motion_pixels = int(cv2.countNonZero(combined_mask))
        max_area = self._max_contour_area(combined_mask)

        self._last_motion_pixels = motion_pixels
        self._last_max_area = max_area
        self._previous_gray = gray

        detected = motion_pixels >= self._sensitivity and max_area >= self._min_area
        confidence = self._calculate_confidence(motion_pixels, max_area)

        metadata = self._metadata(
            motion_pixels=motion_pixels,
            max_contour_area=max_area,
            confidence=confidence,
            warming_up=False,
        )

        if detected:
            self._last_detection_time = time.time()
            logger.info(
                "Motion detected: pixels=%d, max_area=%.0f, confidence=%.2f",
                motion_pixels,
                max_area,
                confidence,
            )
            return True, confidence, motion_pixels, metadata

        return False, 0.0, motion_pixels, metadata

    def warmup(self, frame: np.ndarray) -> None:
        if not self._is_valid_frame(frame):
            return

        gray = self._prepare_gray(frame)
        self._warmup(frame, gray)

    def reset_background(self) -> None:
        self._bg_subtractor = self._create_background_subtractor()
        self._frame_count = 0
        self._warmup_count = 0
        self._is_warmed_up = self._warmup_frames == 0
        self._previous_gray = None
        self._last_motion_pixels = 0
        self._last_max_area = 0.0
        logger.info("Detector background model reset")

    def set_sensitivity(self, value: float) -> None:
        try:
            self._sensitivity = max(1.0, float(value))
        except (TypeError, ValueError):
            logger.warning("Invalid sensitivity value: %r", value)

    def set_min_area(self, value: float) -> None:
        try:
            self._min_area = max(1.0, float(value))
        except (TypeError, ValueError):
            logger.warning("Invalid min_area value: %r", value)

    def _warmup(self, frame: np.ndarray, gray: np.ndarray) -> None:
        self._bg_subtractor.apply(frame, learningRate=0.5)
        self._previous_gray = gray
        self._warmup_count += 1

        if self._warmup_count >= self._warmup_frames:
            self._is_warmed_up = True
            logger.info("Detector warmup complete: %d frames", self._warmup_count)

    def _prepare_gray(self, frame: np.ndarray) -> np.ndarray:
        if len(frame.shape) == 2:
            gray = frame
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        return cv2.GaussianBlur(gray, (21, 21), 0)

    def _frame_difference_mask(self, gray: np.ndarray) -> np.ndarray:
        if self._previous_gray is None:
            self._previous_gray = gray
            return np.zeros_like(gray)

        delta = cv2.absdiff(self._previous_gray, gray)
        _threshold_value, threshold = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)
        return threshold

    def _background_subtraction_mask(self, frame: np.ndarray) -> np.ndarray:
        fg_mask = self._bg_subtractor.apply(frame, learningRate=0.01)
        fg_mask = cv2.medianBlur(fg_mask, 5)
        _threshold_value, threshold = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        return threshold

    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, self._kernel)
        return cv2.dilate(cleaned, self._kernel, iterations=1)

    def _max_contour_area(self, mask: np.ndarray) -> float:
        contours, _hierarchy = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours:
            return 0.0

        return float(max(cv2.contourArea(contour) for contour in contours))

    def _calculate_confidence(self, motion_pixels: int, max_area: float) -> float:
        pixel_score = motion_pixels / max(self._sensitivity * 3.0, 1.0)
        area_score = max_area / max(self._min_area * 3.0, 1.0)
        confidence = max(pixel_score, area_score)
        return max(0.0, min(1.0, float(confidence)))

    def _metadata(
        self,
        motion_pixels: Optional[int] = None,
        max_contour_area: Optional[float] = None,
        confidence: float = 0.0,
        warming_up: bool = False,
    ) -> Dict[str, Any]:
        return {
            "motion_pixels": int(self._last_motion_pixels if motion_pixels is None else motion_pixels),
            "max_contour_area": float(self._last_max_area if max_contour_area is None else max_contour_area),
            "confidence": float(confidence),
            "sensitivity": float(self._sensitivity),
            "min_area": float(self._min_area),
            "frame_count": int(self._frame_count),
            "warmup_count": int(self._warmup_count),
            "warmup_frames": int(self._warmup_frames),
            "is_warmed_up": bool(self._is_warmed_up),
            "warming_up": bool(warming_up),
            "last_detection_time": float(self._last_detection_time),
        }

    def _is_valid_frame(self, frame: np.ndarray) -> bool:
        if frame is None:
            return False

        if not isinstance(frame, np.ndarray):
            return False

        if frame.size == 0:
            return False

        return len(frame.shape) in (2, 3)

    def _create_background_subtractor(self) -> cv2.BackgroundSubtractor:
        return cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=True,
        )

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def warmup_count(self) -> int:
        return self._warmup_count

    @property
    def last_detection_time(self) -> float:
        return self._last_detection_time

    @property
    def is_warmed_up(self) -> bool:
        return self._is_warmed_up

    @property
    def sensitivity(self) -> float:
        return self._sensitivity

    @property
    def min_area(self) -> float:
        return self._min_area
