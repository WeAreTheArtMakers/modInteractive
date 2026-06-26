"""Camera service for USB webcam management.

Handles camera input, auto-detection, reconnection, and frame processing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.event_bus import Event, EventBus, EventPriority, SystemEvents

logger = logging.getLogger(__name__)

FrameCallback = Callable[[np.ndarray], None]


class CameraService:
    """USB webcam management service.

    Handles camera auto-detection, frame capture, and reconnection.
    All frames are published via event bus.
    """

    def __init__(
        self,
        event_bus: EventBus,
        device_id: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 15,
        auto_reconnect: bool = True,
        reconnect_interval: int = 2,
    ) -> None:
        """Initialize camera service.

        Args:
            event_bus: System event bus
            device_id: Camera device ID
            width: Capture width in pixels
            height: Capture height in pixels
            fps: Target frames per second
            auto_reconnect: Enable auto-reconnection on disconnect
            reconnect_interval: Seconds between reconnection attempts
        """
        self._event_bus = event_bus
        self._device_id = device_id
        self._width = width
        self._height = height
        self._target_fps = fps
        self._auto_reconnect = auto_reconnect
        self._reconnect_interval = reconnect_interval

        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._capture_task: Optional[asyncio.Task[None]] = None
        self._connected = False
        self._frame_count = 0
        self._fps = 0.0
        self._last_frame_time = 0.0
        self._brightness: float = 0.0
        self._contrast: float = 0.0
        self._frame_lock = asyncio.Lock()

        # Available cameras cache
        self._available_cameras: List[Dict[str, Any]] = []

    async def start(self) -> bool:
        """Start camera service.

        Returns:
            True if camera started successfully
        """
        if self._running:
            return True

        self._running = True
        success = await self._connect()

        if success:
            self._capture_task = asyncio.create_task(self._capture_loop())
            logger.info(
                f"Camera service started: device={self._device_id}, "
                f"resolution={self._width}x{self._height}, fps={self._target_fps}"
            )
        else:
            logger.error("Camera service failed to start")

        return success

    async def stop(self) -> None:
        """Stop camera service."""
        self._running = False
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
        self._disconnect()
        logger.info("Camera service stopped")

    async def restart(self) -> bool:
        """Restart camera service.

        Returns:
            True if restart succeeded
        """
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    def set_resolution(self, width: int, height: int) -> None:
        """Set camera resolution.

        Args:
            width: New width in pixels
            height: New height in pixels
        """
        self._width = width
        self._height = height
        if self._cap:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def set_brightness(self, value: float) -> None:
        """Set camera brightness.

        Args:
            value: Brightness value (-100 to 100)
        """
        self._brightness = max(-100.0, min(100.0, value))
        if self._cap:
            self._cap.set(cv2.CAP_PROP_BRIGHTNESS, self._brightness)

    def set_contrast(self, value: float) -> None:
        """Set camera contrast.

        Args:
            value: Contrast value (-100 to 100)
        """
        self._contrast = max(-100.0, min(100.0, value))
        if self._cap:
            self._cap.set(cv2.CAP_PROP_CONTRAST, self._contrast)

    @property
    def is_connected(self) -> bool:
        """Check if camera is connected."""
        return self._connected

    @property
    def fps(self) -> float:
        """Get current FPS."""
        return self._fps

    @property
    def frame_count(self) -> int:
        """Get total frame count."""
        return self._frame_count

    @property
    def resolution(self) -> Tuple[int, int]:
        """Get current resolution."""
        return (self._width, self._height)

    def scan_cameras(self, max_devices: int = 10) -> List[Dict[str, Any]]:
        """Scan for available USB cameras.

        Args:
            max_devices: Maximum number of devices to check

        Returns:
            List of available camera info dictionaries
        """
        cameras = []
        for device_id in range(max_devices):
            try:
                cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
                if cap.isOpened():
                    info = {
                        "device_id": device_id,
                        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                        "fps": cap.get(cv2.CAP_PROP_FPS),
                    }
                    cameras.append(info)
                    cap.release()
            except Exception:
                continue
        self._available_cameras = cameras
        return cameras

    async def _connect(self) -> bool:
        """Connect to camera device.

        Returns:
            True if connection succeeded
        """
        try:
            if self._cap:
                self._cap.release()

            self._cap = cv2.VideoCapture(self._device_id, cv2.CAP_V4L2)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self._device_id)
                if not self._cap.isOpened():
                    raise RuntimeError(f"Failed to open camera {self._device_id}")

            # Set resolution
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS, self._target_fps)

            # Set buffer size to minimum for low latency
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Apply brightness/contrast
            if self._brightness != 0:
                self._cap.set(cv2.CAP_PROP_BRIGHTNESS, self._brightness)
            if self._contrast != 0:
                self._cap.set(cv2.CAP_PROP_CONTRAST, self._contrast)

            self._connected = True
            self._frame_count = 0

            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.CAMERA_CONNECTED,
                    source="camera_service",
                    data={
                        "device_id": self._device_id,
                        "width": self._width,
                        "height": self._height,
                    },
                    priority=EventPriority.HIGH,
                )
            )
            return True

        except Exception as e:
            logger.error(f"Camera connection failed: {e}")
            self._connected = False
            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.CAMERA_ERROR,
                    source="camera_service",
                    data={"error": str(e), "device_id": self._device_id},
                    priority=EventPriority.HIGH,
                )
            )
            return False

    def _disconnect(self) -> None:
        """Disconnect from camera."""
        if self._cap:
            self._cap.release()
            self._cap = None
        self._connected = False

    async def _capture_loop(self) -> None:
        """Main frame capture loop."""
        frame_interval = 1.0 / self._target_fps
        last_frame_time = 0.0

        while self._running:
            try:
                if not self._connected:
                    if self._auto_reconnect:
                        logger.info("Attempting camera reconnection...")
                        success = await self._connect()
                        if success:
                            continue
                        await asyncio.sleep(self._reconnect_interval)
                        continue
                    await asyncio.sleep(0.1)
                    continue

                ret, frame = self._cap.read()
                if not ret or frame is None:
                    logger.warning("Camera frame read failed")
                    self._connected = False
                    await self._event_bus.publish(
                        Event(
                            event_type=SystemEvents.CAMERA_DISCONNECTED,
                            source="camera_service",
                            data={"device_id": self._device_id},
                            priority=EventPriority.HIGH,
                        )
                    )
                    continue

                self._frame_count += 1

                # Calculate FPS
                now = time.time()
                if self._last_frame_time > 0:
                    self._fps = 1.0 / (now - self._last_frame_time)
                self._last_frame_time = now

                # Publish frame via event bus
                await self._event_bus.publish(
                    Event(
                        event_type=SystemEvents.CAMERA_FRAME_READY,
                        source="camera_service",
                        data={
                            "frame": frame,
                            "frame_id": self._frame_count,
                            "fps": self._fps,
                            "timestamp": now,
                            "width": frame.shape[1],
                            "height": frame.shape[0],
                        },
                        priority=EventPriority.LOW,
                    )
                )

                # Throttle to target FPS
                elapsed = time.time() - now
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Capture loop error: {e}", exc_info=True)
                await self._event_bus.publish(
                    Event(
                        event_type=SystemEvents.CAMERA_ERROR,
                        source="camera_service",
                        data={"error": str(e)},
                        priority=EventPriority.HIGH,
                    )
                )
                await asyncio.sleep(1)
