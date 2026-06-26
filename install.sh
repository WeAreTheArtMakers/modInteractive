#!/usr/bin/env bash
#===============================================================================
# install.sh - modInteractive Kiosk System Installer
#
# This script installs modInteractive on a Raspberry Pi system.
# It is idempotent: running it multiple times is safe.
#
# Usage:
#   chmod +x install.sh
#   sudo ./install.sh
#
# The script will:
#   1. Install system dependencies (python3-venv, mpv, etc.)
#   2. Create /opt/modInteractive directory structure
#   3. Set up Python virtual environment
#   4. Install Python dependencies
#   5. Install systemd service
#   6. (Optional) Start the service
#===============================================================================

set -euo pipefail

#===============================================================================
# Color output helpers
#===============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

#===============================================================================
# Configuration
#===============================================================================
INSTALL_DIR="/opt/modInteractive"
VENV_DIR="${INSTALL_DIR}/venv"
SERVICE_NAME="modinteractive"
SERVICE_SRC="systemd/${SERVICE_NAME}.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"
REQUIREMENTS="requirements.txt"
CONFIG_FILE="config.json"
PYTHON="python3"

#===============================================================================
# Root check
#===============================================================================
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (use sudo)."
    exit 1
fi

echo ""
echo "========================================"
echo " modInteractive Kiosk System Installer"
echo "========================================"
echo ""

#===============================================================================
# Determine the source directory
#===============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}"

info "Source directory: ${SOURCE_DIR}"
info "Install directory: ${INSTALL_DIR}"
info "Virtual environment: ${VENV_DIR}"
echo ""

#===============================================================================
# Step 1: Install system dependencies
#===============================================================================
info "Step 1/7: Installing system dependencies..."

apt-get update -qq
apt-get install -y -qq \
    "${PYTHON}" \
    "${PYTHON}-venv" \
    "${PYTHON}-pip" \
    "${PYTHON}-opencv" \
    mpv \
    udisks2 \
    dosfstools \
    2>&1 | tail -5

success "System dependencies installed"
echo ""

#===============================================================================
# Step 2: Create directory structure
#===============================================================================
info "Step 2/7: Creating directory structure..."

mkdir -p "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/logs"
mkdir -p "${INSTALL_DIR}/videos"
mkdir -p "${INSTALL_DIR}/core"

success "Directory structure created at ${INSTALL_DIR}"
echo ""

#===============================================================================
# Step 3: Copy application files
#===============================================================================
info "Step 3/7: Copying application files..."

# Main application files
cp -r "${SOURCE_DIR}/main.py"          "${INSTALL_DIR}/main.py"
cp -r "${SOURCE_DIR}/app.py"           "${INSTALL_DIR}/app.py"
cp -r "${SOURCE_DIR}/config.json"      "${INSTALL_DIR}/config.json"
cp -r "${SOURCE_DIR}/requirements.txt" "${INSTALL_DIR}/requirements.txt"

# Core modules
cp -r "${SOURCE_DIR}/core/"*.py        "${INSTALL_DIR}/core/"

# Video files (if any)
if ls "${SOURCE_DIR}/videos/"*.mp4 1>/dev/null 2>&1; then
    cp -r "${SOURCE_DIR}/videos/"*.mp4 "${INSTALL_DIR}/videos/"
    success "Video files copied"
else
    warning "No video files found in videos/. Add videos to ${INSTALL_DIR}/videos/"
fi

# Set permissions
chown -R pi:pi "${INSTALL_DIR}" 2>/dev/null || true
chmod -R 755 "${INSTALL_DIR}"

success "Application files copied"
echo ""

#===============================================================================
# Step 4: Create Python virtual environment
#===============================================================================
info "Step 4/7: Creating Python virtual environment..."

if [[ -d "${VENV_DIR}" ]]; then
    info "Virtual environment already exists, updating..."
else
    "${PYTHON}" -m venv "${VENV_DIR}"
    success "Virtual environment created"
fi

# Upgrade pip
"${VENV_DIR}/bin/pip" install --upgrade pip --quiet

success "Virtual environment ready at ${VENV_DIR}"
echo ""

#===============================================================================
# Step 5: Install Python dependencies
#===============================================================================
info "Step 5/7: Installing Python dependencies..."

cd "${INSTALL_DIR}"
"${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS}" --quiet

success "Python dependencies installed"
echo ""

#===============================================================================
# Step 6: Install systemd service
#===============================================================================
info "Step 6/7: Installing systemd service..."

# Copy service file
if [[ -f "${SOURCE_DIR}/${SERVICE_SRC}" ]]; then
    cp "${SOURCE_DIR}/${SERVICE_SRC}" "${SERVICE_DST}"
    chmod 644 "${SERVICE_DST}"

    # Update user/group in service file to current non-root user
    REAL_USER="${SUDO_USER:-pi}"
    REAL_GROUP=$(id -gn "${REAL_USER}" 2>/dev/null || echo "pi")
    REAL_UID=$(id -u "${REAL_USER}" 2>/dev/null || echo "1000")

    sed -i "s/User=pi/User=${REAL_USER}/" "${SERVICE_DST}"
    sed -i "s/Group=pi/Group=${REAL_GROUP}/" "${SERVICE_DST}"
    sed -i "s|/run/user/1000|/run/user/${REAL_UID}|" "${SERVICE_DST}"

    # Reload systemd
    systemctl daemon-reload

    # Enable service to start on boot
    systemctl enable "${SERVICE_NAME}"

    success "Systemd service installed and enabled"
    info "Service name: ${SERVICE_NAME}"
else
    warning "Service file not found: ${SOURCE_DIR}/${SERVICE_SRC}"
    warning "You will need to manually install the systemd service."
fi
echo ""

#===============================================================================
# Step 7: Verify installation
#===============================================================================
info "Step 7/7: Verifying installation..."

VERIFY_ERRORS=0

# Check virtual environment
if [[ -f "${VENV_DIR}/bin/python" ]]; then
    PYTHON_VERSION=$("${VENV_DIR}/bin/python" --version 2>&1)
    success "Python: ${PYTHON_VERSION}"
else
    error "Virtual environment Python not found!"
    VERIFY_ERRORS=1
fi

# Check main.py exists
if [[ -f "${INSTALL_DIR}/main.py" ]]; then
    success "main.py installed"
else
    error "main.py not found!"
    VERIFY_ERRORS=1
fi

# Check mpv
if command -v mpv &> /dev/null; then
    MPV_VERSION=$(mpv --version 2>&1 | head -1)
    success "mpv: ${MPV_VERSION}"
else
    warning "mpv not found in PATH"
fi

# Check systemd service
if systemctl is-enabled "${SERVICE_NAME}" &> /dev/null; then
    success "Service ${SERVICE_NAME} is enabled"
else
    warning "Service ${SERVICE_NAME} is not enabled"
fi

echo ""
echo "========================================"

if [[ ${VERIFY_ERRORS} -eq 0 ]]; then
    success "Installation completed successfully!"
else
    warning "Installation completed with ${VERIFY_ERRORS} error(s)."
fi

echo ""
info "You can now start the service with:"
info "  sudo systemctl start ${SERVICE_NAME}"
info ""
info "Check service status:"
info "  sudo systemctl status ${SERVICE_NAME}"
info ""
info "View logs:"
info "  journalctl -u ${SERVICE_NAME} -f"
info ""
info "Test the application manually:"
info "  cd ${INSTALL_DIR}"
info "  sudo -u ${REAL_USER:-pi} ${VENV_DIR}/bin/python main.py"
echo ""

exit 0