# modInteractive

**AI-Powered Kiosk System for Raspberry Pi 5**

modInteractive is an intelligent kiosk system that uses computer vision (YOLOv8) and motion detection to detect people and trigger video playback. Designed for Raspberry Pi 5 with hardware-accelerated video rendering via mpv.

## Features

- **Hybrid Detection Engine** — Combines YOLOv8 AI person detection with motion detection for reliable triggering
- **Hardware-Accelerated Playback** — Uses mpv with GPU-accelerated video rendering
- **Smooth Fade Transitions** — Configurable fade-in/fade-out transitions between videos
- **Plugin Architecture** — Extensible via plugin system for detection backends, playback engines, and UI components
- **Event-Driven Architecture** — All services communicate via asynchronous event bus
- **Service Watchdog** — Automatic recovery from service failures
- **Headless Operation** — Can run without a graphical UI for production deployments
- **Dark Theme UI** — Full-featured PySide6 GUI with dark theme

## Hardware Requirements

| Component | Recommended |
|-----------|-------------|
| **Board** | Raspberry Pi 5 (4GB+ RAM) |
| **Camera** | USB webcam (1080p recommended) |
| **Display** | HDMI monitor or touchscreen |
| **Storage** | 32GB+ microSD or SSD |
| **Power** | 5V/5A USB-C (official Pi 5 power supply) |
| **Cooling** | Active cooler recommended |

### Supported Cameras

- Any USB Video Class (UVC) webcam
- Raspberry Pi Camera Module 3 (via V4L2)
- Tested with Logitech C920, C270, and similar

### Tested Resolutions

- 640×480 @ 15-30 FPS (default, best performance)
- 1280×720 @ 15 FPS
- 1920×1080 @ 10-15 FPS (requires good lighting)

## Software Dependencies

### System Packages

- mpv (hardware-accelerated video player)
- Python 3.11+
- OpenCV (for camera and vision processing)
- Ultralytics YOLOv8 (AI person detection)
- PySide6 (GUI framework, optional for headless)
- systemd (service management)

### Python Packages

```
PySide6>=6.5.0
opencv-python-headless>=4.8.0
numpy>=1.24.0
ultralytics>=8.0.0
psutil>=5.9.0
```

## Installation

### Quick Install (Raspberry Pi OS)

```bash
# Clone the repository
git clone https://github.com/yourusername/modInteractive.git
cd modInteractive

# Run the installer (requires sudo)
sudo bash install.sh
```

The installer will:

1. Install system dependencies (mpv, Python, OpenCV, etc.)
2. Create `/opt/modInteractive` directory structure
3. Copy all project files
4. Set up a Python virtual environment
5. Install Python packages (numpy, opencv, ultralytics, etc.)
6. Download YOLOv8n model (~6MB)
7. Install and enable the systemd service
8. Create example video directory

### Manual Installation

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y mpv python3 python3-pip python3-venv python3-dev \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    cmake build-essential libatlas-base-dev git curl wget v4l-utils

# Create directories
sudo mkdir -p /opt/modInteractive
sudo chown pi:pi /opt/modInteractive

# Copy project files
cp -r * /opt/modInteractive/

# Set up virtual environment
cd /opt/modInteractive
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Download YOLO model
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt \
    -O models/yolov8n.pt

# Install systemd service
sudo cp systemd/modinteractive.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable modinteractive

# Start the service
sudo systemctl start modinteractive
```

### Development Setup

```bash
# Clone and enter the project
git clone https://github.com/yourusername/modInteractive.git
cd modInteractive

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov flake8 mypy

# Run tests
pytest tests/ -v --cov=core

# Type checking
mypy core/ app.py main.py

# Linting
flake8 core/ app.py main.py
```

## Configuration

Configuration is managed via `config.json`. Key settings:

```json
{
  "system": {
    "log_level": "INFO",
    "watchdog_timeout": 10
  },
  "camera": {
    "device_id": 0,
    "resolution": { "width": 640, "height": 480 },
    "fps": 15,
    "auto_reconnect": true
  },
  "detection": {
    "confidence_threshold": 0.65,
    "motion_sensitivity": 0.02,
    "cooldown_seconds": 10,
    "model_path": "models/yolov8n.pt"
  },
  "video": {
    "fade_in_duration": 1.0,
    "fade_out_duration": 1.0,
    "volume": 80,
    "fullscreen": true,
    "playback_mode": "random"
  }
}
```

### Detection Modes

| Mode | Description |
|------|-------------|
| **hybrid** (default) | YOLOv8 person detection with motion detection fallback |
| **yolo** | YOLOv8 AI detection only (requires model) |
| **motion** | Motion detection only (no AI model needed) |

### Playback Modes

| Mode | Description |
|------|-------------|
| **random** (default) | Play random videos from playlist |
| **sequential** | Play videos in order, loop |
| **single** | Always play the first video |

### Video Playlist

Add your MP4 files to `/opt/modInteractive/videos/` and update `config.json`:

```json
{
  "video": {
    "playlist": ["videos/promo1.mp4", "videos/promo2.mp4"]
  }
}
```

Or leave the playlist empty to auto-scan the videos directory.

## Service Management

```bash
# Check service status
sudo systemctl status modinteractive

# View real-time logs
sudo journalctl -u modinteractive -f

# View application log
tail -f /opt/modInteractive/logs/modinteractive.log

# Restart service
sudo systemctl restart modinteractive

# Stop service
sudo systemctl stop modinteractive

# Disable auto-start
sudo systemctl disable modinteractive
```

## Project Structure

```
/opt/modInteractive/
├── main.py                 # Entry point
├── app.py                  # Application controller
├── config.json             # Configuration
├── requirements.txt        # Python dependencies
├── core/
│   ├── __init__.py
│   ├── event_bus.py        # Async event bus
│   ├── state_machine.py    # System state machine
│   ├── config_service.py   # Configuration management
│   ├── logging_service.py  # Logging service
│   ├── camera_service.py   # USB camera management
│   ├── detection_service.py # AI + motion detection
│   ├── playback_service.py # Video playback with mpv
│   ├── watchdog.py         # System watchdog
│   └── plugin_base.py      # Plugin system
├── ui/
│   └── __init__.py         # UI components (PySide6)
├── assets/
│   ├── themes/             # QSS stylesheets
│   ├── icons/              # Application icons
│   └── scripts/            # mpv Lua scripts
├── plugins/
│   ├── detection/          # Detection plugins
│   ├── playback/           # Playback plugins
│   └── ui/                 # UI plugins
├── models/                 # YOLO model files
├── videos/                 # Video playlist directory
├── logs/                   # Application logs
├── systemd/                # Systemd service file
├── tests/                  # Test suite
├── install.sh              # Installation script
├── uninstall.sh            # Uninstallation script
└── README.md               # This file
```

## Troubleshooting

### Camera Not Detected

```bash
# Check connected USB devices
lsusb

# Check video devices
ls -la /dev/video*

# Test camera with OpenCV
python3 -c "import cv2; cap=cv2.VideoCapture(0); print(cap.isOpened())"

# Enable V4L2 if not loaded
sudo modprobe v4l2loopback
```

### Video Playback Issues

```bash
# Test mpv directly
mpv --vo=gpu --hwdec=v4l2m2m /path/to/video.mp4

# Check mpv hardware acceleration
mpv --vo=help

# Test with software rendering
mpv --vo=x11 --hwdec=no /path/to/video.mp4
```

### Service Won't Start

```bash
# Check service logs
sudo journalctl -u modinteractive -n 50 --no-pager

# Check application log
cat /opt/modInteractive/logs/modinteractive.log

# Run directly to see errors
sudo -u pi /opt/modInteractive/venv/bin/python /opt/modInteractive/main.py

# Verify Python environment
/opt/modInteractive/venv/bin/python -c "import cv2; import numpy; import ultralytics; print('OK')"
```

### High CPU Usage

- Reduce camera resolution in `config.json` (640×480 recommended)
- Increase `frame_skip` to process fewer frames
- Lower detection `confidence_threshold`
- Disable YOLO detection and use motion-only mode

### Permission Issues

```bash
# Fix permissions
sudo chown -R pi:pi /opt/modInteractive
sudo chmod -R 755 /opt/modInteractive
sudo chmod -R 775 /opt/modInteractive/logs
sudo chmod -R 775 /opt/modInteractive/videos

# Add pi user to video group
sudo usermod -a -G video pi
```

## Performance Tuning

### Raspberry Pi 5 Optimizations

1. **Enable hardware acceleration**:
   ```bash
   # In /boot/config.txt, ensure:
   dtoverlay=vc4-kms-v3d
   gpu_mem=256
   ```

2. **Use performance governor**:
   ```bash
   sudo cpufreq-set -g performance
   ```

3. **Reduce camera resolution** (in config.json):
   ```json
   "resolution": { "width": 640, "height": 480 }
   ```

4. **Adjust frame skip**:
   ```json
   "frame_skip": 3
   ```

5. **Disable GUI for headless operation**:
   The system runs headless by default when the UI module is unavailable.

## API Reference

### Event Bus Events

| Event | Description |
|-------|-------------|
| `CAMERA_FRAME_READY` | New camera frame available |
| `CAMERA_CONNECTED` | Camera connected successfully |
| `CAMERA_DISCONNECTED` | Camera disconnected |
| `PERSON_DETECTED` | Motion detected (low confidence) |
| `PERSON_CONFIRMED` | Person confirmed (high confidence) |
| `PERSON_LOST` | Person left detection area |
| `PLAYBACK_STARTED` | Video playback started |
| `PLAYBACK_COMPLETED` | Video playback finished |
| `FADE_IN_STARTED` | Fade-in transition started |
| `FADE_OUT_STARTED` | Fade-out transition started |
| `SYSTEM_STARTUP` | System startup complete |
| `SYSTEM_SHUTDOWN` | System shutting down |
| `SYSTEM_ERROR` | System error occurred |

## License

MIT License — see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- All services communicate via the event bus — no direct service-to-service calls
- Use async/await for all I/O operations
- Type hints are required for all function signatures
- Tests must pass before merging
- Follow PEP 8 style guide
