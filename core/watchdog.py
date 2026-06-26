"""System watchdog for modInteractive.

Monitors system health and auto-restarts if frozen for >10 seconds.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from typing import Optional

from core.event_bus import Event, EventBus, EventPriority, SystemEvents

logger = logging.getLogger(__name__)


class SystemWatchdog:
    """Watchdog service that monitors system health.

    Triggers auto-restart if system is frozen for more than timeout duration.
    Uses heartbeat mechanism with the event bus.
    """

    def __init__(
        self,
        event_bus: EventBus,
        timeout: float = 10.0,
        check_interval: float = 2.0,
    ) -> None:
        """Initialize watchdog.

        Args:
            event_bus: System event bus
            timeout: Maximum allowed freeze time in seconds
            check_interval: Health check interval in seconds
        """
        self._event_bus = event_bus
        self._timeout = timeout
        self._check_interval = check_interval

        self._last_heartbeat: float = time.time()
        self._running = False
        self._watchdog_task: Optional[asyncio.Task[None]] = None
        self._restart_requested = False

    async def start(self) -> None:
        """Start watchdog monitoring."""
        if self._running:
            return

        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())

        # Register heartbeat on event bus activity
        self._event_bus.subscribe_all(self._heartbeat_handler)

        logger.info(
            f"Watchdog started (timeout: {self._timeout}s, "
            f"check_interval: {self._check_interval}s)"
        )

    async def stop(self) -> None:
        """Stop watchdog monitoring."""
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        logger.info("Watchdog stopped")

    def heartbeat(self) -> None:
        """Manually trigger heartbeat to indicate system is alive."""
        self._last_heartbeat = time.time()

    async def _heartbeat_handler(self, event: Event) -> None:
        """Handle any event as a heartbeat signal.

        Args:
            event: Any system event
        """
        self._last_heartbeat = time.time()

    async def _watchdog_loop(self) -> None:
        """Main watchdog monitoring loop."""
        while self._running:
            try:
                elapsed = time.time() - self._last_heartbeat

                if elapsed >= self._timeout:
                    logger.warning(
                        f"Watchdog timeout! No heartbeat for {elapsed:.1f}s "
                        f"(threshold: {self._timeout}s)"
                    )

                    await self._event_bus.publish(
                        Event(
                            event_type=SystemEvents.SYSTEM_WATCHDOG_TRIGGERED,
                            source="watchdog",
                            data={
                                "elapsed_seconds": elapsed,
                                "timeout": self._timeout,
                            },
                            priority=EventPriority.CRITICAL,
                        )
                    )

                    # Attempt restart
                    await self._restart_system()

                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog loop error: {e}")
                await asyncio.sleep(1)

    async def _restart_system(self) -> None:
        """Restart the system via systemd or direct restart."""
        if self._restart_requested:
            return
        self._restart_requested = True

        logger.info("Initiating system restart via watchdog")

        try:
            # Try systemd restart first
            if os.geteuid() == 0:
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                # Graceful shutdown and let systemd restart us
                await self._event_bus.publish(
                    Event(
                        event_type=SystemEvents.SYSTEM_SHUTDOWN,
                        source="watchdog",
                        data={"reason": "watchdog_timeout"},
                        priority=EventPriority.CRITICAL,
                    )
                )
                # Give time for graceful shutdown
                await asyncio.sleep(2)
                os._exit(1)
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            os._exit(1)
