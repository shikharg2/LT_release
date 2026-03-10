#!/bin/bash
#
# build_deb.sh - Build the loadtestframework Debian package
#
# Usage: ./build_deb.sh
# Output: loadtestframework.deb in the current directory
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/debian"
INSTALL_DIR="$BUILD_DIR/opt/loadtestframework"
OUTPUT="$SCRIPT_DIR/loadtestframework.deb"

echo "=========================================="
echo " Building loadtestframework.deb"
echo "=========================================="

# ── Clean previous build artifacts in opt/ ──
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# ── Copy application files ──
echo "Copying application files..."

# Core Python files
cp "$SCRIPT_DIR/gui.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/orchestrate.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/cleanup.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/voip_test.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/Dockerfile" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/install_sipp.sh" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/setup.sh" "$INSTALL_DIR/"

# Source modules
mkdir -p "$INSTALL_DIR/src/test_modules" "$INSTALL_DIR/src/utils"
cp "$SCRIPT_DIR/src/__init__.py" "$INSTALL_DIR/src/"
cp "$SCRIPT_DIR/src/scheduler.py" "$INSTALL_DIR/src/"
cp "$SCRIPT_DIR/src/worker.py" "$INSTALL_DIR/src/"

cp "$SCRIPT_DIR/src/test_modules/__init__.py" "$INSTALL_DIR/src/test_modules/"
cp "$SCRIPT_DIR/src/test_modules/speed_test.py" "$INSTALL_DIR/src/test_modules/"
cp "$SCRIPT_DIR/src/test_modules/streaming.py" "$INSTALL_DIR/src/test_modules/"
cp "$SCRIPT_DIR/src/test_modules/voip_sipp.py" "$INSTALL_DIR/src/test_modules/"
cp "$SCRIPT_DIR/src/test_modules/web_browsing.py" "$INSTALL_DIR/src/test_modules/"

cp "$SCRIPT_DIR/src/utils/__init__.py" "$INSTALL_DIR/src/utils/"
cp "$SCRIPT_DIR/src/utils/aggregator.py" "$INSTALL_DIR/src/utils/"
cp "$SCRIPT_DIR/src/utils/config_validator.py" "$INSTALL_DIR/src/utils/"
cp "$SCRIPT_DIR/src/utils/db.py" "$INSTALL_DIR/src/utils/"
cp "$SCRIPT_DIR/src/utils/error_logger.py" "$INSTALL_DIR/src/utils/"
cp "$SCRIPT_DIR/src/utils/unit_converter.py" "$INSTALL_DIR/src/utils/"
cp "$SCRIPT_DIR/src/utils/uuid_generator.py" "$INSTALL_DIR/src/utils/"

# Configurations
mkdir -p "$INSTALL_DIR/configurations"
cp "$SCRIPT_DIR/configurations/main.json" "$INSTALL_DIR/configurations/"

# Docker SQL init
mkdir -p "$INSTALL_DIR/docker"
cp "$SCRIPT_DIR/docker/init_db.sql" "$INSTALL_DIR/docker/"

# SIPp scenarios (only XML files, not the full source repo)
mkdir -p "$INSTALL_DIR/sipp/sipp_scenarios"
cp "$SCRIPT_DIR/sipp/sipp_scenarios/"*.xml "$INSTALL_DIR/sipp/sipp_scenarios/"

# Logo / UI assets
mkdir -p "$INSTALL_DIR/logo"
cp "$SCRIPT_DIR/logo/"*.png "$INSTALL_DIR/logo/" 2>/dev/null || true

# Results directory (empty, will be created at runtime)
mkdir -p "$INSTALL_DIR/results_voip"

# ── Set permissions ──
echo "Setting permissions..."

# DEBIAN scripts must be 755
chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/DEBIAN/prerm"
chmod 755 "$BUILD_DIR/DEBIAN/postrm"

# Binaries must be 755
chmod 755 "$BUILD_DIR/usr/local/bin/loadtest"
chmod 755 "$BUILD_DIR/usr/local/bin/loadtest-cleanup"

# Application files
find "$INSTALL_DIR" -type f -name "*.py" -exec chmod 644 {} \;
find "$INSTALL_DIR" -type f -name "*.sh" -exec chmod 755 {} \;
find "$INSTALL_DIR" -type f -name "*.json" -exec chmod 644 {} \;
find "$INSTALL_DIR" -type f -name "*.xml" -exec chmod 644 {} \;
find "$INSTALL_DIR" -type f -name "*.sql" -exec chmod 644 {} \;
find "$INSTALL_DIR" -type f -name "*.txt" -exec chmod 644 {} \;
find "$INSTALL_DIR" -type d -exec chmod 755 {} \;

# ── Build the package ──
echo "Building Debian package..."
dpkg-deb --build "$BUILD_DIR" "$OUTPUT"

echo ""
echo "=========================================="
echo " Package built successfully!"
echo "=========================================="
echo " Output: $OUTPUT"
echo ""
echo " Install with:"
echo "   sudo apt install ./$( basename "$OUTPUT" )"
echo ""
