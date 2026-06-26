"""Tests for CameraService."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
from core.camera_service import CameraService


class TestCameraService(unittest.IsolatedAsyncioTestCase):
    """Test suite for CameraService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_event_bus = MagicMock()
        self.mock_event_bus.start = AsyncMock()
        self.mock_event_bus.stop = AsyncMock()
        self.mock_event_bus.publish = AsyncMock()
        self.mock_event_bus.subscribe = MagicMock(return_value=lambda: None)

        self.service = CameraService(
            event_bus=self.mock_event_bus,
            device_id=0,
            width=640,
            height=480,
            fps=30,
            auto_reconnect=True,
            reconnect_interval=1,
        )

    def tearDown(self):
        """Clean up after test."""
        self.service._cap = None
        self.service._connected = False
        self.service._running = False

    @patch("cv2.VideoCapture")
    async def test_start_stop(self, mock_video_capture):
        """Test starting and stopping the camera service."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.read.return_value = (
            True,
            np.zeros((480, 640, 3), dtype=np.uint8),
        )
        mock_video_capture.return_value = mock_cap_instance

        # Start service
        result = await self.service.start()
        self.assertTrue(result)
        self.assertTrue(self.service._running)
        self.assertTrue(self.service.is_connected)

        # Verify event bus was called for camera connected
        self.mock_event_bus.publish.assert_called_once()
        call_args = self.mock_event_bus.publish.call_args[0][0]
        self.assertEqual(call_args.source, "camera_service")

        # Stop service
        await self.service.stop()
        self.assertFalse(self.service._running)
        self.assertFalse(self.service.is_connected)

    @patch("cv2.VideoCapture")
    async def test_scan_cameras(self, mock_video_capture):
        """Test scanning for available cameras."""
        # Mock that devices 0 and 2 are available, 1 is not
        mock_caps = {}

        for dev_id in [0, 2]:
            cap_mock = MagicMock()
            cap_mock.isOpened.return_value = True
            cap_mock.get.side_effect = lambda prop: {
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_FPS: 30.0,
            }.get(prop, 0.0)
            mock_caps[dev_id] = cap_mock

        cap_not_opened = MagicMock()
        cap_not_opened.isOpened.return_value = False
        mock_caps[1] = cap_not_opened

        def video_capture_side_effect(device_id, *args, **kwargs):
            return mock_caps.get(device_id, cap_not_opened)

        mock_video_capture.side_effect = video_capture_side_effect

        cameras = self.service.scan_cameras(max_devices=5)
        self.assertEqual(len(cameras), 2)
        self.assertEqual(cameras[0]["device_id"], 0)
        self.assertEqual(cameras[1]["device_id"], 2)
        self.assertEqual(cameras[0]["width"], 640)
        self.assertEqual(cameras[0]["height"], 480)

    @patch("cv2.VideoCapture")
    async def test_set_resolution(self, mock_video_capture):
        """Test setting camera resolution."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_video_capture.return_value = mock_cap_instance

        await self.service.start()

        self.service.set_resolution(1280, 720)
        self.assertEqual(self.service._width, 1280)
        self.assertEqual(self.service._height, 720)

        mock_cap_instance.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        mock_cap_instance.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        await self.service.stop()

    @patch("cv2.VideoCapture")
    async def test_connect_failure_retries(self, mock_video_capture):
        """Test that camera service handles connection failures."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = False
        mock_video_capture.return_value = mock_cap_instance

        result = await self.service.start()
        self.assertFalse(result)
        self.assertFalse(self.service.is_connected)

    @patch("cv2.VideoCapture")
    async def test_frame_capture_and_publish(self, mock_video_capture):
        """Test that frames are captured and published via event bus."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        frame_data = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        mock_cap_instance.read.return_value = (True, frame_data)
        mock_video_capture.return_value = mock_cap_instance

        await self.service.start()

        # Allow capture loop to run briefly
        await asyncio.sleep(0.05)

        # Check that frames were published
        self.assertGreater(self.service._frame_count, 0)
        self.assertGreater(self.service.fps, 0)

        await self.service.stop()

    @patch("cv2.VideoCapture")
    async def test_brightness_contrast(self, mock_video_capture):
        """Test brightness and contrast settings."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_video_capture.return_value = mock_cap_instance

        await self.service.start()

        self.service.set_brightness(50)
        self.assertEqual(self.service._brightness, 50.0)
        mock_cap_instance.set.assert_any_call(cv2.CAP_PROP_BRIGHTNESS, 50.0)

        self.service.set_contrast(-30)
        self.assertEqual(self.service._contrast, -30.0)
        mock_cap_instance.set.assert_any_call(cv2.CAP_PROP_CONTRAST, -30.0)

        # Test clamping
        self.service.set_brightness(200)
        self.assertEqual(self.service._brightness, 100.0)

        self.service.set_brightness(-200)
        self.assertEqual(self.service._brightness, -100.0)

        await self.service.stop()


if __name__ == "__main__":
    unittest.main()
