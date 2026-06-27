from __future__ import annotations

from typing import Any, Dict, Tuple


class Detector:
    def __init__(self, sensitivity: int = 500, min_area: int = 1500, warmup_frames: int = 30) -> None:
        self.sensitivity = int(sensitivity)
        self.min_area = int(min_area)
        self.warmup_frames = int(warmup_frames)
        self._background = None
        self._frames = 0

    def set_sensitivity(self, sensitivity: int) -> None:
        self.sensitivity = int(sensitivity)

    def set_min_area(self, min_area: int) -> None:
        self.min_area = int(min_area)

    def detect(self, frame: Any) -> Tuple[bool, float, int, Dict[str, Any]]:
        import cv2
        import numpy as np

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._background is None:
            self._background = gray.astype("float")
            self._frames = 1
            return False, 0.0, 0, {"warmup": True, "max_contour_area": 0}

        cv2.accumulateWeighted(gray, self._background, 0.05)
        self._frames += 1

        if self._frames <= self.warmup_frames:
            return False, 0.0, 0, {"warmup": True, "max_contour_area": 0}

        delta = cv2.absdiff(gray, cv2.convertScaleAbs(self._background))
        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_area = 0.0

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area > max_area:
                max_area = area

        pixels = int(np.count_nonzero(thresh))
        detected = max_area >= self.min_area or pixels >= self.sensitivity
        confidence = min(1.0, max(max_area / max(1, self.min_area), pixels / max(1, self.sensitivity)))

        return detected, float(confidence), pixels, {"max_contour_area": max_area}
