#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

INSTALL_DIR="/opt/modInteractive"
SERVICE_NAME="modinteractive"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "${EUID}" -ne 0 ]]; then
    error "This script must be run as root. Use: sudo bash uninstall.sh"
    exit 1
fi

echo ""
echo "========================================"
echo " modInteractive Uninstaller"
echo "========================================"
echo ""

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    info "Stopping service"
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true

    info "Disabling service"
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
fi

if [[ -f "${SERVICE_FILE}" ]]; then
    info "Removing service file"
    rm -f "${SERVICE_FILE}"
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
    success "Service removed"
else
    warning "Service file not found"
fi

if [[ -d "${INSTALL_DIR}" ]]; then
    warning "Application directory exists: ${INSTALL_DIR}"
    read -r -p "Remove ${INSTALL_DIR}? [y/N] " answer

    case "${answer}" in
        y|Y|yes|YES)
            rm -rf "${INSTALL_DIR}"
            success "Application directory removed"
            ;;
        *)
            info "Application directory kept"
            ;;
    esac
else
    warning "Application directory not found"
fi

echo ""
success "Uninstall completed"
echo ""

exit 0
