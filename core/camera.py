from __future__ import annotations

import logging
import platform
import time
from typing import Optional, Union

import cv2
import numpy as np

logger = logging.getLogger("modInteractive.camera")

CameraIndex = Union[int, str]


class Camera:
    def __init__(
        self,
        index: CameraIndex = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 15,
        warmup_frames: int = 30,
        backend: str = "auto",
    ) -> None:
        self._index = index
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._fps = max(1, int(fps))
        self._warmup_frames = max(0, int(warmup_frames))
        self._backend = str(backend or "auto").lower().strip()
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_open = False
        self._frame_count = 0
        self._error_count = 0
        self._opened_at = 0.0
        self._actual_width = 0
        self._actual_height = 0
        self._actual_fps = 0.0

    def open(self) -> bool:
        if self._is_open and self._cap is not None and self._cap.isOpened():
            return True

        self.close()

        try:
            self._cap = self._create_capture()

            if self._cap is None or not self._cap.isOpened():
                logger.error("Cannot open camera: index=%s backend=%s", self._index, self._backend)
                self._cap = None
                self._is_open = False
                return False

            self._configure_capture()
            self._warmup()

            self._is_open = True
            self._frame_count = 0
            self._error_count = 0
            self._opened_at = time.time()
            self._actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._actual_fps = float(self._cap.get(cv2.CAP_PROP_FPS))

            logger.info(
                "Camera opened: index=%s backend=%s actual=%dx%d fps=%.1f",
                self._index,
                self._backend,
                self._actual_width,
                self._actual_height,
                self._actual_fps,
            )
            return True

        except Exception:
            logger.exception("Camera open error")
            self.close()
            return False

    def read(self) -> Optional[np.ndarray]:
        if not self._is_open or self._cap is None:
            return None

        try:
            ok, frame = self._cap.read()

            if not ok or frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                self._register_read_error()
                return None

            self._frame_count += 1
            self._error_count = 0
            return frame

        except Exception:
            self._register_read_error()
            logger.exception("Camera read error")
            return None

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                logger.debug("Camera release failed", exc_info=True)

        self._cap = None
        self._is_open = False

    def reopen(self, delay_seconds: float = 1.0) -> bool:
        self.close()

        if delay_seconds > 0:
            time.sleep(delay_seconds)

        return self.open()

    def _create_capture(self) -> cv2.VideoCapture:
        backend_id = self._backend_id()

        if backend_id is not None:
            return cv2.VideoCapture(self._index, backend_id)

        return cv2.VideoCapture(self._index)

    def _backend_id(self) -> Optional[int]:
        if self._backend == "v4l2":
            return cv2.CAP_V4L2

        if self._backend == "auto" and platform.system().lower() == "linux":
            return cv2.CAP_V4L2

        return None

    def _configure_capture(self) -> None:
        if self._cap is None:
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            logger.debug("Camera buffer size setting ignored", exc_info=True)

    def _warmup(self) -> None:
        if self._cap is None:
            return

        if self._warmup_frames <= 0:
            return

        logger.info("Camera warmup: discarding %d frames", self._warmup_frames)

        for _ in range(self._warmup_frames):
            self._cap.read()

    def _register_read_error(self) -> None:
        self._error_count += 1

        if self._error_count <= 3 or self._error_count % 30 == 0:
            logger.warning("Camera read failed (%d consecutive errors)", self._error_count)

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def index(self) -> CameraIndex:
        return self._index

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def actual_width(self) -> int:
        return self._actual_width

    @property
    def actual_height(self) -> int:
        return self._actual_height

    @property
    def actual_fps(self) -> float:
        return self._actual_fps

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def uptime_seconds(self) -> float:
        if not self._opened_at:
            return 0.0

        return max(0.0, time.time() - self._opened_at)
