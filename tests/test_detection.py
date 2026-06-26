"""Tests for DetectionService."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from core.detection_service import DetectionService


class TestDetectionService(unittest.IsolatedAsyncioTestCase):
    """Test suite for DetectionService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_event_bus = MagicMock()
        self.mock_event_bus.start = AsyncMock()
        self.mock_event_bus.stop = AsyncMock()
        self.mock_event_bus.publish = AsyncMock()
        self.mock_event_bus.subscribe = MagicMock(return_value=lambda: None)

        self.service = DetectionService(
            event_bus=self.mock_event_bus,
            confidence_threshold=0.65,
            motion_sensitivity=0.02,
            frame_skip=0,
            model_path="models/yolov8n.pt",
        )

    def tearDown(self):
        """Clean up after test."""
        self.service._model = None
        self.service._running = False
        self.service._person_present = False
        self.service._consecutive_detections = 0

    async def test_motion_detection(self):
        """Test motion detection with various frame inputs."""
        # Create two identical frames — no motion
        frame1 = np.ones((100, 100, 3), dtype=np.uint8) * 128
        frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 128

        score1 = self.service._detect_motion(frame1)
        self.assertEqual(score1, 0.0)

        score2 = self.service._detect_motion(frame2)
        self.assertAlmostEqual(score2, 0.0, delta=0.01)

        # Create frame with motion (different pixels)
        frame3 = np.zeros((100, 100, 3), dtype=np.uint8)
        frame3[40:60, 40:60] = 255

        score3 = self.service._detect_motion(frame3)
        # Motion should be detected
        self.assertGreater(score3, self.service._motion_sensitivity)

        # Create frame with no motion again
        frame4 = np.ones((100, 100, 3), dtype=np.uint8) * 128
        score4 = self.service._detect_motion(frame4)
        self.assertLess(score4, self.service._motion_sensitivity)

    async def test_decision_engine_high_confidence(self):
        """Test decision engine with high confidence YOLO detection."""
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # High confidence detection (above threshold)
        await self.service._decision_engine(
            motion_score=0.01,
            yolo_confidence=0.85,
            frame=frame,
        )
        # Should have triggered consecutive detection
        self.assertEqual(self.service._consecutive_detections, 1)

        # Multiple consecutive high confidence detections
        for _ in range(self.service._required_consecutive):
            await self.service._decision_engine(
                motion_score=0.01,
                yolo_confidence=0.85,
                frame=frame,
            )

        self.assertTrue(self.service._person_present)
        self.mock_event_bus.publish.assert_called_with(
            unittest.mock.ANY
        )
        # Verify PERSON_CONFIRMED was published
        calls = self.mock_event_bus.publish.call_args_list
        confirmed_events = [
            c for c in calls
            if c[0][0].source == "detection_service"
        ]
        self.assertGreater(len(confirmed_events), 0)

    async def test_decision_engine_low_confidence(self):
        """Test decision engine with low confidence YOLO detection."""
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # Low confidence detection with motion
        await self.service._decision_engine(
            motion_score=0.05,
            yolo_confidence=0.35,
            frame=frame,
        )

        # Should have triggered PERSON_DETECTED via motion fallback
        self.assertFalse(self.service._person_present)
        # Person is not yet confirmed (requires consecutive high conf)

        # Very low confidence, no motion — should not trigger
        self.service._consecutive_detections = 0
        self.service._person_present = False

        await self.service._decision_engine(
            motion_score=0.001,
            yolo_confidence=0.05,
            frame=frame,
        )

        self.assertFalse(self.service._person_present)
        self.assertEqual(self.service._consecutive_detections, 0)

    async def test_decision_engine_person_lost(self):
        """Test the person lost transition in decision engine."""
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # First establish person present
        self.service._person_present = True
        self.service._consecutive_detections = 3

        # Then drop confidence significantly with no motion
        await self.service._decision_engine(
            motion_score=0.001,
            yolo_confidence=0.1,
            frame=frame,
        )

        # Person should be lost
        self.assertFalse(self.service._person_present)
        self.assertEqual(self.service._consecutive_detections, 0)

    @patch("core.detection_service.YOLO")
    async def test_load_model_success(self, mock_yolo):
        """Test successful YOLO model loading."""
        mock_yolo_instance = MagicMock()
        mock_yolo.return_value = mock_yolo_instance

        result = await self.service.load_model()
        self.assertTrue(result)
        self.assertIsNotNone(self.service._model)

    async def test_load_model_ultralytics_not_available(self):
        """Test model loading when ultralytics is not installed."""
        # Simulate ImportError by temporarily removing YOLO from namespace
        with patch("core.detection_service.YOLO", side_effect=ImportError("No module")):
            result = await self.service.load_model()
            self.assertFalse(result)
            self.assertIsNone(self.service._model)

    async def test_set_confidence_threshold(self):
        """Test confidence threshold setter."""
        self.service.set_confidence_threshold(0.5)
        self.assertEqual(self.service._confidence_threshold, 0.5)

        # Test clamping
        self.service.set_confidence_threshold(-0.1)
        self.assertEqual(self.service._confidence_threshold, 0.0)

        self.service.set_confidence_threshold(1.5)
        self.assertEqual(self.service._confidence_threshold, 1.0)

    async def test_set_motion_sensitivity(self):
        """Test motion sensitivity setter."""
        self.service.set_motion_sensitivity(0.1)
        self.assertEqual(self.service._motion_sensitivity, 0.1)

        # Test clamping
        self.service.set_motion_sensitivity(0.0)
        self.assertEqual(self.service._motion_sensitivity, 0.01)

        self.service.set_motion_sensitivity(2.0)
        self.assertEqual(self.service._motion_sensitivity, 1.0)


if __name__ == "__main__":
    unittest.main()
