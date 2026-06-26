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
            retention_days=self._config_service.get("system.log_retention_days", 30),
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
            reconnect_interval=camera_config.get("reconnect_interval", 2),
        )

        # Initialize detection service
        detection_config = self._config_service.get("detection", {})
        self._detection_service = DetectionService(
            event_bus=self._event_bus,
            confidence_threshold=detection_config.get("confidence_threshold", 0.65),
            motion_sensitivity=detection_config.get("motion_sensitivity", 0.02),
            frame_skip=detection_config.get("frame_skip", 2),
            model_path=detection_config.get("model_path", "models/yolov8n.pt"),
        )

        # Initialize playback service
        video_config = self._config_service.get("video", {})
        self._playback_service = PlaybackService(
            event_bus=self._event_bus,
            fade_in_duration=video_config.get("fade_in_duration", 1.0),
            fade_out_duration=video_config.get("fade_out_duration", 1.0),
            volume=video_config.get("volume", 80),
            fullscreen=video_config.get("fullscreen", True),
            playback_mode=video_config.get("playback_mode", "random"),
            loop_videos=video_config.get("loop_videos", False),
        )

        # Initialize watchdog
        watchdog_timeout = self._config_service.get("system.watchdog_timeout", 10)
        self._watchdog = SystemWatchdog(
            event_bus=self._event_bus,
            timeout=watchdog_timeout,
        )

        # Subscribe system event handlers
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
        try:
            from ui.main_window import MainWindow
            self._ui = MainWindow(
                event_bus=self._event_bus,
                state_machine=self._state_machine,
                config_service=self._config_service,
            )
            self._ui.show()
        except ImportError as e:
            logger.warning(f"UI not available (running headless): {e}")
        except Exception as e:
            logger.error(f"UI initialization failed: {e}")

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

        # Log all events
        self._event_bus.subscribe_all(self._on_any_event)

    async def _on_any_event(self, event: Event) -> None:
        """Handle any event for logging purposes.

        Args:
            event: Any system event
        """
        if self._logging_service:
            await self._logging_service.log_event(event)
        
        # Forward to state machine
        await self._state_machine.handle_event(event)

    async def _on_person_confirmed(self, event: Event) -> None:
        """Handle person confirmed event.

        Args:
            event: Person confirmed event
        """
        if time.time() < self._cooldown_until:
            logger.debug("Cooldown active, ignoring detection")
            return

        # Check if video playlist has content
        playlist = self._playback_service.get_playlist()
        if not playlist:
            logger.warning("No videos in playlist, cannot trigger playback")
            return

        logger.info(f"Person confirmed, triggering video playback")

        # Play a random video
        await self._playback_service.play_video()

    async def _on_playback_completed(self, event: Event) -> None:
        """Handle playback completed event.

        Args:
            event: Playback completed event
        """
        cooldown = self._config_service.get("detection.cooldown_seconds", 10)
        self._cooldown_until = time.time() + cooldown
        logger.info(f"Cooldown active for {cooldown}s")

    async def _on_system_error(self, event: Event) -> None:
        """Handle system error events.

        Args:
            event: Error event
        """
        if self._logging_service:
            await self._logging_service.log_error(
                error_type="SYSTEM_ERROR",
                message=str(event.data.get("error", "Unknown error")),
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
                detection_config.get("confidence_threshold", 0.65)
            )
            self._detection_service.set_motion_sensitivity(
                detection_config.get("motion_sensitivity", 0.02)
            )

        # Apply video config changes
        video_config = new_config.get("video", {})
        if video_config:
            self._playback_service.set_volume(video_config.get("volume", 80))
            self._playback_service.set_fade_duration(
                video_config.get("fade_in_duration", 1.0),
                video_config.get("fade_out_duration", 1.0),
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
            # Ensure camera is running in idle
            if not self._camera_service.is_connected:
                await self._camera_service.restart()
        elif new_state == SystemState.ERROR:
            logger.error("System entered error state")
            # Attempt auto-recovery after delay
            asyncio.create_task(self._auto_recovery())

    async def _auto_recovery(self) -> None:
        """Attempt automatic recovery from error state."""
        await asyncio.sleep(5)
        if self._state_machine.current_state == SystemState.ERROR:
            logger.info("Attempting auto-recovery...")
            await self._state_machine.transition_to(SystemState.IDLE)
            await self._camera_service.restart()
            logger.info("Auto-recovery completed")