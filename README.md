# modInteractive - Interactive Kiosk System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**modInteractive** is an interactive kiosk application designed for **Raspberry Pi 5**. It uses a camera to detect motion or people, and plays a greeting video in fullscreen when someone approaches. After the video ends, it returns to detection mode.

## System Architecture

```
┌──────────────────────────────────────────────┐
│                  main.py                      │
│         Entry point + signal handling        │
├──────────────────────────────────────────────┤
│                  app.py                       │
│      Application controller + event loop     │
├───────────────┬───────────────┬──────────────┤
│  core/config  │ core/detector  │ core/player │
│  JSON config  │ Motion + YOLO  │  mpv video  │
│               │   OpenCV       │  subprocess │
├───────────────┴───────────────┴──────────────┤
│              core/logger                      │
│     Console + rotating file logging           │
└──────────────────────────────────────────────┘
```

## Features

- **Motion Detection**: OpenCV background subtraction (MOG2) for reliable motion detection
- **Optional YOLO Detection**: Person detection using YOLOv8 (requires ultralytics)
- **Video Playback**: Fullscreen video via mpv with hardware acceleration
- **Cooldown System**: Prevents re-triggering during and shortly after playback
- **Dual Logging**: Console output + rotating file in `logs/`
- **System Check Mode**: `python main.py --check` verifies all components
- **Systemd Service**: Runs as a proper Linux service with auto-restart
- **Idempotent Installer**: `install.sh` can be run multiple times safely

## Requirements

### Hardware
- Raspberry Pi 5 (recommended)
- Raspberry Pi Camera Module or USB camera
- Display (HDMI)

### Software
- Raspberry Pi OS (Bookworm) or newer
- Python 3.11+
- mpv video player

## Quick Installation

### Automatic Installation

```bash
# Clone the repository
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive

# Add your greeting video
cp /path/to/your/video.mp4 videos/selamlama.mp4

# Run the installer
sudo ./install.sh
```

### Manual Installation

```bash
# 1. Install system dependencies
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-opencv mpv

# 2. Clone and setup
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Add a video file
cp /path/to/your/greeting.mp4 videos/selamlama.mp4

# 6. Test the application
python main.py

# 7. Install systemd service (optional)
sudo cp systemd/modinteractive.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable modinteractive
sudo systemctl start modinteractive
```

## Configuration

Edit `config.json` to customize the application:

```json
{
  "video_path": "videos/selamlama.mp4",
  "camera_index": 0,
  "camera_width": 640,
  "camera_height": 480,
  "camera_fps": 15,
  "detection_enabled": true,
  "detection_mode": "motion",
  "detection_confidence": 0.5,
  "motion_sensitivity": 500,
  "cooldown_seconds": 10,
  "fullscreen": true,
  "log_level": "INFO",
  "log_max_bytes": 5242880,
  "log_backup_count": 3,
  "player": "mpv",
  "player_volume": 90
}
```

### Configuration Fields

| Field | Default | Description |
|-------|---------|-------------|
| `video_path` | `videos/selamlama.mp4` | Path to the greeting video |
| `camera_index` | `0` | Camera device index (0 = first camera) |
| `camera_width` | `640` | Camera capture width |
| `camera_height` | `480` | Camera capture height |
| `camera_fps` | `15` | Camera capture framerate |
| `detection_enabled` | `true` | Enable/disable motion detection |
| `detection_mode` | `motion` | Detection mode: `motion` or `yolo` |
| `detection_confidence` | `0.5` | Confidence threshold (0.0-1.0) |
| `motion_sensitivity` | `500` | Lower = more sensitive to motion |
| `cooldown_seconds` | `10` | Seconds to wait after video ends |
| `fullscreen` | `true` | Play video in fullscreen mode |
| `log_level` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `log_max_bytes` | `5242880` | Max log file size (5 MB) |
| `log_backup_count` | `3` | Number of rotated log files to keep |
| `player` | `mpv` | Video player executable |
| `player_volume` | `90` | Playback volume (0-100) |

## Usage

### Running Manually

```bash
# Normal run
python main.py

# With custom config
python main.py --config /path/to/config.json

# System check mode
python main.py --check
```

### Running as a Service

```bash
# Start the service
sudo systemctl start modinteractive

# Stop the service
sudo systemctl stop modinteractive

# Check service status
sudo systemctl status modinteractive

# View live logs
journalctl -u modinteractive -f

# Disable auto-start
sudo systemctl disable modinteractive

# Re-enable auto-start
sudo systemctl enable modinteractive
```

### System Check Mode

The `--check` flag runs diagnostics and reports the status of all components:

```bash
python main.py --check
```

Expected output:
```
============================================================
modInteractive - System Check
============================================================
[OK] Configuration loaded: config.json
[OK] Log directory is writable: logs/
[OK] Video file found: /Users/bg/Desktop/modInteractive/videos/selamlama.mp4
[OK] Player 'mpv' is available
[OK] Camera (index 0) is available
    Resolution: 640x480
[OK] Python 3.11.4
------------------------------------------------------------
System check complete
```

## Adding Videos

1. Place your video files in the `videos/` directory
2. Update `video_path` in `config.json` if using a different filename
3. Supported formats: MP4, AVI, MKV, MOV, WebM

```bash
# Example: Add a greeting video
cp /path/to/your/greeting.mp4 videos/selamlama.mp4
```

## Project Structure

```
modInteractive/
├── main.py                  # Entry point
├── app.py                   # Application controller
├── config.json              # Configuration file
├── requirements.txt         # Python dependencies
├── install.sh               # Installation script
├── README.md                # This file
├── .gitignore               # Git ignore rules
├── core/
│   ├── __init__.py          # Package init
│   ├── config.py            # Configuration management
│   ├── detector.py          # Motion/person detection
│   ├── logger.py            # Logging setup
│   └── player.py            # Video playback
├── systemd/
│   └── modinteractive.service  # Systemd service file
├── videos/
│   ├── .gitkeep             # Keep directory in git
│   ├── README.md            # Video instructions
│   └── selamlama.mp4        # Your greeting video (not tracked)
└── logs/
    └── .gitkeep             # Keep directory in git
```

## Troubleshooting

### Camera not opening

```bash
# Check if camera is detected
ls -la /dev/video*

# Test camera with v4l2
sudo apt install v4l-utils
v4l2-ctl --list-devices

# Ensure user is in video group
sudo usermod -a -G video $USER

# On Raspberry Pi, enable camera
sudo raspi-config
# → Interface Options → Camera → Enable

# Reboot after changes
sudo reboot
```

### Video not found

```
[WARNING] Video file not found: videos/selamlama.mp4
```

Place a video file in the `videos/` directory or update `video_path` in `config.json`.

### mpv not installed

```bash
sudo apt install mpv
```

### Service not starting

```bash
# Check service status
sudo systemctl status modinteractive

# View detailed logs
journalctl -u modinteractive -f

# Check virtual environment path
ls -la /opt/modInteractive/venv/bin/python

# Fix permissions
sudo chown -R pi:pi /opt/modInteractive

# Test manually
sudo -u pi /opt/modInteractive/venv/bin/python /opt/modInteractive/main.py
```

### Virtualenv path mismatch

The installer creates the virtual environment at `/opt/modInteractive/venv/`.
The systemd service file uses the same path. If you see errors about Python not found:

```bash
# Verify the path
ls -la /opt/modInteractive/venv/bin/python

# Reinstall if missing
sudo ./install.sh
```

### Permission errors

```bash
# Fix ownership
sudo chown -R pi:pi /opt/modInteractive

# Check video group membership
groups pi

# Add user to video group if needed
sudo usermod -a -G video pi
```

## Development

```bash
# Clone repository
git clone https://github.com/WeAreTheArtMakers/modInteractive.git
cd modInteractive

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Log Files

Logs are written to both the console and `logs/modinteractive.log`.

Example log format:
```
[2026-06-26 14:20:00] [INFO] modInteractive: Application started
[2026-06-26 14:20:01] [OK] Video file found: videos/selamlama.mp4
[2026-06-26 14:20:02] [INFO] app: Camera opened: index=0, 640x480 @ 15 fps
[2026-06-26 14:20:15] [INFO] app: 🎯 Detection: method=motion, confidence=0.78, pixels=1234
[2026-06-26 14:20:15] [INFO] app: ▶️ Starting video playback
[2026-06-26 14:20:20] [INFO] app: ⏹️ Video playback finished
[2026-06-26 14:20:20] [INFO] app: ⏳ Cooldown: 10 seconds
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- GitHub Issues: [https://github.com/WeAreTheArtMakers/modInteractive/issues](https://github.com/WeAreTheArtMakers/modInteractive/issues)
- Repository: [https://github.com/WeAreTheArtMakers/modInteractive](https://github.com/WeAreTheArtMakers/modInteractive)