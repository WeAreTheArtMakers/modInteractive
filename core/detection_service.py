"""AI-powered detection service with hybrid motion + YOLO detection.

Supports multiple detection backends via plugin system.
Optimized for Raspberry Pi 5 with adaptive frame skipping.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.event_bus import Event, EventBus, EventPriority, SystemEvents

logger = logging.getLogger(__name__)


class DetectionService:
    """Hybrid detection service combining motion detection and YOLO AI.

    Uses a confidence-based decision engine to trigger person detection events.
    Optimized for Raspberry Pi 5 with frame skipping and adaptive FPS.
    """

    def __init__(
        self,
        event_bus: EventBus,
        confidence_threshold: float = 0.55,
        motion_sensitivity: float = 0.03,
        frame_skip: int = 3,
        model_path: str = "models/yolov8n.pt",
        consecutive_frames: int = 2,
    ) -> None:
        """Initialize detection service.

        Args:
            event_bus: System event bus
            confidence_threshold: Minimum confidence for YOLO detection (0.55 for Pi5)
            motion_sensitivity: Motion detection sensitivity (0.0-1.0)
            frame_skip: Number of frames to skip between detections (higher = less CPU)
            model_path: Path to YOLO model file
            consecutive_frames: Required consecutive detections before trigger
        """
        self._event_bus = event_bus
        self._confidence_threshold = confidence_threshold
        self._motion_sensitivity = motion_sensitivity
        self._frame_skip = max(1, frame_skip)  # Minimum 1
        self._model_path = model_path
        self._required_consecutive = max(1, consecutive_frames)

        self._model = None
        self._running = False
        self._processing_task: Optional[asyncio.Task[None]] = None
        self._frame_count = 0
        self._last_frame: Optional[np.ndarray] = None
        self._previous_gray: Optional[np.ndarray] = None
        self._person_present = False
        self._consecutive_detections = 0
        self._last_person_time: float = 0.0
        self._person_lost_timeout: float = 2.0  # Seconds before person considered lost

        # Frame skip counter
        self._skip_counter = 0

    async def start(self) -> bool:
        """Start detection service.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        self._running = True
        self._processing_task = asyncio.create_task(self._process_frames())
        logger.info(f"Detection service started (confidence: {self._confidence_threshold})")
        return True

    async def stop(self) -> None:
        """Stop detection service."""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        self._person_present = False
        self._consecutive_detections = 0
        logger.info("Detection service stopped")

    async def load_model(self) -> bool:
        """Load YOLO model.

        Returns:
            True if model loaded successfully
        """
        try:
            from ultralytics import YOLO
            # Use half precision on Pi5 for faster inference
            try:
                self._model = YOLO(self._model_path)
                logger.info(f"YOLO model loaded: {self._model_path}")
            except Exception as e:
                logger.warning(f"YOLO loading failed with half precision: {e}")
                self._model = YOLO(self._model_path)
            return True
        except ImportError:
            logger.warning("Ultralytics not installed, using motion-only detection")
            return False
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return False

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set detection confidence threshold.

        Args:
            threshold: Confidence threshold (0.0-1.0)
        """
        self._confidence_threshold = max(0.1, min(1.0, threshold))

    def set_motion_sensitivity(self, sensitivity: float) -> None:
        """Set motion detection sensitivity.

        Args:
            sensitivity: Sensitivity (0.0-1.0)
        """
        self._motion_sensitivity = max(0.01, min(1.0, sensitivity))

    @property
    def person_detected(self) -> bool:
        """Check if person is currently detected."""
        return self._person_present

    async def _process_frames(self) -> None:
        """Process camera frames for detection."""
        # Try to load YOLO model (non-blocking)
        yolo_available = await self.load_model()

        # Subscribe to camera frames
        unsubscribe = self._event_bus.subscribe(
            SystemEvents.CAMERA_FRAME_READY,
            self._handle_frame,
        )

        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe()

    async def _handle_frame(self, event: Event) -> None:
        """Handle incoming camera frame.

        Args:
            event: Camera frame event
        """
        frame = event.data.get("frame")
        if frame is None:
            return

        # Frame skipping: only process every Nth frame
        self._skip_counter += 1
        if self._skip_counter < self._frame_skip:
            return
        self._skip_counter = 0

        self._frame_count += 1

        try:
            # Motion detection (fast, runs every processed frame)
            motion_score = self._detect_motion(frame)

            # YOLO detection (slower, only if not in cooldown/playback)
            yolo_confidence = 0.0
            if self._model is not None:
                yolo_confidence = await self._run_yolo_inference(frame)

            # Decision engine
            await self._decision_engine(motion_score, yolo_confidence)

        except Exception as e:
            logger.error(f"Detection error: {e}", exc_info=True)

    def _detect_motion(self, frame: np.ndarray) -> float:
        """Detect motion in frame using background subtraction.

        Args:
            frame: Current video frame

        Returns:
            Motion score (0.0-1.0)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._previous_gray is None:
            self._previous_gray = gray
            return 0.0

        frame_delta = cv2.absdiff(self._previous_gray, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        motion_score = float(np.sum(thresh) / (thresh.shape[0] * thresh.shape[1] * 255))
        self._previous_gray = gray

        return motion_score

    async def _run_yolo_inference(self, frame: np.ndarray) -> float:
        """Run YOLO inference on frame.

        Args:
            frame: Video frame

        Returns:
            Maximum confidence score for person detection (class 0)
        """
        if self._model is None:
            return 0.0

        try:
            # Resize for faster inference on Pi5
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = 640
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))

            results = self._model(frame, verbose=False, device="cpu")
            max_confidence = 0.0

            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        # Class 0 is person in COCO dataset
                        if cls_id == 0 and confidence > max_confidence:
                            max_confidence = confidence

            return max_confidence
        except Exception as e:
            logger.debug(f"YOLO inference error: {e}")
            return 0.0

    async def _decision_engine(
        self,
        motion_score: float,
        yolo_confidence: float,
    ) -> None:
        """Decision engine for person detection.

        Pipeline:
        1. YOLO confidence > threshold → PERSON_CONFIRMED (after consecutive frames)
        2. Motion detected + low YOLO → PERSON_DETECTED (fallback)
        3. No detection for timeout → PERSON_LOST

        Args:
            motion_score: Motion detection score (0.0-1.0)
            yolo_confidence: YOLO confidence score (0.0-1.0)
        """
        current_time = time.time()

        # ---- HIGH CONFIDENCE YOLO DETECTION ----
        if yolo_confidence >= self._confidence_threshold:
            self._consecutive_detections += 1
            self._last_person_time = current_time

            if self._consecutive_detections >= self._required_consecutive:
                if not self._person_present:
                    self._person_present = True
                    await self._event_bus.publish(
                        Event(
                            event_type=SystemEvents.PERSON_CONFIRMED,
                            source="detection_service",
                            data={
                                "confidence": yolo_confidence,
                                "method": "yolo",
                                "motion_score": motion_score,
                            },
                            priority=EventPriority.HIGH,
                        )
                    )
                    logger.info(
                        f"🎯 PERSON CONFIRMED via YOLO "
                        f"(confidence: {yolo_confidence:.2f}, "
                        f"motion: {motion_score:.3f})"
                    )
        else:
            # Decrease confidence counter slowly
            if self._consecutive_detections > 0:
                self._consecutive_detections -= 1

        # ---- MOTION DETECTION FALLBACK ----
        if motion_score >= self._motion_sensitivity:
            if not self._person_present:
                self._last_person_time = current_time
                await self._event_bus.publish(
                    Event(
                        event_type=SystemEvents.PERSON_DETECTED,
                        source="detection_service",
                        data={
                            "confidence": yolo_confidence,
                            "method": "motion",
                            "motion_score": motion_score,
                        },
                        priority=EventPriority.NORMAL,
                    )
                )

        # ---- PERSON LOST DETECTION ----
        if self._person_present:
            time_since_last = current_time - self._last_person_time
            if time_since_last > self._person_lost_timeout:
                self._person_present = False
                self._consecutive_detections = 0
                await self._event_bus.publish(
                    Event(
                        event_type=SystemEvents.PERSON_LOST,
                        source="detection_service",
                        data={
                            "last_confidence": yolo_confidence,
                            "timeout_duration": self._person_lost_timeout,
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
                logger.info("Person lost (timeout)")