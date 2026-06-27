from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("modInteractive.pir")


class PIRSensor:
    def __init__(
        self,
        gpio_pin: int = 17,
        active_high: bool = True,
        pull_up: bool = False,
        bounce_time_ms: int = 500,
        settle_seconds: int = 30,
    ) -> None:
        self.gpio_pin = int(gpio_pin)
        self.active_high = bool(active_high)
        self.pull_up = bool(pull_up)
        self.bounce_time_ms = max(0, int(bounce_time_ms))
        self.settle_seconds = max(0, int(settle_seconds))
        self._device: Optional[object] = None
        self._last_state = False
        self._last_trigger_time = 0.0

    @property
    def is_open(self) -> bool:
        return self._device is not None

    @property
    def last_trigger_time(self) -> float:
        return self._last_trigger_time

    def open(self) -> bool:
        if self._device is not None:
            return True

        try:
            from gpiozero import DigitalInputDevice
        except ImportError as exc:
            logger.error(
                "gpiozero is not installed. Install with: sudo apt install python3-gpiozero python3-lgpio"
            )
            logger.debug("gpiozero import error: %s", exc)
            return False

        try:
            bounce_time = self.bounce_time_ms / 1000 if self.bounce_time_ms > 0 else None
            self._device = DigitalInputDevice(
                self.gpio_pin,
                pull_up=self.pull_up,
                bounce_time=bounce_time,
            )

            if self.settle_seconds > 0:
                logger.info("PIR warming up for %d seconds", self.settle_seconds)
                time.sleep(self.settle_seconds)

            logger.info(
                "PIR sensor opened on BCM GPIO %d active_high=%s pull_up=%s bounce=%sms",
                self.gpio_pin,
                self.active_high,
                self.pull_up,
                self.bounce_time_ms,
            )
            return True

        except Exception:
            logger.exception("Could not open PIR sensor on BCM GPIO %d", self.gpio_pin)
            self.close()
            return False

    def motion_detected(self) -> bool:
        if self._device is None:
            return False

        try:
            raw_state = bool(getattr(self._device, "is_active"))
            current_state = raw_state if self.active_high else not raw_state
        except Exception:
            logger.exception("Could not read PIR state")
            return False

        detected = current_state and not self._last_state
        self._last_state = current_state

        if detected:
            self._last_trigger_time = time.time()

        return detected

    def current_state(self) -> bool:
        if self._device is None:
            return False

        try:
            raw_state = bool(getattr(self._device, "is_active"))
            return raw_state if self.active_high else not raw_state
        except Exception:
            logger.exception("Could not read current PIR state")
            return False

    def close(self) -> None:
        if self._device is None:
            return

        try:
            close = getattr(self._device, "close", None)
            if callable(close):
                close()
        except Exception:
            logger.debug("PIR close failed", exc_info=True)
        finally:
            self._device = None
            self._last_state = False
