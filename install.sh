#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# modInteractive Installer
# Installs the AI-Powered Kiosk System on Raspberry Pi 5
# =============================================================================

VERSION="2.0.0"
INSTALL_DIR="/opt/modInteractive"
SERVICE_NAME="modinteractive.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
VENV_DIR="${INSTALL_DIR}/venv"
REQUIREMENTS_FILE="${INSTALL_DIR}/requirements.txt"
CONFIG_FILE="${INSTALL_DIR}/config.json"
MAIN_SCRIPT="${INSTALL_DIR}/main.py"
MODEL_DIR="${INSTALL_DIR}/models"
YOLO_MODEL="${MODEL_DIR}/yolov8n.pt"
VIDEO_DIR="${INSTALL_DIR}/videos"
EXAMPLE_VIDEO_DIR="${VIDEO_DIR}/examples"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_err "This script must be run as root (use sudo)"
        exit 1
    fi
    log_ok "Root privileges confirmed"
}

check_raspberry_pi() {
    if [[ ! -f /proc/device-tree/model ]]; then
        log_warn "Not running on a Raspberry Pi (no /proc/device-tree/model)"
        log_warn "Installation will continue, but hardware acceleration may not work."
        return
    fi
    local model
    model=$(tr -d '\0' < /proc/device-tree/model)
    log_info "Detected: ${model}"
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        log_info "OS: ${PRETTY_NAME:-${NAME} ${VERSION_ID}}"
    else
        log_warn "Could not detect OS version"
    fi
}

# ---------------------------------------------------------------------------
# System dependency installation
# ---------------------------------------------------------------------------
install_system_deps() {
    log_info "Updating package lists..."
    apt-get update -qq

    log_info "Installing system dependencies..."
    apt-get install -y -qq \
        mpv \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        cmake \
        build-essential \
        libatlas-base-dev \
        git \
        curl \
        wget \
        v4l-utils \
    || {
        log_err "Failed to install system dependencies"
        exit 1
    }
    log_ok "System dependencies installed"
}

install_mpv_arm64() {
    # Ensure mpv is available with hardware acceleration on Pi 5
    if command -v mpv &>/dev/null; then
        log_ok "mpv $(mpv --version | head -1)"
    else
        log_err "mpv installation failed"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
create_directories() {
    log_info "Creating installation directory: ${INSTALL_DIR}"
    mkdir -p "${INSTALL_DIR}"
    mkdir -p "${MODEL_DIR}"
    mkdir -p "${VIDEO_DIR}"
    mkdir -p "${EXAMPLE_VIDEO_DIR}"
    mkdir -p "${INSTALL_DIR}/logs"
    mkdir -p "${INSTALL_DIR}/assets/scripts"
    mkdir -p "${INSTALL_DIR}/assets/themes"
    mkdir -p "${INSTALL_DIR}/assets/icons"
    mkdir -p "${INSTALL_DIR}/plugins/detection"
    mkdir -p "${INSTALL_DIR}/plugins/playback"
    mkdir -p "${INSTALL_DIR}/plugins/ui"
    log_ok "Directories created"
}

# ---------------------------------------------------------------------------
# File copy
# ---------------------------------------------------------------------------
copy_files() {
    local src_dir
    src_dir="$(dirname "$0")"

    log_info "Copying project files to ${INSTALL_DIR}..."

    cp -r "${src_dir}/main.py"          "${INSTALL_DIR}/"
    cp -r "${src_dir}/app.py"           "${INSTALL_DIR}/"
    cp -r "${src_dir}/config.json"      "${INSTALL_DIR}/"
    cp -r "${src_dir}/requirements.txt" "${INSTALL_DIR}/"
    cp -r "${src_dir}/core"             "${INSTALL_DIR}/"
    cp -r "${src_dir}/ui"               "${INSTALL_DIR}/"
    cp -r "${src_dir}/assets"           "${INSTALL_DIR}/"
    cp -r "${src_dir}/plugins"          "${INSTALL_DIR}/"

    # Copy systemd service file
    cp "${src_dir}/systemd/modinteractive.service" "${INSTALL_DIR}/"

    log_ok "Project files copied"
}

# ---------------------------------------------------------------------------
# Python virtual environment setup
# ---------------------------------------------------------------------------
setup_venv() {
    log_info "Creating Python virtual environment..."

    python3 -m venv --system-site-packages "${VENV_DIR}"

    # Upgrade pip
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip setuptools wheel

    log_ok "Virtual environment created at ${VENV_DIR}"
}

install_python_requirements() {
    log_info "Installing Python requirements..."
    log_info "This may take a while on a Raspberry Pi (especially PyTorch)..."

    # Install dependencies that are easier via apt on Pi
    pip_install() {
        "${VENV_DIR}/bin/pip" install --quiet "$@" || {
            log_warn "pip install failed for: $*"
            log_warn "Retrying without cache..."
            "${VENV_DIR}/bin/pip" install --quiet --no-cache-dir "$@" || {
                log_err "Failed to install: $*"
                log_err "Check the error above and install manually."
            }
        }
    }

    # Core ML dependencies (install numpy first)
    pip_install numpy>=1.24.0
    pip_install opencv-python-headless>=4.8.0
    pip_install "opencv-python-headless>=4.8.0"
    pip_install ultralytics>=8.0.0
    pip_install PySide6>=6.5.0
    pip_install psutil>=5.9.0

    log_ok "Python requirements installed"
}

# ---------------------------------------------------------------------------
# YOLO model download
# ---------------------------------------------------------------------------
download_yolo_model() {
    if [[ -f "${YOLO_MODEL}" ]]; then
        log_info "YOLO model already exists at ${YOLO_MODEL}, skipping download"
        return
    fi

    log_info "Downloading YOLOv8n model..."
    "${VENV_DIR}/bin/python" -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.save('${YOLO_MODEL}')
print('YOLOv8n model downloaded successfully')
" || {
        log_warn "Failed to download via ultralytics, trying direct download..."
        wget -q -O "${YOLO_MODEL}" "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt" || {
            log_err "Failed to download YOLO model"
            log_err "You can download manually:"
            log_err "  wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt -O ${YOLO_MODEL}"
        }
    }

    if [[ -f "${YOLO_MODEL}" ]]; then
        log_ok "YOLO model downloaded: ${YOLO_MODEL}"
    fi
}

# ---------------------------------------------------------------------------
# Example videos
# ---------------------------------------------------------------------------
create_example_videos() {
    log_info "Creating example video directory: ${EXAMPLE_VIDEO_DIR}"
    # Placeholder — users should copy their own .mp4 files here
    cat > "${EXAMPLE_VIDEO_DIR}/README.txt" << 'VIDEOF'
modInteractive Example Videos
=============================

Place your MP4 video files in this directory to add them to the playlist.

The system will pick videos from /opt/modInteractive/videos/ by default.

You can also copy videos to any path and configure the playlist in config.json.

Supported formats: MP4, AVI, MKV, MOV (via mpv)
VIDEOF
    log_ok "Example video directory ready (add .mp4 files to ${EXAMPLE_VIDEO_DIR})"
}

# ---------------------------------------------------------------------------
# Systemd service installation
# ---------------------------------------------------------------------------
install_systemd_service() {
    log_info "Installing systemd service..."

    cp "${INSTALL_DIR}/${SERVICE_NAME}" "${SERVICE_FILE}"
    chmod 644 "${SERVICE_FILE}"

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"

    log_ok "Systemd service installed and enabled: ${SERVICE_NAME}"
}

start_service() {
    log_info "Starting modInteractive service..."
    systemctl start "${SERVICE_NAME}" || {
        log_warn "Service failed to start. Check logs: journalctl -u ${SERVICE_NAME} -n 50"
    }

    # Give it a moment
    sleep 2

    local status
    status=$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo "unknown")
    if [[ "${status}" == "active" ]]; then
        log_ok "Service is running"
    else
        log_warn "Service status: ${status}"
        log_warn "Run 'sudo journalctl -u ${SERVICE_NAME} -n 50' to debug"
    fi
}

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
set_permissions() {
    log_info "Setting permissions..."
    chown -R pi:pi "${INSTALL_DIR}"
    chmod -R 755 "${INSTALL_DIR}"
    # Make sure pi user can read/write logs and videos
    chmod -R 775 "${INSTALL_DIR}/logs"
    chmod -R 775 "${INSTALL_DIR}/videos"
    log_ok "Permissions set"
}

# ---------------------------------------------------------------------------
# Post-install summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo "============================================================================="
    echo -e "${GREEN}  modInteractive v${VERSION} installed successfully!${NC}"
    echo "============================================================================="
    echo ""
    echo "  Installation:  ${INSTALL_DIR}"
    echo "  Virtual env:   ${VENV_DIR}"
    echo "  Config file:   ${CONFIG_FILE}"
    echo "  Videos:        ${VIDEO_DIR}"
    echo "  YOLO model:    ${YOLO_MODEL}"
    echo "  Service:       ${SERVICE_NAME}"
    echo ""
    echo "  Manage service:"
    echo "    sudo systemctl start   ${SERVICE_NAME}"
    echo "    sudo systemctl stop    ${SERVICE_NAME}"
    echo "    sudo systemctl restart ${SERVICE_NAME}"
    echo "    sudo systemctl status  ${SERVICE_NAME}"
    echo ""
    echo "  View logs:"
    echo "    sudo journalctl -u ${SERVICE_NAME} -f"
    echo "    tail -f ${INSTALL_DIR}/logs/modinteractive.log"
    echo ""
    echo "  Uninstall:     sudo ${INSTALL_DIR}/uninstall.sh"
    echo ""
    echo "============================================================================="
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo "============================================================================="
    echo "  modInteractive v${VERSION} Installer"
    echo "  AI-Powered Kiosk System for Raspberry Pi 5"
    echo "============================================================================="
    echo ""

    check_root
    check_raspberry_pi
    check_os
    echo ""

    install_system_deps
    install_mpv_arm64
    echo ""

    create_directories
    copy_files
    echo ""

    setup_venv
    install_python_requirements
    echo ""

    download_yolo_model
    create_example_videos
    echo ""

    set_permissions
    install_systemd_service
    start_service
    echo ""

    print_summary
}

main "$@"
