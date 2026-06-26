# PIR Sensor Support

This patch adds PIR GPIO trigger support next to the existing camera motion trigger.

## Modes

Default mode:

```bash
python main.py
```

Force camera mode:

```bash
python main.py --source camera
```

Force PIR mode:

```bash
python main.py --source pir
```

Health check:

```bash
python main.py --check
python main.py --source pir --check
```

## Config

`config.json` now includes:

```json
{
  "trigger": {
    "source": "camera"
  },
  "pir": {
    "gpio_pin": 17,
    "active_high": true,
    "pull_up": false,
    "bounce_time_ms": 500,
    "settle_seconds": 30,
    "poll_interval": 0.05
  }
}
```

Set `"trigger": { "source": "pir" }` to use PIR by default.

## Wiring

Use BCM GPIO numbering, not physical pin numbering.

Common PIR wiring:

- PIR VCC to 5V
- PIR GND to GND
- PIR OUT to a 3.3V-safe Raspberry Pi GPIO input, default BCM GPIO 17

Important: Raspberry Pi GPIO pins are 3.3V only. The PIR signal output must not send 5V into the GPIO pin.

For Raspberry Pi 5, install GPIO packages with apt:

```bash
sudo apt install python3-gpiozero python3-lgpio
```
