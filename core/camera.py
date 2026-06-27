from __future__ import annotations

from typing import Any, Optional


class Camera:
    def __init__(
        self,
        index: Any = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 15,
        warmup_frames: int = 30,
        backend: str = "v4l2",
    ) -> None:
        self.index = index
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.warmup_frames = int(warmup_frames)
        self.backend = backend
        self._cap: Optional[object] = None

    def open(self) -> bool:
        try:
            import cv2
        except ImportError:
            return False

        self.close()

        if self.backend == "v4l2" and hasattr(cv2, "CAP_V4L2"):
            cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(self.index)

        if cap is None or not cap.isOpened():
            self._cap = None
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        for _ in range(max(0, self.warmup_frames)):
            cap.read()

        self._cap = cap
        return True

    def read(self):
        if self._cap is None:
            return None

        ok, frame = self._cap.read()
        if not ok:
            return None
        return frame

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
