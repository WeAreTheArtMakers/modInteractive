"""Finite State Machine for modInteractive system.

Strict state management with no direct service-to-service calls.
All state transitions are event-driven through the event bus.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, Optional, Set

from core.event_bus import Event, EventBus, EventPriority, SystemEvents

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """System states for the kiosk finite state machine."""

    STARTUP = auto()
    IDLE = auto()
    DETECTING = auto()
    PERSON_CONFIRMED = auto()
    FADE_IN = auto()
    PLAYING = auto()
    FADE_OUT = auto()
    COOLDOWN = auto()
    ERROR = auto()
    SHUTDOWN = auto()


# Define valid state transitions
VALID_TRANSITIONS: Dict[SystemState, Set[SystemState]] = {
    SystemState.STARTUP: {SystemState.IDLE, SystemState.ERROR},
    SystemState.IDLE: {SystemState.DETECTING, SystemState.ERROR, SystemState.SHUTDOWN},
    SystemState.DETECTING: {
        SystemState.PERSON_CONFIRMED,
        SystemState.IDLE,
        SystemState.ERROR,
        SystemState.SHUTDOWN,
    },
    SystemState.PERSON_CONFIRMED: {
        SystemState.FADE_IN,
        SystemState.IDLE,
        SystemState.ERROR,
        SystemState.SHUTDOWN,
    },
    SystemState.FADE_IN: {
        SystemState.PLAYING,
        SystemState.ERROR,
        SystemState.SHUTDOWN,
    },
    SystemState.PLAYING: {
        SystemState.FADE_OUT,
        SystemState.ERROR,
        SystemState.SHUTDOWN,
    },
    SystemState.FADE_OUT: {
        SystemState.COOLDOWN,
        SystemState.IDLE,
        SystemState.ERROR,
        SystemState.SHUTDOWN,
    },
    SystemState.COOLDOWN: {
        SystemState.IDLE,
        SystemState.ERROR,
        SystemState.SHUTDOWN,
    },
    SystemState.ERROR: {
        SystemState.IDLE,
        SystemState.SHUTDOWN,
    },
    SystemState.SHUTDOWN: set(),
}


# Map event types to state transitions
EVENT_TO_STATE_MAP: Dict[SystemEvents, SystemState] = {
    SystemEvents.SYSTEM_STARTUP: SystemState.STARTUP,
    SystemEvents.PERSON_DETECTED: SystemState.DETECTING,
    SystemEvents.PERSON_CONFIRMED: SystemState.PERSON_CONFIRMED,
    SystemEvents.FADE_IN_STARTED: SystemState.FADE_IN,
    SystemEvents.PLAYBACK_STARTED: SystemState.PLAYING,
    SystemEvents.FADE_OUT_STARTED: SystemState.FADE_OUT,
    SystemEvents.PLAYBACK_COMPLETED: SystemState.COOLDOWN,
    SystemEvents.CAMERA_ERROR: SystemState.ERROR,
    SystemEvents.DETECTION_ERROR: SystemState.ERROR,
    SystemEvents.PLAYBACK_ERROR: SystemState.ERROR,
    SystemEvents.SYSTEM_ERROR: SystemState.ERROR,
    SystemEvents.SYSTEM_SHUTDOWN: SystemState.SHUTDOWN,
}


class StateMachine:
    """Finite state machine for system control.

    Enforces strict state transitions and emits events on changes.
    """

    def __init__(
        self,
        event_bus: EventBus,
        on_state_change: Optional[Callable[[SystemState, SystemState], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """Initialize state machine.

        Args:
            event_bus: System event bus for communication
            on_state_change: Optional callback for state changes
        """
        self._event_bus = event_bus
        self._current_state: SystemState = SystemState.STARTUP
        self._previous_state: Optional[SystemState] = None
        self._on_state_change = on_state_change
        self._lock = asyncio.Lock()
        self._state_timers: Dict[SystemState, float] = {}
        self._transition_count: int = 0

    @property
    def current_state(self) -> SystemState:
        """Get current system state."""
        return self._current_state

    @property
    def previous_state(self) -> Optional[SystemState]:
        """Get previous system state."""
        return self._previous_state

    @property
    def state_duration(self) -> float:
        """Get duration in current state in seconds."""
        if self._current_state in self._state_timers:
            import time
            return time.time() - self._state_timers[self._current_state]
        return 0.0

    async def transition_to(self, new_state: SystemState) -> bool:
        """Attempt to transition to a new state.

        Args:
            new_state: Target state to transition to

        Returns:
            True if transition succeeded, False otherwise
        """
        async with self._lock:
            return await self._do_transition(new_state)

    async def handle_event(self, event: Event) -> None:
        """Handle incoming event and potentially trigger state transition.

        Args:
            event: Incoming event
        """
        target_state = EVENT_TO_STATE_MAP.get(event.event_type)
        if target_state:
            await self.transition_to(target_state)

    async def _do_transition(self, new_state: SystemState) -> bool:
        """Execute state transition with validation.

        Args:
            new_state: Target state

        Returns:
            True if transition succeeded
        """
        # Allow transition from any state to ERROR or SHUTDOWN
        if new_state in (SystemState.ERROR, SystemState.SHUTDOWN):
            pass  # Always allowed
        elif new_state not in VALID_TRANSITIONS.get(self._current_state, set()):
            logger.warning(
                f"Invalid transition: {self._current_state.name} -> {new_state.name}"
            )
            await self._event_bus.publish(
                Event(
                    event_type=SystemEvents.STATE_TRANSITION_FAILED,
                    source="state_machine",
                    data={
                        "from": self._current_state.name,
                        "to": new_state.name,
                        "reason": "invalid_transition",
                    },
                    priority=EventPriority.HIGH,
                )
            )
            return False

        old_state = self._current_state
        self._previous_state = old_state
        self._current_state = new_state
        self._transition_count += 1

        import time
        self._state_timers[new_state] = time.time()

        logger.info(
            f"State transition: {old_state.name} -> {new_state.name} "
            f"(transition #{self._transition_count})"
        )

        # Notify via event bus
        await self._event_bus.publish(
            Event(
                event_type=SystemEvents.STATE_CHANGED,
                source="state_machine",
                data={
                    "from": old_state.name,
                    "to": new_state.name,
                    "transition_id": self._transition_count,
                    "duration_in_previous": time.time() - self._state_timers.get(old_state, time.time()),
                },
                priority=EventPriority.HIGH,
            )
        )

        # Call optional callback - safely handle both coroutine and regular functions
        if self._on_state_change:
            try:
                result = self._on_state_change(old_state, new_state)
                if result is not None:
                    await result
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        return True

    def reset(self) -> None:
        """Reset state machine to idle state."""
        self._current_state = SystemState.IDLE
        self._previous_state = None
        import time
        self._state_timers[SystemState.IDLE] = time.time()
        self._transition_count = 0
        logger.info("State machine reset to IDLE")