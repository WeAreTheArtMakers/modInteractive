#!/usr/bin/env python3
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pir import PIRSensor


running = True


def stop(_signum, _frame):
    global running
    running = False


def parse_args():
    parser = argparse.ArgumentParser(description="Test PIR sensor wiring on Raspberry Pi")
    parser.add_argument("--pin", type=int, default=17, help="BCM GPIO pin number, default: 17")
    parser.add_argument("--active-low", action="store_true", help="Use active_low signal")
    parser.add_argument("--pull-up", action="store_true", help="Enable internal pull-up")
    parser.add_argument("--settle", type=int, default=5, help="Warmup seconds, default: 5")
    parser.add_argument("--interval", type=float, default=0.2, help="Poll interval seconds, default: 0.2")
    return parser.parse_args()


def main():
    args = parse_args()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    sensor = PIRSensor(
        gpio_pin=args.pin,
        active_high=not args.active_low,
        pull_up=args.pull_up,
        bounce_time_ms=100,
        settle_seconds=args.settle,
    )

    if not sensor.open():
        print(f"FAIL: PIR sensor could not be opened on BCM GPIO {args.pin}")
        print("Check wiring and install packages: sudo apt install python3-gpiozero python3-lgpio")
        return 1

    print(f"OK: PIR opened on BCM GPIO {args.pin}")
    print("Move in front of the sensor. Press CTRL+C to stop.")

    last_state = None

    try:
        while running:
            state = sensor.current_state()

            if state != last_state:
                print(f"{time.strftime('%H:%M:%S')} state={state}")
                last_state = state

            if sensor.motion_detected():
                print(f"{time.strftime('%H:%M:%S')} MOTION")

            time.sleep(max(0.01, args.interval))

    finally:
        sensor.close()

    print("Stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
