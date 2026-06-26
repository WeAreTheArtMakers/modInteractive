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
VENV_DIR="${INSTALL_DIR}/venv"
REQUIREMENTS="${INSTALL_DIR}/requirements.txt"
SERVICE_NAME="modinteractive"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON="python3"

if [[ "${EUID}" -ne 0 ]]; then
    error "This script must be run as root. Use: sudo bash install.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}"

if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    REAL_USER="${SUDO_USER}"
elif id -u pi >/dev/null 2>&1; then
    REAL_USER="pi"
else
    REAL_USER="$(awk -F: '$3 >= 1000 && $3 < 65534 { print $1; exit }' /etc/passwd)"
fi

if [[ -z "${REAL_USER}" ]]; then
    REAL_USER="root"
fi

REAL_GROUP="$(id -gn "${REAL_USER}" 2>/dev/null || echo "${REAL_USER}")"
REAL_UID="$(id -u "${REAL_USER}" 2>/dev/null || echo "0")"

echo ""
echo "========================================"
echo " modInteractive Installer"
echo " Raspberry Pi 5 Camera/PIR Triggered Display"
echo "========================================"
echo ""

info "Source: ${SOURCE_DIR}"
info "Target: ${INSTALL_DIR}"
info "Virtualenv: ${VENV_DIR}"
info "Service user: ${REAL_USER}:${REAL_GROUP}"
echo ""

info "Step 1/6: Installing system dependencies"
apt-get update
apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-opencv \
    python3-numpy \
    python3-gpiozero \
    python3-lgpio \
    mpv \
    v4l-utils
success "System dependencies installed"
echo ""

for group in audio video render input gpio; do
    if getent group "${group}" >/dev/null 2>&1; then
        usermod -a -G "${group}" "${REAL_USER}" || true
    fi
done

info "Step 2/6: Creating directory structure"
mkdir -p "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/core"
mkdir -p "${INSTALL_DIR}/admin"
mkdir -p "${INSTALL_DIR}/systemd"
mkdir -p "${INSTALL_DIR}/videos"
mkdir -p "${INSTALL_DIR}/logs"
success "Directories created"
echo ""

info "Step 3/6: Copying application files"

for required_file in main.py app.py config.json; do
    if [[ ! -f "${SOURCE_DIR}/${required_file}" ]]; then
        error "Required file missing: ${SOURCE_DIR}/${required_file}"
        exit 1
    fi
done

if [[ ! -d "${SOURCE_DIR}/core" ]]; then
    error "Required directory missing: ${SOURCE_DIR}/core"
    exit 1
fi

cp "${SOURCE_DIR}/main.py" "${INSTALL_DIR}/main.py"
cp "${SOURCE_DIR}/app.py" "${INSTALL_DIR}/app.py"
cp "${SOURCE_DIR}/config.json" "${INSTALL_DIR}/config.json"

if [[ -f "${SOURCE_DIR}/requirements.txt" ]]; then
    cp "${SOURCE_DIR}/requirements.txt" "${INSTALL_DIR}/requirements.txt"
else
    cat > "${INSTALL_DIR}/requirements.txt" <<'EOF'
flask>=2.3.0
EOF
fi

rm -rf "${INSTALL_DIR}/core"
mkdir -p "${INSTALL_DIR}/core"
cp -a "${SOURCE_DIR}/core/." "${INSTALL_DIR}/core/"

if [[ -d "${SOURCE_DIR}/admin" ]]; then
    rm -rf "${INSTALL_DIR}/admin"
    mkdir -p "${INSTALL_DIR}/admin"
    cp -a "${SOURCE_DIR}/admin/." "${INSTALL_DIR}/admin/"
else
    warning "Admin directory not found. Admin panel will be disabled."
fi

if [[ -d "${SOURCE_DIR}/videos" ]]; then
    find "${SOURCE_DIR}/videos" -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.webm" \) -exec cp -a {} "${INSTALL_DIR}/videos/" \;
fi

chown -R "${REAL_USER}:${REAL_GROUP}" "${INSTALL_DIR}" 2>/dev/null || true
find "${INSTALL_DIR}" -type d -exec chmod 755 {} \;
find "${INSTALL_DIR}" -type f -exec chmod 644 {} \;
success "Application files copied"
echo ""

info "Step 4/6: Creating Python virtual environment"

if [[ ! -d "${VENV_DIR}" ]]; then
    "${PYTHON}" -m venv --system-site-packages "${VENV_DIR}"
    success "Virtual environment created"
else
    info "Virtual environment already exists"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
success "Virtualenv ready: ${VENV_DIR}"
echo ""

info "Step 5/6: Installing Python dependencies"

if [[ -s "${REQUIREMENTS}" ]]; then
    "${VENV_DIR}/bin/python" -m pip install -r "${REQUIREMENTS}"
else
    warning "requirements.txt is empty, skipping pip install"
fi

success "Python dependencies installed"
echo ""

info "Step 6/6: Installing systemd service"

SERVICE_GROUPS=""
for group in audio video render input gpio; do
    if getent group "${group}" >/dev/null 2>&1; then
        SERVICE_GROUPS="${SERVICE_GROUPS} ${group}"
    fi
done
SERVICE_GROUPS="$(echo "${SERVICE_GROUPS}" | xargs || true)"

cat > "${SERVICE_DST}" <<EOF
[Unit]
Description=modInteractive Camera/PIR Triggered HDMI Video Display
Documentation=https://github.com/WeAreTheArtMakers/modInteractive
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=${REAL_USER}
Group=${REAL_GROUP}
SupplementaryGroups=${SERVICE_GROUPS}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/main.py
Restart=always
RestartSec=5
TimeoutStartSec=30
TimeoutStopSec=10
KillSignal=SIGINT
KillMode=control-group
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/${REAL_UID}
Environment=PATH=${VENV_DIR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

chmod 644 "${SERVICE_DST}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
success "Service installed and enabled"
echo ""

if ! find "${INSTALL_DIR}/videos" -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.avi" -o -iname "*.webm" \) | grep -q .; then
    warning "No video files found in ${INSTALL_DIR}/videos"
    warning "Add a video file as ${INSTALL_DIR}/videos/selamlama.mp4 before starting"
fi

echo ""
echo "========================================"
success "Installation completed"
echo ""
echo "Install dir: ${INSTALL_DIR}"
echo "Virtualenv:  ${VENV_DIR}"
echo "Service:     ${SERVICE_NAME}"
echo ""
info "Camera mode:"
echo "sudo systemctl restart ${SERVICE_NAME}"
echo ""
info "PIR mode:"
echo "cd ${INSTALL_DIR}"
echo "sudo -u ${REAL_USER} ${VENV_DIR}/bin/python main.py --source pir --check"
echo "Set config.json trigger.source to pir or run: ${VENV_DIR}/bin/python main.py --source pir"
echo ""
info "Status:"
echo "sudo systemctl status ${SERVICE_NAME}"
echo "journalctl -u ${SERVICE_NAME} -f"
echo ""
info "Admin panel:"
echo "http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080"
echo ""

exit 0
