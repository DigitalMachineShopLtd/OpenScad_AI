#!/bin/bash
# OpenScad_AI Environment Setup & Dependency Check
# Usage: ./scripts/setup.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
OPENSCAD=""

echo "OpenScad_AI — Environment Check"
echo "================================"

# 1. OpenSCAD (prefer local AppImage)
echo -n "OpenSCAD............. "
if [ -x "${PROJECT_DIR}/bin/OpenSCAD-latest.AppImage" ]; then
    OPENSCAD="${PROJECT_DIR}/bin/OpenSCAD-latest.AppImage"
    VERSION=$(xvfb-run -a "$OPENSCAD" --version 2>&1 | head -1)
    echo -e "${GREEN}$VERSION (AppImage)${NC}"
elif command -v openscad >/dev/null 2>&1; then
    OPENSCAD="openscad"
    VERSION=$(openscad --version 2>&1 | head -1)
    echo -e "${YELLOW}$VERSION (system — consider using AppImage for latest)${NC}"
elif [ -x "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD" ]; then
    OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    echo -e "${GREEN}Found (macOS app)${NC}"
else
    echo -e "${RED}NOT INSTALLED${NC}"
    echo "  Download AppImage to bin/OpenSCAD-latest.AppImage from https://files.openscad.org/snapshots/"
    FAILED=1
fi

# 2. BOSL2 Library
echo -n "BOSL2 Library........ "
BOSL2_PATHS=(
    "$HOME/.local/share/OpenSCAD/libraries/BOSL2"
    "$HOME/Documents/OpenSCAD/libraries/BOSL2"
    "/usr/share/openscad/libraries/BOSL2"
)
BOSL2_FOUND=0
for p in "${BOSL2_PATHS[@]}"; do
    if [ -d "$p" ] && [ -f "$p/std.scad" ]; then
        echo -e "${GREEN}$p${NC}"
        BOSL2_FOUND=1
        break
    fi
done
if [ $BOSL2_FOUND -eq 0 ]; then
    echo -e "${RED}NOT FOUND${NC}"
    echo "  Install: git clone https://github.com/BelfrySCAD/BOSL2.git ~/.local/share/OpenSCAD/libraries/BOSL2"
    FAILED=1
fi

# 3. xvfb (headless rendering)
echo -n "xvfb-run (headless).. "
if command -v xvfb-run >/dev/null 2>&1; then
    echo -e "${GREEN}Available${NC}"
else
    if [ -z "$DISPLAY" ]; then
        echo -e "${RED}NOT INSTALLED (needed for headless)${NC}"
        echo "  Install: sudo apt-get install xvfb"
        FAILED=1
    else
        echo -e "${YELLOW}Not installed (not needed — display available)${NC}"
    fi
fi

# 4. MQTT client
echo -n "mosquitto_pub (MQTT). "
if command -v mosquitto_pub >/dev/null 2>&1; then
    echo -e "${GREEN}Available${NC}"
else
    echo -e "${YELLOW}Not installed (MQTT publishing disabled)${NC}"
    echo "  Install: sudo apt-get install mosquitto-clients"
fi

# 5. Directory structure
echo -n "Output directories... "
mkdir -p "${PROJECT_DIR}/output/stl" "${PROJECT_DIR}/output/png" "${PROJECT_DIR}/output/gcode" 2>/dev/null
echo -e "${GREEN}OK${NC}"

# 6. Script permissions
echo -n "Script permissions... "
chmod +x "${SCRIPT_DIR}"/*.sh 2>/dev/null
echo -e "${GREEN}OK${NC}"

# 7. Quick compile test
echo -n "BOSL2 compile test... "
if [ $BOSL2_FOUND -eq 1 ] && [ -n "$OPENSCAD" ]; then
    TEST_FILE=$(mktemp /tmp/bosl2_test_XXXXXX.scad)
    echo 'include <BOSL2/std.scad>; cuboid([10,10,10]);' > "$TEST_FILE"
    if [ -z "$DISPLAY" ] && command -v xvfb-run >/dev/null 2>&1; then
        TEST_OUTPUT=$(timeout 30 xvfb-run -a "$OPENSCAD" -o /tmp/bosl2_test_out.stl "$TEST_FILE" 2>&1)
    else
        TEST_OUTPUT=$(timeout 30 "$OPENSCAD" -o /tmp/bosl2_test_out.stl "$TEST_FILE" 2>&1)
    fi
    RESULT=$?
    rm -f "$TEST_FILE" /tmp/bosl2_test_out.stl
    if [ $RESULT -eq 0 ]; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED${NC}"
        echo "  $TEST_OUTPUT"
        FAILED=1
    fi
else
    echo -e "${YELLOW}Skipped (missing dependencies)${NC}"
fi

echo "================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed. Ready to design.${NC}"
    exit 0
else
    echo -e "${RED}Some checks failed. Fix the issues above.${NC}"
    exit 1
fi
