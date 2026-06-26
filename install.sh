#!/usr/bin/env bash
#===============================================================================
# install.sh - modInteractive Installer for Raspberry Pi
#
# Usage:
#   chmod +x install.sh
#   sudo ./install.sh
#
# This script is idempotent: running it multiple times is safe.
#
# It installs:
#   - System packages: python3, python3-venv, python3-opencv, python3-numpy, mpv, v4l-utils
#   - Virtual environment at /opt/modInteractive/venv (with --system-site-packages)
#   - Python dependencies from requirements.txt
#   - Systemd service (enabled but not started)
#===============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Configuration
INSTALL_DIR="/opt/modInteractive"
VENV_DIR="${INSTALL_DIR}/venv"
REQUIREMENTS="${INSTALL_DIR}/requirements.txt"
SERVICE_NAME="modinteractive"
SERVICE_SRC="systemd/${SERVICE_NAME}.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON="python3"

# Root check
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (use sudo)."
    exit 1
fi

echo ""
echo "========================================"
echo " modInteractive Installer"
echo " Raspberry Pi Motion Triggered Display"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}"

info "Source: ${SOURCE_DIR}"
info "Target: ${INSTALL_DIR}"
info "Virtualenv: ${VENV_DIR}"
echo ""

#------------------------------------------------------------------------------
# Step 1: Install system dependencies
#------------------------------------------------------------------------------
info "Step 1/6: Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    "${PYTHON}" \
    "${PYTHON}-venv" \
    "${PYTHON}-pip" \
    "${PYTHON}-opencv" \
    "${PYTHON}-numpy" \
    mpv \
    v4l-utils \
    2>&1 | tail -3
success "System dependencies installed"
echo ""

#------------------------------------------------------------------------------
# Step 2: Create directory structure
#------------------------------------------------------------------------------
info "Step 2/6: Creating directory structure..."
mkdir -p "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/core"
mkdir -p "${INSTALL_DIR}/admin/templates"
mkdir -p "${INSTALL_DIR}/admin/static"
mkdir -p "${INSTALL_DIR}/systemd"
mkdir -p "${INSTALL_DIR}/videos"
mkdir -p "${INSTALL_DIR}/logs"
success "Directories created"
echo ""

#------------------------------------------------------------------------------
# Step 3: Copy application files
#------------------------------------------------------------------------------
info "Step 3/6: Copying application files..."

# Python files
cp "${SOURCE_DIR}/main.py"              "${INSTALL_DIR}/main.py"
cp "${SOURCE_DIR}/app.py"               "${INSTALL_DIR}/app.py"
cp "${SOURCE_DIR}/config.json"          "${INSTALL_DIR}/config.json"
cp "${SOURCE_DIR}/requirements.txt"     "${INSTALL_DIR}/requirements.txt"

# Core modules
for pyfile in "${SOURCE_DIR}/core/"*.py; do
    cp "${pyfile}" "${INSTALL_DIR}/core/"
done

# Admin panel
if [[ -d "${SOURCE_DIR}/admin" ]]; then
    cp -r "${SOURCE_DIR}/admin/"* "${INSTALL_DIR}/admin/"
fi

# Systemd service file (to both service dir and local copy)
if [[ -f "${SOURCE_DIR}/${SERVICE_SRC}" ]]; then
    cp "${SOURCE_DIR}/${SERVICE_SRC}" "${INSTALL_DIR}/systemd/"
fi

# Video files
if ls "${SOURCE_DIR}/videos/"*.mp4 1>/dev/null 2>&1; then
    cp "${SOURCE_DIR}/videos/"*.mp4 "${INSTALL_DIR}/videos/"
fi

# Set ownership
REAL_USER="${SUDO_USER:-pi}"
chown -R "${REAL_USER}":"${REAL_USER}" "${INSTALL_DIR}" 2>/dev/null || true
chmod -R 755 "${INSTALL_DIR}"

success "Application files copied"
echo ""

#------------------------------------------------------------------------------
# Step 4: Create Python virtual environment with system-site-packages
#------------------------------------------------------------------------------
info "Step 4/6: Creating Python virtual environment..."

if [[ -d "${VENV_DIR}" ]]; then
    info "Virtual environment exists, skipping creation"
else
    "${PYTHON}" -m venv --system-site-packages "${VENV_DIR}"
    success "Virtual environment created with --system-site-packages"
fi

# Upgrade pip
"${VENV_DIR}/bin/pip" install --upgrade pip --quiet

success "Virtualenv: ${VENV_DIR}"
echo ""

#------------------------------------------------------------------------------
# Step 5: Install Python dependencies
#------------------------------------------------------------------------------
info "Step 5/6: Installing Python dependencies..."
cd "${INSTALL_DIR}"
"${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS}" --quiet
success "Python dependencies installed"
echo ""

#------------------------------------------------------------------------------
# Step 6: Install systemd service (enabled but NOT started)
#------------------------------------------------------------------------------
info "Step 6/6: Installing systemd service..."

if [[ -f "${SOURCE_DIR}/${SERVICE_SRC}" ]]; then
    cp "${SOURCE_DIR}/${SERVICE_SRC}" "${SERVICE_DST}"
    chmod 644 "${SERVICE_DST}"

    # Update user/group in service file
    REAL_USER="${SUDO_USER:-pi}"
    REAL_GROUP=$(id -gn "${REAL_USER}" 2>/dev/null || echo "pi")
    REAL_UID=$(id -u "${REAL_USER}" 2>/dev/null || echo "1000")

    sed -i "s/User=pi/User=${REAL_USER}/" "${SERVICE_DST}"
    sed -i "s/Group=pi/Group=${REAL_GROUP}/" "${SERVICE_DST}"
    sed -i "s|/run/user/1000|/run/user/${REAL_UID}|" "${SERVICE_DST}"

    # Fix virtualenv path if .venv was used (ensure consistency)
    sed -i "s|/opt/modInteractive/.venv|${VENV_DIR}|g" "${SERVICE_DST}"

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"

    success "Service ${SERVICE_NAME} installed and enabled"
    info "Start it with: sudo systemctl start ${SERVICE_NAME}"
else
    warning "Service file not found: ${SOURCE_DIR}/${SERVICE_SRC}"
fi
echo ""

#------------------------------------------------------------------------------
# Check for video file
#------------------------------------------------------------------------------
if ! ls "${INSTALL_DIR}/videos/"*.mp4 1>/dev/null 2>&1; then
    warning "No video files found in ${INSTALL_DIR}/videos/"
    warning "Add a greeting video before starting the service:"
    warning "  cp your_video.mp4 ${INSTALL_DIR}/videos/selamlama.mp4"
    warning "  sudo chown -R ${REAL_USER:-pi}:${REAL_USER:-pi} ${INSTALL_DIR}/videos/"
fi

#------------------------------------------------------------------------------
# Summary
#------------------------------------------------------------------------------
echo ""
echo "========================================"
success "Installation completed!"
echo ""
echo "  Install dir:  ${INSTALL_DIR}"
echo "  Virtualenv:   ${VENV_DIR}"
echo "  Service:      ${SERVICE_NAME}"
echo ""
info "Next steps:"
info "  1. Add a video file:"
info "     cp your_video.mp4 ${INSTALL_DIR}/videos/selamlama.mp4"
info "     sudo chown -R ${REAL_USER:-pi}:${REAL_USER:-pi} ${INSTALL_DIR}/videos/"
info ""
info "  2. Test the application:"
info "     sudo -u ${REAL_USER:-pi} ${VENV_DIR}/bin/python ${INSTALL_DIR}/main.py --check"
info ""
info "  3. Start the service:"
info "     sudo systemctl start ${SERVICE_NAME}"
info ""
info "  4. Check status:"
info "     sudo systemctl status ${SERVICE_NAME}"
info ""
info "  5. View logs:"
info "     journalctl -u ${SERVICE_NAME} -f"
echo ""
info "  6. Admin panel (if enabled):"
info "     http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080"
echo ""

exit 0