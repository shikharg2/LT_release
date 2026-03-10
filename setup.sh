#!/bin/bash
#
# setup.sh - LoadTest Framework first-time setup
#
# Installs Docker, Python venv + deps, Playwright, SIPp, and builds the Docker image.
# Must be run as root (sudo loadtest --setup).
#

set -e

INSTALL_DIR="/opt/loadtestframework"
VENV_DIR="$INSTALL_DIR/.venv"
SETUP_MARKER="$INSTALL_DIR/.setup_complete"

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: Setup must be run as root."
    echo "Usage: sudo loadtest --setup"
    exit 1
fi

# Check if already set up
if [ -f "$SETUP_MARKER" ]; then
    echo "Setup has already been completed."
    echo "To force re-setup, remove $SETUP_MARKER and run again."
    exit 0
fi

echo "=========================================="
echo " LoadTest Framework - First-Time Setup"
echo "=========================================="

# ── 1. Install Docker Engine (official method) ──
echo ""
echo "[1/6] Installing Docker Engine..."

# Remove conflicting packages (ignore errors if not installed)
apt-get remove -y docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc 2>/dev/null || true

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add the Docker repository to Apt sources
tee /etc/apt/sources.list.d/docker.sources > /dev/null <<DOCKEREOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
DOCKEREOF

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo "  Docker Engine installed successfully."

# ── 2. Create Python virtual environment ──
echo ""
echo "[2/6] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
echo "  Virtual environment created at $VENV_DIR"

# ── 3. Install Python dependencies ──
echo ""
echo "[3/6] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo "  Python dependencies installed."

# ── 4. Install Playwright browsers ──
echo ""
echo "[4/6] Installing Playwright browsers..."
"$VENV_DIR/bin/python3" -m playwright install chromium
"$VENV_DIR/bin/python3" -m playwright install-deps chromium
echo "  Playwright browsers installed."

# ── 5. Build SIPp from source ──
echo ""
echo "[5/6] Building SIPp from source..."
SIPP_BUILD_DIR=$(mktemp -d)
cd "$SIPP_BUILD_DIR"

git clone https://github.com/SIPp/sipp.git
cd sipp
git submodule update --init --recursive

cmake . -DUSE_SSL=1 -DUSE_PCAP=1 -DUSE_SCTP=1 -DUSE_GSL=1
make -j$(nproc)
cp sipp /usr/local/bin/sipp
chmod +x /usr/local/bin/sipp

cd /
rm -rf "$SIPP_BUILD_DIR"
echo "  SIPp installed to /usr/local/bin/sipp"

# ── 6. Build Docker image & setup ──
echo ""
echo "[6/6] Setting up Docker..."

# Ensure Docker daemon is running
if ! systemctl is-active --quiet docker 2>/dev/null; then
    echo "  Starting Docker daemon..."
    systemctl start docker || true
    sleep 2
fi

# Add the invoking user to the docker group
if [ -n "$SUDO_USER" ]; then
    usermod -aG docker "$SUDO_USER" 2>/dev/null || true
    echo "  Added user '$SUDO_USER' to docker group."
    echo "  NOTE: Log out and back in for docker group changes to take effect."
fi

# Initialize Docker Swarm
echo "  Initializing Docker Swarm..."
if ! docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
    docker swarm init --advertise-addr 127.0.0.1
    echo "  Docker Swarm initialized."
else
    echo "  Docker Swarm already active."
fi

# Create the overlay network
echo "  Creating loadtest-network..."
if ! docker network ls --format '{{.Name}}' | grep -q '^loadtest-network$'; then
    docker network create --driver overlay --attachable loadtest-network
    echo "  Network 'loadtest-network' created."
else
    echo "  Network 'loadtest-network' already exists."
fi

# Build the loadtest Docker image
echo "  Building loadtest Docker image (this may take a few minutes)..."
docker build -t loadtest:latest "$INSTALL_DIR/"
echo "  Docker image 'loadtest:latest' built successfully."

# ── Mark setup as complete ──
touch "$SETUP_MARKER"

echo ""
echo "=========================================="
echo " LoadTest Framework setup complete!"
echo "=========================================="
echo ""
echo " Usage:"
echo "   loadtest              - Launch the GUI"
echo "   loadtest config.json  - Run in CLI mode"
echo "   loadtest-cleanup      - Clean up Docker resources"
echo "   loadtest-cleanup --remove  - Full uninstall"
echo ""

exit 0
