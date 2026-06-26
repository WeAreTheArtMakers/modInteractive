"""Event bus system for inter-service communication.

All services communicate through this event bus.
No direct service-to-service calls are allowed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Priority levels for events."""

    CRITICAL = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()


class SystemEvents(Enum):
    """System-wide event types."""

    # State machine events
    STATE_CHANGED = auto()
    STATE_TRANSITION_FAILED = auto()

    # Camera events
    CAMERA_CONNECTED = auto()
    CAMERA_DISCONNECTED = auto()
    CAMERA_FRAME_READY = auto()
    CAMERA_ERROR = auto()

    # Detection events
    PERSON_DETECTED = auto()
    PERSON_CONFIRMED = auto()
    PERSON_LOST = auto()
    MOTION_DETECTED = auto()
    DETECTION_ERROR = auto()

    # Playback events
    PLAYBACK_STARTED = auto()
    PLAYBACK_COMPLETED = auto()
    PLAYBACK_ERROR = auto()
    FADE_IN_STARTED = auto()
    FADE_IN_COMPLETED = auto()
    FADE_OUT_STARTED = auto()
    FADE_OUT_COMPLETED = auto()

    # System events
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_ERROR = auto()
    SYSTEM_WATCHDOG_TRIGGERED = auto()
    CONFIG_CHANGED = auto()
    PLUGIN_LOADED = auto()
    PLUGIN_ERROR = auto()

    # UI events
    UI_STATE_UPDATE = auto()
    UI_USER_ACTION = auto()
    UI_THEME_CHANGED = auto()


@dataclass
class Event:
    """Immutable event object passed through the bus."""

    event_type: SystemEvents
    source: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    id: str = field(default_factory=lambda: f"{time.time_ns()}")

    def __post_init__(self) -> None:
        """Validate event after initialization."""
        if not isinstance(self.event_type, SystemEvents):
            raise ValueError(f"Invalid event type: {self.event_type}")


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus implementing publish-subscribe pattern.

    All services communicate through this bus. No direct calls.
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        """Initialize event bus.

        Args:
            max_queue_size: Maximum number of events in queue
        """
        self._subscribers: Dict[SystemEvents, List[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: List[EventHandler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._event_history: List[Event] = []
        self._max_history = 1000

    async def start(self) -> None:
        """Start the event bus processing loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the event bus processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped")

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        try:
            await self._queue.put(event)
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
        except asyncio.QueueFull:
            logger.warning(f"Event queue full, dropping event: {event.event_type}")

    def subscribe(
        self,
        event_type: SystemEvents,
        handler: EventHandler,
    ) -> Callable[[], None]:
        """Subscribe to a specific event type.

        Args:
            event_type: Event type to subscribe to
            handler: Async callback function

        Returns:
            Unsubscribe callback
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed to {event_type.name}")

        def unsubscribe() -> None:
            """Remove subscription."""
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

        return unsubscribe

    def subscribe_all(self, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to all events.

        Args:
            handler: Async callback for all events

        Returns:
            Unsubscribe callback
        """
        self._wildcard_subscribers.append(handler)

        def unsubscribe() -> None:
            """Remove wildcard subscription."""
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)

        return unsubscribe

    def get_history(
        self,
        event_type: Optional[SystemEvents] = None,
        limit: int = 50,
    ) -> List[Event]:
        """Get recent event history.

        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return

        Returns:
            List of recent events
        """
        if event_type:
            filtered = [e for e in self._event_history if e.event_type == event_type]
            return filtered[-limit:]
        return self._event_history[-limit:]

    async def _process_events(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await self._queue.get()
                await self._dispatch(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event processing error: {e}", exc_info=True)

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all subscribers.

        Args:
            event: Event to dispatch
        """
        # Dispatch to wildcard subscribers
        for handler in self._wildcard_subscribers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Wildcard handler error: {e}")

        # Dispatch to specific subscribers
        for handler in self._subscribers.get(event.event_type, []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Handler error for {event.event_type.name}: {e}",
                    exc_info=True,
                )