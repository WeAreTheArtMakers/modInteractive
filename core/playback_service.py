"""Video playback service with mpv and fade transitions.

Handles hardware-accelerated video playback with GPU shader-based fade transitions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.event_bus import Event, EventBus, EventPriority, SystemEvents

logger = logging.getLogger(__name__)


class PlaybackService:
    """Video playback service using mpv for hardware-accelerated rendering.

    Manages fade-in/out transitions, playlist engine, and playback controls.
    """

    def __init__(
        self,
        event_bus: EventBus,
        fade_in_duration: float = 1.0,
        fade_out_duration: float = 1.0,
        volume: int = 80,
        fullscreen: bool = True,
        playback_mode: str = "random",
        loop_videos: bool = False,
    ) -> None:
        """Initialize playback service.

        Args:
            event_bus: System event bus
            fade_in_duration: Fade-in transition duration in seconds
            fade_out_duration: Fade-out transition duration in seconds
            volume: Audio volume (0-100)
            fullscreen: Play video in fullscreen mode
            playback_mode: Playback mode (random, sequential, single)
            loop_videos: Loop individual videos
        """
        self._event_bus = event_bus
        self._fade_in_duration = fade_in_duration
        self._fade_out_duration = fade_out_duration
        self._volume = volume
        self._fullscreen = fullscreen
        self._playback_mode = playback_mode
        self._loop_videos = loop_videos

        self._mpv_process: Optional[subprocess.Popen[bytes]] = None
        self._running = False
        self._playing = False
        self._playlist: List[str] = []
        self._current_video: Optional[str] = None
        self._current_index: int = -1
        self._monitor_task: Optional[asyncio.Task[None]] = None
        self._fade_script_path: Optional[Path] = None

    async def start(self) -> bool:
        """Start playback service.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_playback())

        # Create fade transition lua script
        self._fade_script_path = await self._create_fade_script()

        logger.info(
            f"Playback service started (mode: {self._playback_mode}, "
            f"fade_in: {self._fade_in_duration}s, fade_out: {self._fade_out_duration}s)"
        )
        return True

    async def stop(self) -> None:
        """Stop playback service."""
        self._running = False
        await self.stop_playback()
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Playback service stopped")

    def set_playlist(self, videos: List[str]) -> None:
        """Set video playlist.

        Args:
            videos: List of video file paths
        """
        self._playlist = [v for v in videos if os.path.exists(v)]
        self._current_index = -1 if not self._playlist else 0
        logger.info(f"Playlist updated: {len(self._playlist)} videos")

    def add_to_playlist(self, video_path: str) -> bool:
        """Add video to playlist.

        Args:
            video_path: Path to video file

        Returns:
            True if added successfully
        """
        if os.path.exists(video_path):
            self._playlist.append(video_path)
            if self._current_index == -1:
                self._current_index = 0
            logger.info(f"Added to playlist: {video_path}")
            return True
        logger.warning(f"Video not found: {video_path}")
        return False

    def remove_from_playlist(self, index: int) -> bool:
        """Remove video from playlist.

        Args:
            index: Playlist index

        Returns:
            True if removed successfully
        """
        if 0 <= index < len(self._playlist):
            removed = self._playlist.pop(index)
            if index <= self._current_index:
                self._current_index = max(0, self._current_index - 1)
            logger.info(f"Removed from playlist: {removed}")
            return True
        return False

    def get_playlist(self) -> List[Dict[str, Any]]:
        """Get current playlist with metadata.

        Returns:
            List of video info dictionaries
        """
        playlist = []
        for i, path in enumerate(self._playlist):
            p = Path(path)
            playlist.append({
                "index": i,
                "path": path,
                "filename": p.name,
                "size": p.stat().st_size if p.exists() else 0,
                "is_current": i == self._current_index,
            })
        return playlist

    async def play_video(self, video_path: Optional[str] = None) -> bool:
        """Play a video with fade-in transition.

        Args:
            video_path: Path to video file (None for next in playlist)

        Returns:
            True if playback started
        """
        if video_path:
            if not os.path.exists(video_path):
                logger.error(f"Video not found: {video_path}")
                return False
        else:
            video_path = self._next_video()
            if not video_path:
                logger.warning("No videos in playlist")
                return False

        # Stop current playback
        await self.stop_playback()

        try:
            mpv_args = [
                "mpv",
                "--no-terminal",
                "--really-quiet",
                "--no-osc",
                "--no-osd-bar",
                "--no-border",
                f"--volume={self._volume}",
                f"--start={self._fade_in_duration}",
            ]

            if self._fullscreen:
                mpv_args.extend(["--fs", "--fs-screen=0"])

            if self._loop_videos:
                mpv_args.append("--loop-file=inf")

            # Add fade shader
            if self._fade_script_path and self._fade_script_path.exists():
                mpv_args.append(f"--script={self._fade_script_path}")

            mpv_args.append(video_path)

            self._mpv_process = subprocess.Popen(
                mpv_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )

            self._current_video = video_path
            self._playing = True

            # Emit fade-in started
            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.FADE_IN_STARTED,
                    source="playback_service",
                    data={"video": video_path},
                    priority=EventPriority.HIGH,
                )
            )

            logger.info(f"Playback started: {video_path}")

            # Wait for fade-in duration then emit playback started
            asyncio.create_task(self._emit_playback_started())

            return True

        except FileNotFoundError:
            logger.error("mpv not found. Install with: sudo apt install mpv")
            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.PLAYBACK_ERROR,
                    source="playback_service",
                    data={"error": "mpv not found"},
                    priority=EventPriority.CRITICAL,
                )
            )
            return False
        except Exception as e:
            logger.error(f"Playback start error: {e}")
            return False

    async def stop_playback(self) -> None:
        """Stop current video playback with fade-out."""
        if self._mpv_process and self._playing:
            # Emit fade-out started
            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.FADE_OUT_STARTED,
                    source="playback_service",
                    data={"video": self._current_video},
                    priority=EventPriority.HIGH,
                )
            )

            # Send quit to mpv process
            try:
                self._mpv_process.send_signal(signal.SIGTERM)
                self._mpv_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._mpv_process.kill()
            except Exception:
                pass

            self._mpv_process = None
            self._playing = False
            self._current_video = None

            # Emit fade-out completed
            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.FADE_OUT_COMPLETED,
                    source="playback_service",
                    data={},
                    priority=EventPriority.HIGH,
                )
            )

            logger.info("Playback stopped")

    @property
    def is_playing(self) -> bool:
        """Check if video is currently playing."""
        if self._mpv_process:
            return self._mpv_process.poll() is None
        return False

    @property
    def current_video(self) -> Optional[str]:
        """Get current video path."""
        return self._current_video

    def set_volume(self, volume: int) -> None:
        """Set playback volume.

        Args:
            volume: Volume level (0-100)
        """
        self._volume = max(0, min(100, volume))

    def set_fade_duration(self, fade_in: float, fade_out: float) -> None:
        """Set fade transition durations.

        Args:
            fade_in: Fade-in duration in seconds
            fade_out: Fade-out duration in seconds
        """
        self._fade_in_duration = max(0.0, fade_in)
        self._fade_out_duration = max(0.0, fade_out)

    def _next_video(self) -> Optional[str]:
        """Get next video from playlist.

        Returns:
            Path to next video or None
        """
        if not self._playlist:
            return None

        if self._playback_mode == "random":
            return random.choice(self._playlist)
        elif self._playback_mode == "sequential":
            self._current_index = (self._current_index + 1) % len(self._playlist)
            return self._playlist[self._current_index]
        else:  # single
            return self._playlist[0] if self._playlist else None

    async def _emit_playback_started(self) -> None:
        """Emit playback started event after fade-in."""
        await asyncio.sleep(self._fade_in_duration)
        await self._event_bus.publish(
            Event(
                event_type=SystemEvents.PLAYBACK_STARTED,
                source="playback_service",
                data={"video": self._current_video},
                priority=EventPriority.HIGH,
            )
        )

    async def _monitor_playback(self) -> None:
        """Monitor mpv process and detect playback completion."""
        while self._running:
            try:
                if self._mpv_process and self._playing:
                    ret = self._mpv_process.poll()
                    if ret is not None:
                        # Playback completed
                        self._playing = False
                        self._mpv_process = None

                        await self._event_bus.publish(
                            Event(
                                event_type=SystemEvents.PLAYBACK_COMPLETED,
                                source="playback_service",
                                data={
                                    "video": self._current_video,
                                    "exit_code": ret,
                                },
                                priority=EventPriority.HIGH,
                            )
                        )

                        # Handle fade-out completion
                        await asyncio.sleep(self._fade_out_duration)
                        await self._event_bus.publish(
                            Event(
                                event_type=SystemEvents.FADE_OUT_COMPLETED,
                                source="playback_service",
                                data={},
                                priority=EventPriority.HIGH,
                            )
                        )

                        logger.info(f"Playback completed: {self._current_video}")
                        self._current_video = None

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Playback monitor error: {e}")
                await asyncio.sleep(1)

    async def _create_fade_script(self) -> Optional[Path]:
        """Create mpv lua script for fade transitions.

        Returns:
            Path to the created script
        """
        try:
            script_dir = Path("assets/scripts")
            script_dir.mkdir(parents=True, exist_ok=True)
            script_path = script_dir / "fade_transitions.lua"

            script_content = f"""-- modInteractive fade transitions script
local fade_in_duration = {self._fade_in_duration}
local fade_out_duration = {self._fade_out_duration}

function fade_in()
    local steps = math.floor(fade_in_duration * 30)
    for i = 1, steps do
        local alpha = i / steps
        mp.set_property_number("alpha", alpha)
        mp.commandv("no-osd", "set", "volume", tostring(alpha * 100))
        mp.add_timeout(fade_in_duration / steps, function() end)
    end
end

function fade_out()
    local steps = math.floor(fade_out_duration * 30)
    for i = steps, 0, -1 do
        local alpha = i / steps
        mp.set_property_number("alpha", alpha)
        mp.commandv("no-osd", "set", "volume", tostring(alpha * 100))
        mp.add_timeout(fade_out_duration / steps, function() end)
    end
end

mp.add_key_binding("Ctrl+f", "fade-in", fade_in)
mp.add_key_binding("Ctrl+g", "fade-out", fade_out)
mp.register_event("file-loaded", fade_in)
"""

            script_path.write_text(script_content)
            logger.info(f"Fade transition script created: {script_path}")
            return script_path

        except Exception as e:
            logger.error(f"Failed to create fade script: {e}")
            return None
