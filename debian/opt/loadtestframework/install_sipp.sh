#!/bin/bash
# SIPp Installation Script with PCAP, SCTP, OpenSSL, and GSL support
# Targets: Ubuntu/Debian-based systems

set -e

echo "Updating package lists and installing dependencies..."
apt update
apt install -y \
    build-essential \
    pkg-config \
    cmake \
    git \
    libncurses5-dev \
    libssl-dev \
    libpcap-dev \
    libnet1-dev \
    libsctp-dev \
    lksctp-tools \
    libgsl-dev \
    git

# Clone the latest version from official GitHub
echo "Cloning the latest SIPp source code..."
if [ -d "sipp" ]; then
    rm -rf sipp
fi
git clone https://github.com/SIPp/sipp.git
cd sipp

# Update submodules (required for gtest and other components)
git submodule update --init --recursive

# Configure and Build
echo "Configuring SIPp with all utility supports..."
# Flags: SSL (TLS), PCAP (media play), SCTP, and GSL (distributed pauses)
cmake . -DUSE_SSL=1 -DUSE_PCAP=1 -DUSE_SCTP=1 -DUSE_GSL=1

echo "Compiling SIPp..."
make -j$(nproc)

# Install binary to PATH
echo "Installing SIPp binary to /usr/local/bin..."
cp sipp /usr/local/bin/
