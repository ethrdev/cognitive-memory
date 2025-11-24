#!/bin/bash
#
# Cognitive Memory MCP Server - Systemd Service Installation Script
#
# This script installs the MCP Server as a systemd service for auto-start
# and crash recovery.
#
# Usage: sudo bash scripts/install_service.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Cognitive Memory MCP Server - Service Installation${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Define paths - detect project root dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_FILE="$PROJECT_ROOT/systemd/cognitive-memory-mcp.service"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="cognitive-memory-mcp.service"

echo "Project root detected: $PROJECT_ROOT"
echo

echo "1. Verifying service file exists..."
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}Error: Service file not found at $SERVICE_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}   ✓ Service file found${NC}"

echo
echo "2. Validating service file syntax..."
# Note: systemd-analyze verify requires the file to be in /etc/systemd/system
# So we'll copy first, then verify, and remove if verification fails
cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME"

if systemd-analyze verify "$SERVICE_NAME" 2>&1 | grep -i "error"; then
    echo -e "${RED}   ✗ Service file validation failed${NC}"
    rm "$SYSTEMD_DIR/$SERVICE_NAME"
    exit 1
fi
echo -e "${GREEN}   ✓ Service file syntax valid${NC}"

echo
echo "3. Installing service file to $SYSTEMD_DIR..."
# File already copied above, just confirm
echo -e "${GREEN}   ✓ Service file installed${NC}"

echo
echo "4. Reloading systemd daemon..."
if ! systemctl daemon-reload 2>/dev/null; then
    echo -e "${YELLOW}   ⚠ Systemd not available in this environment${NC}"
    echo -e "${YELLOW}   ⚠ Service file installed but cannot be started${NC}"
    echo -e "${YELLOW}   ⚠ This is normal in containers or WSL without systemd${NC}"
    echo
    echo -e "${GREEN}Service file installed successfully at:${NC}"
    echo "  $SYSTEMD_DIR/$SERVICE_NAME"
    echo
    echo "To use this service, run this script in an environment with systemd."
    exit 0
fi
echo -e "${GREEN}   ✓ Systemd daemon reloaded${NC}"

echo
echo "5. Enabling service for auto-start..."
systemctl enable $SERVICE_NAME
echo -e "${GREEN}   ✓ Service enabled for auto-start${NC}"

echo
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo
echo "Service Management Commands:"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Restart: sudo systemctl restart $SERVICE_NAME"
echo "  Status:  systemctl status $SERVICE_NAME"
echo "  Logs:    journalctl -u $SERVICE_NAME -f"
echo
echo -e "${YELLOW}Note: The service is enabled but not started.${NC}"
echo -e "${YELLOW}Use 'sudo systemctl start $SERVICE_NAME' to start it now.${NC}"
echo
