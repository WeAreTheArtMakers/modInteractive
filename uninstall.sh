#!/usr/bin/env bash
#===============================================================================
# uninstall.sh - Remove modInteractive from the system
#
# Usage:
#   sudo ./uninstall.sh
#
# This will:
#   1. Stop and disable the systemd service
#   2. Remove /opt/modInteractive directory
#===============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

INSTALL_DIR="/opt/modInteractive"
SERVICE_NAME="modinteractive"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (use sudo)."
    exit 1
fi

echo ""
echo "========================================"
echo " modInteractive Uninstaller"
echo "========================================"
echo ""

warning "This will remove modInteractive completely."
read -rp "Are you sure? (y/N): " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    info "Uninstall cancelled."
    exit 0
fi

# Stop and disable service
if systemctl is-enabled "${SERVICE_NAME}" &>/dev/null; then
    info "Stopping ${SERVICE_NAME} service..."
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    success "Service stopped and disabled"
fi

# Remove service file
if [[ -f "${SERVICE_FILE}" ]]; then
    rm -f "${SERVICE_FILE}"
    systemctl daemon-reload
    success "Service file removed"
fi

# Remove installation directory
if [[ -d "${INSTALL_DIR}" ]]; then
    rm -rf "${INSTALL_DIR}"
    success "Removed ${INSTALL_DIR}"
fi

echo ""
success "modInteractive has been uninstalled."
echo ""

exit 0