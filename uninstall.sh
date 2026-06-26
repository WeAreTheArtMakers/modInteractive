#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# modInteractive Uninstaller
# Removes the AI-Powered Kiosk System from Raspberry Pi 5
# =============================================================================

INSTALL_DIR="/opt/modInteractive"
SERVICE_NAME="modinteractive.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

confirm_removal() {
    echo ""
    echo "============================================================"
    echo -e "${RED}  WARNING: This will completely remove modInteractive${NC}"
    echo "============================================================"
    echo ""
    echo "  The following will be deleted:"
    echo "    - ${INSTALL_DIR} (all files, logs, models, videos)"
    echo "    - ${SERVICE_FILE} (systemd service)"
    echo ""
    echo -n "Are you sure you want to proceed? [y/N] "
    read -r confirm

    if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
        echo ""
        log_info "Uninstall cancelled by user"
        exit 0
    fi
    echo ""
    log_info "Proceeding with uninstall..."
}

# ---------------------------------------------------------------------------
# Stop and disable systemd service
# ---------------------------------------------------------------------------
stop_and_disable_service() {
    if systemctl is-enabled "${SERVICE_NAME}" &>/dev/null 2>&1; then
        log_info "Stopping and disabling ${SERVICE_NAME}..."

        systemctl stop "${SERVICE_NAME}" 2>/dev/null || log_warn "Service was not running"
        systemctl disable "${SERVICE_NAME}" 2>/dev/null || log_warn "Service was not enabled"

        log_ok "Service stopped and disabled"
    else
        log_info "Service ${SERVICE_NAME} is not installed or enabled"
    fi
}

# ---------------------------------------------------------------------------
# Remove systemd service file
# ---------------------------------------------------------------------------
remove_service_file() {
    if [[ -f "${SERVICE_FILE}" ]]; then
        log_info "Removing service file: ${SERVICE_FILE}"
        rm -f "${SERVICE_FILE}"
        systemctl daemon-reload
        log_ok "Service file removed"
    else
        log_info "Service file not found at ${SERVICE_FILE}"
    fi
}

# ---------------------------------------------------------------------------
# Remove installation directory
# ---------------------------------------------------------------------------
remove_install_dir() {
    if [[ -d "${INSTALL_DIR}" ]]; then
        log_info "Removing installation directory: ${INSTALL_DIR}"
        rm -rf "${INSTALL_DIR}"
        log_ok "Installation directory removed"
    else
        log_info "Installation directory not found at ${INSTALL_DIR}"
    fi
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo "============================================================"
    echo -e "${GREEN}  modInteractive has been uninstalled${NC}"
    echo "============================================================"
    echo ""
    echo "  Removed:"
    echo "    - ${SERVICE_FILE}"
    echo "    - ${INSTALL_DIR}"
    echo ""
    echo "  Note: System packages (mpv, python3, etc.) were NOT removed."
    echo "  To remove them manually:"
    echo "    sudo apt-get remove mpv python3-pip python3-venv"
    echo ""
    echo "============================================================"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "  modInteractive Uninstaller"
    echo "============================================================"
    echo ""

    check_root
    confirm_removal

    stop_and_disable_service
    remove_service_file
    remove_install_dir

    print_summary
}

main "$@"
