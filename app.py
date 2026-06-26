"""Application controller for modInteractive.

Core application that initializes all services and manages the event-driven system.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.event_bus import Event, EventBus, EventPriority, SystemEvents
from core.state_machine import StateMachine, SystemState
from core.config_service import ConfigService
from core.logging_service import LoggingService
from core.camera_service import CameraService
from core.detection_service import DetectionService
from core.playback_service import PlaybackService
from core.watchdog import SystemWatchdog
from core.plugin_base import PluginManager

logger = logging.getLogger(__name__)


class Application:
    """Main application controller.

    Initializes all services, wires them together via event bus,
    and manages the system lifecycle.
    """

    def __init__(self, config_path: str = "config.json") -> None:
        """Initialize application.

        Args:
            config_path: Path to configuration file
        """
        self._config_path = config_path
        self._running = False

        # Core event bus
        self._event_bus = EventBus()

        # State machine
        self._state_machine = StateMachine(
            event_bus=self._event_bus,
            on_state_change=self._on_state_change,
        )

        # Services
        self._config_service: Optional[ConfigService] = None
        self._logging_service: Optional[LoggingService] = None
        self._camera_service: Optional[CameraService] = None
        self._detection_service: Optional[DetectionService] = None
        self._playback_service: Optional[PlaybackService] = None
        self._watchdog: Optional[SystemWatchdog] = None
        self._plugin_manager: Optional[PluginManager] = None

        # UI
        self._ui = None

        # Background tasks
        self._tasks: List[asyncio.Task[None]] = []

        # Cooldown state
        self._cooldown_until: float = 0.0

    async def start(self) -> None:
        """Start the application and all services."""
        logger.info("Starting modInteractive...")

        # Initialize event bus first
        await self._event_bus.start()

        # Initialize config service
        self._config_service = ConfigService(
            event_bus=self._event_bus,
            config_path=self._config_path,
        )
        await self._config_service.start()

        # Initialize logging service
        self._logging_service = LoggingService(
            event_bus=self._event_bus,
            retention_days=self._config_service.get("system.log_retention_days", 7),
        )
        await self._logging_service.start()

        # Initialize plugin manager
        self._plugin_manager = PluginManager(
            event_bus=self._event_bus,
            plugin_paths=self._config_service.get("plugins.paths", []),
        )

        # Initialize camera service
        camera_config = self._config_service.get("camera", {})
        self._camera_service = CameraService(
            event_bus=self._event_bus,
            device_id=camera_config.get("device_id", 0),
            width=camera_config.get("resolution", {}).get("width", 640),
            height=camera_config.get("resolution", {}).get("height", 480),
            fps=camera_config.get("fps", 15),
            auto_reconnect=camera_config.get("auto_reconnect", True),
            reconnect_interval=camera_config.get("reconnect_interval", 3),
        )

        # Initialize detection service
        detection_config = self._config_service.get("detection", {})
        self._detection_service = DetectionService(
            event_bus=self._event_bus,
            confidence_threshold=detection_config.get("confidence_threshold", 0.55),
            motion_sensitivity=detection_config.get("motion_sensitivity", 0.03),
            frame_skip=detection_config.get("frame_skip", 3),
            model_path=detection_config.get("model_path", "models/yolov8n.pt"),
            consecutive_frames=detection_config.get("consecutive_frames", 2),
        )

        # Initialize playback service
        video_config = self._config_service.get("video", {})
        self._playback_service = PlaybackService(
            event_bus=self._event_bus,
            fade_in_duration=video_config.get("fade_in_duration", 0.8),
            fade_out_duration=video_config.get("fade_out_duration", 0.8),
            volume=video_config.get("volume", 90),
            fullscreen=video_config.get("fullscreen", True),
            playback_mode=video_config.get("playback_mode", "single"),
            loop_videos=video_config.get("loop_videos", False),
        )

        # Initialize watchdog
        watchdog_timeout = self._config_service.get("system.watchdog_timeout", 10)
        self._watchdog = SystemWatchdog(
            event_bus=self._event_bus,
            timeout=watchdog_timeout,
        )

        # Load video playlist from config
        playlist = video_config.get("playlist", [])
        if playlist:
            resolved_playlist = []
            for video_path in playlist:
                abs_path = os.path.abspath(video_path)
                if os.path.exists(abs_path):
                    resolved_playlist.append(abs_path)
                    logger.info(f"Video found: {abs_path}")
                elif os.path.exists(video_path):
                    resolved_playlist.append(video_path)
                    logger.info(f"Video found: {video_path}")
                else:
                    logger.warning(f"Video not found: {video_path}")
            
            if resolved_playlist:
                self._playback_service.set_playlist(resolved_playlist)
                logger.info(f"Playlist loaded: {len(resolved_playlist)} video(s)")
            else:
                logger.warning("No videos found in playlist configuration")

        # Subscribe system event handlers (BEFORE starting services)
        self._subscribe_events()

        # Start services
        await self._camera_service.start()
        await self._detection_service.start()
        await self._playback_service.start()
        await self._watchdog.start()

        # Load plugins
        await self._plugin_manager.discover_plugins()
        await self._plugin_manager.load_all_plugins()

        # Start UI if available
        ui_enabled = self._config_service.get("ui.headless", False) is False
        if ui_enabled:
            try:
                from ui.main_window import MainWindow
                self._ui = MainWindow(
                    event_bus=self._event_bus,
                    state_machine=self._state_machine,
                    config_service=self._config_service,
                )
                self._ui.show()
                logger.info("UI started successfully")
            except ImportError as e:
                logger.warning(f"UI not available (running headless): {e}")
            except Exception as e:
                logger.warning(f"UI initialization failed, running headless: {e}")

        # Transition to IDLE state
        await self._state_machine.transition_to(SystemState.IDLE)

        # System startup complete
        await self._event_bus.publish(
            Event(
                event_type=SystemEvents.SYSTEM_STARTUP,
                source="app",
                data={"status": "success"},
                priority=EventPriority.HIGH,
            )
        )

        self._running = True
        logger.info("modInteractive started successfully")

    async def stop(self) -> None:
        """Stop the application gracefully."""
        logger.info("Stopping modInteractive...")

        await self._event_bus.publish(
            Event(
                event_type=SystemEvents.SYSTEM_SHUTDOWN,
                source="app",
                data={"reason": "user_request"},
                priority=EventPriority.CRITICAL,
            )
        )

        # Stop services in reverse order
        if self._playback_service:
            await self._playback_service.stop()
        if self._detection_service:
            await self._detection_service.stop()
        if self._camera_service:
            await self._camera_service.stop()
        if self._watchdog:
            await self._watchdog.stop()
        if self._plugin_manager:
            await self._plugin_manager.shutdown_all()
        if self._logging_service:
            await self._logging_service.stop()
        if self._config_service:
            await self._config_service.stop()

        await self._event_bus.stop()
        self._running = False
        logger.info("modInteractive stopped")

    async def _subscribe_events(self) -> None:
        """Subscribe to system events."""
        # Detection events -> trigger playback
        self._event_bus.subscribe(
            SystemEvents.PERSON_CONFIRMED,
            self._on_person_confirmed,
        )

        # Playback events -> state transitions
        self._event_bus.subscribe(
            SystemEvents.PLAYBACK_COMPLETED,
            self._on_playback_completed,
        )

        # Camera events
        self._event_bus.subscribe(
            SystemEvents.CAMERA_ERROR,
            self._on_system_error,
        )

        # Config changes
        self._event_bus.subscribe(
            SystemEvents.CONFIG_CHANGED,
            self._on_config_changed,
        )

        # Log all events and forward to state machine
        self._event_bus.subscribe_all(self._on_any_event)

    async def _on_any_event(self, event: Event) -> None:
        """Handle any event for logging and state machine forwarding.

        Args:
            event: Any system event
        """
        if self._logging_service:
            await self._logging_service.log_event(event)
        
        # Forward to state machine
        await self._state_machine.handle_event(event)

    async def _on_person_confirmed(self, event: Event) -> None:
        """Handle person confirmed event - triggers video playback.

        Args:
            event: Person confirmed event
        """
        # Check cooldown
        if time.time() < self._cooldown_until:
            logger.debug(f"Cooldown active ({self._cooldown_until - time.time():.0f}s remaining)")
            return

        # Check if video playlist has content
        playlist = self._playback_service.get_playlist()
        if not playlist:
            logger.warning("No videos in playlist, cannot trigger playback")
            return

        confidence = event.data.get("confidence", 0.0)
        method = event.data.get("method", "unknown")
        logger.info(f"🎯 Person detected! Confidence={confidence:.2f}, Method={method}")

        # Trigger video playback
        success = await self._playback_service.play_video()
        if success:
            logger.info("▶️ Video playback triggered successfully")
        else:
            logger.error("❌ Video playback failed to start")

    async def _on_playback_completed(self, event: Event) -> None:
        """Handle playback completed event - activate cooldown.

        Args:
            event: Playback completed event
        """
        cooldown = self._config_service.get("detection.cooldown_seconds", 8)
        self._cooldown_until = time.time() + cooldown
        logger.info(f"⏳ Cooldown active for {cooldown}s")

    async def _on_system_error(self, event: Event) -> None:
        """Handle system error events.

        Args:
            event: Error event
        """
        error_msg = str(event.data.get("error", "Unknown error"))
        logger.error(f"System error from {event.source}: {error_msg}")
        if self._logging_service:
            await self._logging_service.log_error(
                error_type="SYSTEM_ERROR",
                message=error_msg,
                source=event.source,
            )

    async def _on_config_changed(self, event: Event) -> None:
        """Handle configuration changes.

        Args:
            event: Config changed event
        """
        new_config = event.data.get("new", {})
        logger.info("Configuration changed, applying updates")

        # Apply camera config changes
        camera_config = new_config.get("camera", {})
        if camera_config:
            resolution = camera_config.get("resolution", {})
            if resolution:
                self._camera_service.set_resolution(
                    resolution.get("width", 640),
                    resolution.get("height", 480),
                )

        # Apply detection config changes
        detection_config = new_config.get("detection", {})
        if detection_config:
            self._detection_service.set_confidence_threshold(
                detection_config.get("confidence_threshold", 0.55)
            )
            self._detection_service.set_motion_sensitivity(
                detection_config.get("motion_sensitivity", 0.03)
            )

        # Apply video config changes
        video_config = new_config.get("video", {})
        if video_config:
            self._playback_service.set_volume(video_config.get("volume", 90))
            self._playback_service.set_fade_duration(
                video_config.get("fade_in_duration", 0.8),
                video_config.get("fade_out_duration", 0.8),
            )

    async def _on_state_change(
        self,
        old_state: SystemState,
        new_state: SystemState,
    ) -> None:
        """Handle state machine state changes.

        Args:
            old_state: Previous state
            new_state: New state
        """
        logger.info(f"System state: {old_state.name} -> {new_state.name}")

        # Start/stop services based on state
        if new_state == SystemState.IDLE:
            if self._camera_service and not self._camera_service.is_connected:
                logger.info("Camera not connected in IDLE state, restarting...")
                await self._camera_service.restart()
        elif new_state == SystemState.ERROR:
            logger.error("System entered error state")
            asyncio.create_task(self._auto_recovery())

    async def _auto_recovery(self) -> None:
        """Attempt automatic recovery from error state."""
        logger.info("Auto-recovery in 5 seconds...")
        await asyncio.sleep(5)
        if self._state_machine.current_state == SystemState.ERROR:
            logger.info("Attempting auto-recovery...")
            await self._state_machine.transition_to(SystemState.IDLE)
            if self._camera_service:
                await self._camera_service.restart()
            logger.info("Auto-recovery completed")