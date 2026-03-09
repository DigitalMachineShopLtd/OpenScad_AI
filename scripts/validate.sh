#!/bin/bash
# Don't use set -e - conflicts with || FAILED=1 pattern

# OpenSCAD BOSL2 Design Validation Script
# Usage: ./scripts/validate.sh designs/path/to/file.scad

# Cross-platform OpenSCAD detection (prefer local AppImage)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -x "${PROJECT_DIR}/bin/OpenSCAD-latest.AppImage" ]; then
    OPENSCAD="${PROJECT_DIR}/bin/OpenSCAD-latest.AppImage"
elif command -v openscad >/dev/null 2>&1; then
    OPENSCAD="openscad"
elif [ -x "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD" ]; then
    OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
else
    echo "Error: OpenSCAD not found. Run ./scripts/setup.sh for install instructions."
    exit 1
fi

# Headless rendering support (Linux without display)
if [ -z "$DISPLAY" ] && command -v xvfb-run >/dev/null 2>&1; then
    OPENSCAD="xvfb-run -a $OPENSCAD"
fi

DESIGN_FILE="$1"

# MQTT configuration
MQTT_BROKER="${MQTT_BROKER:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_TOPIC_BASE="openscad/validate"

mqtt_publish() {
    local subtopic="$1"
    local payload="$2"
    if command -v mosquitto_pub >/dev/null 2>&1; then
        mosquitto_pub -h "$MQTT_BROKER" -p "$MQTT_PORT" \
            -t "${MQTT_TOPIC_BASE}/${subtopic}" \
            -m "$payload" 2>/dev/null &
    fi
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup handler
TEMP_FILES=()
cleanup() {
    rm -f "${TEMP_FILES[@]}" 2>/dev/null
}
trap cleanup EXIT INT TERM

# Usage and validation checks
if [ -z "$DESIGN_FILE" ]; then
    echo "Usage: $0 <design-file.scad>"
    exit 1
fi

if [ ! -f "$DESIGN_FILE" ]; then
    echo -e "${RED}Error: File not found: $DESIGN_FILE${NC}"
    exit 1
fi

echo "Validating: $DESIGN_FILE"
echo "================================"
mqtt_publish "started" "{\"file\":\"$DESIGN_FILE\",\"timestamp\":\"$(date -Iseconds)\"}"

# Syntax check function
validate_syntax() {
    echo -n "Checking syntax... "

    # Try to compile without rendering (use temp file — /dev/null lacks suffix)
    local SYNTAX_TMP
    SYNTAX_TMP=$(mktemp /tmp/syntax_XXXXXX.stl)
    TEMP_FILES+=("$SYNTAX_TMP")
    if $OPENSCAD -o "$SYNTAX_TMP" "$DESIGN_FILE" 2>&1 | grep -q "ERROR\|WARNING"; then
        echo -e "${RED}FAILED${NC}"
        local errors
        errors=$($OPENSCAD -o "$SYNTAX_TMP" "$DESIGN_FILE" 2>&1 | grep "ERROR\|WARNING")
        echo "$errors"
        mqtt_publish "syntax" "{\"status\":\"failed\",\"errors\":\"$(echo "$errors" | head -5 | tr '\n' ' ')\"}"
        return 1
    else
        echo -e "${GREEN}OK${NC}"
        mqtt_publish "syntax" "{\"status\":\"passed\"}"
        return 0
    fi
}

# STL export validation
validate_stl_export() {
    echo -n "Checking STL export... "

    TEMP_STL=$(mktemp /tmp/validate_XXXXXX.stl)
    TEMP_FILES+=("$TEMP_STL")

    if $OPENSCAD -o "$TEMP_STL" "$DESIGN_FILE" 2>&1 | grep -q "ERROR"; then
        echo -e "${RED}FAILED${NC}"
        mqtt_publish "export" "{\"status\":\"failed\"}"
        return 1
    else
        if [ -f "$TEMP_STL" ] && [ -s "$TEMP_STL" ]; then
            echo -e "${GREEN}OK${NC}"
            mqtt_publish "export" "{\"status\":\"passed\"}"
            return 0
        else
            echo -e "${RED}FAILED (empty output)${NC}"
            mqtt_publish "export" "{\"status\":\"failed\",\"reason\":\"empty output\"}"
            return 1
        fi
    fi
}

# Manifold check
check_manifold() {
    echo -n "Checking manifold geometry... "

    # OpenSCAD will warn about non-manifold edges in stderr
    TEMP_STL=$(mktemp /tmp/manifold_XXXXXX.stl)
    TEMP_FILES+=("$TEMP_STL")
    OUTPUT=$($OPENSCAD -o "$TEMP_STL" "$DESIGN_FILE" 2>&1)

    if echo "$OUTPUT" | grep -q "WARNING: Object may not be a valid 2-manifold"; then
        echo -e "${YELLOW}WARNING: Non-manifold geometry detected${NC}"
        echo "  This may cause slicing issues. Review your model."
        mqtt_publish "manifold" "{\"status\":\"warning\",\"message\":\"non-manifold geometry\"}"
        return 0  # Warning, not error
    else
        echo -e "${GREEN}OK${NC}"
        mqtt_publish "manifold" "{\"status\":\"passed\"}"
        return 0
    fi
}

# Run validations
FAILED=0

validate_syntax || FAILED=1
validate_stl_export || FAILED=1
check_manifold || FAILED=1

echo "================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All validations passed!${NC}"
    mqtt_publish "result" "{\"file\":\"$DESIGN_FILE\",\"status\":\"passed\",\"timestamp\":\"$(date -Iseconds)\"}"
    exit 0
else
    echo -e "${RED}Validation failed. Fix errors before printing.${NC}"
    mqtt_publish "result" "{\"file\":\"$DESIGN_FILE\",\"status\":\"failed\",\"timestamp\":\"$(date -Iseconds)\"}"
    exit 1
fi
