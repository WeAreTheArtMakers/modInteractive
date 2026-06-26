"""Tests for PlaybackService."""

import asyncio
import os
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.playback_service import PlaybackService


class TestPlaybackService(unittest.IsolatedAsyncioTestCase):
    """Test suite for PlaybackService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_event_bus = MagicMock()
        self.mock_event_bus.start = AsyncMock()
        self.mock_event_bus.stop = AsyncMock()
        self.mock_event_bus.publish = AsyncMock()
        self.mock_event_bus.subscribe = MagicMock(return_value=lambda: None)

        self.service = PlaybackService(
            event_bus=self.mock_event_bus,
            fade_in_duration=0.5,
            fade_out_duration=0.5,
            volume=80,
            fullscreen=False,
            playback_mode="random",
            loop_videos=False,
        )

        # Create a temporary video file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_video = os.path.join(self.temp_dir, "test_video.mp4")
        with open(self.test_video, "w") as f:
            f.write("fake video content")

    def tearDown(self):
        """Clean up after test."""
        self.service._mpv_process = None
        self.service._playing = False
        self.service._running = False
        self.service._playlist = []
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    async def test_start_stop(self):
        """Test starting and stopping the playback service."""
        result = await self.service.start()
        self.assertTrue(result)
        self.assertTrue(self.service._running)

        await self.service.stop()
        self.assertFalse(self.service._running)
        self.assertFalse(self.service._playing)

    async def test_add_to_playlist(self):
        """Test adding videos to the playlist."""
        # Add existing file
        result = self.service.add_to_playlist(self.test_video)
        self.assertTrue(result)
        self.assertEqual(len(self.service._playlist), 1)

        # Add non-existent file
        result = self.service.add_to_playlist("/nonexistent/video.mp4")
        self.assertFalse(result)
        self.assertEqual(len(self.service._playlist), 1)

    async def test_remove_from_playlist(self):
        """Test removing videos from the playlist."""
        self.service.add_to_playlist(self.test_video)
        self.service.add_to_playlist(self.test_video)
        self.assertEqual(len(self.service._playlist), 2)

        # Remove valid index
        result = self.service.remove_from_playlist(0)
        self.assertTrue(result)
        self.assertEqual(len(self.service._playlist), 1)

        # Remove invalid index
        result = self.service.remove_from_playlist(10)
        self.assertFalse(result)
        self.assertEqual(len(self.service._playlist), 1)

    async def test_get_playlist(self):
        """Test getting playlist metadata."""
        self.service.add_to_playlist(self.test_video)
        playlist = self.service.get_playlist()

        self.assertEqual(len(playlist), 1)
        self.assertEqual(playlist[0]["filename"], "test_video.mp4")
        self.assertEqual(playlist[0]["index"], 0)
        self.assertIn("size", playlist[0])
        self.assertIn("path", playlist[0])

    @patch("subprocess.Popen")
    async def test_play_video_success(self, mock_popen):
        """Test successful video playback."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process

        await self.service.start()
        self.service.add_to_playlist(self.test_video)

        result = await self.service.play_video()
        self.assertTrue(result)
        self.assertTrue(self.service._playing)

        # Verify mpv was started with correct args
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        self.assertIn("mpv", call_args)
        self.assertIn(self.test_video, call_args)
        self.assertIn("--volume=80", call_args)

        await self.service.stop()

    @patch("subprocess.Popen")
    async def test_stop_playback(self, mock_popen):
        """Test stopping video playback."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        await self.service.start()
        self.service.add_to_playlist(self.test_video)
        await self.service.play_video()

        # Stop playback
        await self.service.stop_playback()
        self.assertFalse(self.service._playing)
        self.assertIsNone(self.service._current_video)
        self.assertIsNone(self.service._mpv_process)

        # Verify SIGTERM was sent
        mock_process.send_signal.assert_called_with(signal.SIGTERM)

        await self.service.stop()

    @patch("subprocess.Popen")
    async def test_play_video_file_not_found(self, mock_popen):
        """Test playback with a non-existent video file."""
        await self.service.start()

        result = await self.service.play_video(video_path="/nonexistent/video.mp4")
        self.assertFalse(result)
        self.assertFalse(self.service._playing)
        # mpv should not have been called
        mock_popen.assert_not_called()

        await self.service.stop()

    @patch("subprocess.Popen")
    async def test_play_video_empty_playlist(self, mock_popen):
        """Test playback with empty playlist."""
        await self.service.start()

        # Try to play next video with empty playlist
        result = await self.service.play_video()
        self.assertFalse(result)
        self.assertFalse(self.service._playing)
        mock_popen.assert_not_called()

        await self.service.stop()

    async def test_set_volume(self):
        """Test volume setter."""
        self.service.set_volume(50)
        self.assertEqual(self.service._volume, 50)

        # Test clamping
        self.service.set_volume(-10)
        self.assertEqual(self.service._volume, 0)

        self.service.set_volume(150)
        self.assertEqual(self.service._volume, 100)

    async def test_set_fade_duration(self):
        """Test fade duration setter."""
        self.service.set_fade_duration(2.0, 3.0)
        self.assertEqual(self.service._fade_in_duration, 2.0)
        self.assertEqual(self.service._fade_out_duration, 3.0)

        # Test clamping to zero
        self.service.set_fade_duration(-1.0, -2.0)
        self.assertEqual(self.service._fade_in_duration, 0.0)
        self.assertEqual(self.service._fade_out_duration, 0.0)

    async def test_set_playlist(self):
        """Test setting the entire playlist."""
        # Create multiple test files
        videos = []
        for i in range(3):
            v = os.path.join(self.temp_dir, f"video_{i}.mp4")
            with open(v, "w") as f:
                f.write(f"content {i}")
            videos.append(v)

        # Add some non-existent paths too
        videos.append("/nonexistent.mp4")

        self.service.set_playlist(videos)
        self.assertEqual(len(self.service._playlist), 3)  # only existing files

    @patch("subprocess.Popen")
    async def test_is_playing(self, mock_popen):
        """Test is_playing property."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        await self.service.start()
        self.service.add_to_playlist(self.test_video)

        self.assertFalse(self.service.is_playing)
        await self.service.play_video()
        self.assertTrue(self.service.is_playing)

        await self.service.stop()

    async def test_sequential_playback_mode(self):
        """Test sequential playback mode."""
        self.service._playback_mode = "sequential"

        # Create test files
        videos = []
        for i in range(3):
            v = os.path.join(self.temp_dir, f"seq_{i}.mp4")
            with open(v, "w") as f:
                f.write(f"content {i}")
            videos.append(v)

        self.service.set_playlist(videos)
        self.service._current_index = -1

        # First call should return first video
        next_video = self.service._next_video()
        self.assertEqual(next_video, videos[0])
        self.assertEqual(self.service._current_index, 0)

        # Second call should return second video
        next_video = self.service._next_video()
        self.assertEqual(next_video, videos[1])
        self.assertEqual(self.service._current_index, 1)

        # Wrap around
        for _ in range(2):
            self.service._next_video()

        # Should wrap back to first
        self.assertEqual(self.service._current_index, 0)


if __name__ == "__main__":
    unittest.main()
