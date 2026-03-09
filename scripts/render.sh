#!/bin/bash
# Don't use set -e - conflicts with error handling

# OpenSCAD High-Quality STL Rendering Script
# Usage: ./scripts/render.sh designs/path/to/file.scad

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
OPENSCAD_PNG="$OPENSCAD"
if [ -z "$DISPLAY" ] && command -v xvfb-run >/dev/null 2>&1; then
    OPENSCAD="xvfb-run -a $OPENSCAD"
    OPENSCAD_PNG="$OPENSCAD"  # PNG needs display too
fi

DESIGN_FILE="$1"
OUTPUT_DIR="output/stl"
PNG_DIR="output/png"

# MQTT configuration
MQTT_BROKER="${MQTT_BROKER:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_TOPIC_BASE="openscad/render"

mqtt_publish() {
    local subtopic="$1"
    local payload="$2"
    if command -v mosquitto_pub >/dev/null 2>&1; then
        mosquitto_pub -h "$MQTT_BROKER" -p "$MQTT_PORT" \
            -t "${MQTT_TOPIC_BASE}/${subtopic}" \
            -m "$payload" 2>/dev/null &
    fi
}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "$DESIGN_FILE" ]; then
    echo "Usage: $0 <design-file.scad>"
    exit 1
fi

if [ ! -f "$DESIGN_FILE" ]; then
    echo "Error: File not found: $DESIGN_FILE"
    exit 1
fi

# Extract filename without path and extension
BASENAME=$(basename "$DESIGN_FILE" .scad)

render_stl() {
    echo "Rendering STL (high quality)..."

    OUTPUT_FILE="${OUTPUT_DIR}/${BASENAME}.stl"

    # High-quality render settings
    # --render for full geometry (not preview)
    ERROR_OUTPUT=$($OPENSCAD \
        --render \
        -o "$OUTPUT_FILE" \
        "$DESIGN_FILE" 2>&1)
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ] && [ -f "$OUTPUT_FILE" ] && [ -s "$OUTPUT_FILE" ]; then
        SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo -e "${GREEN}✓ STL created: $OUTPUT_FILE ($SIZE)${NC}"
        mqtt_publish "stl" "{\"file\":\"$OUTPUT_FILE\",\"size\":\"$SIZE\",\"status\":\"success\"}"
        return 0
    else
        echo "Error: Failed to create STL"
        if [ -n "$ERROR_OUTPUT" ]; then
            echo "$ERROR_OUTPUT" | grep -i "error\|warning"
        fi
        mqtt_publish "stl" "{\"file\":\"$DESIGN_FILE\",\"status\":\"failed\"}"
        return 1
    fi
}

render_png() {
    echo "Rendering preview image..."

    OUTPUT_FILE="${PNG_DIR}/${BASENAME}.png"

    $OPENSCAD_PNG \
        --render \
        --imgsize=1024,768 \
        --colorscheme=Tomorrow \
        --view=axes,scales \
        -o "$OUTPUT_FILE" \
        "$DESIGN_FILE" 2>&1

    if [ -f "$OUTPUT_FILE" ]; then
        echo -e "${GREEN}✓ Preview created: $OUTPUT_FILE${NC}"
        mqtt_publish "png" "{\"file\":\"$OUTPUT_FILE\",\"status\":\"success\"}"
        return 0
    else
        echo -e "${YELLOW}⚠ Preview creation failed (non-critical)${NC}"
        mqtt_publish "png" "{\"status\":\"failed\",\"reason\":\"non-critical\"}"
        return 0
    fi
}

echo "Rendering: $DESIGN_FILE"
echo "================================"
mqtt_publish "started" "{\"file\":\"$DESIGN_FILE\",\"timestamp\":\"$(date -Iseconds)\"}"

mkdir -p "$OUTPUT_DIR" "$PNG_DIR"

if render_stl; then
    render_png  # Non-critical, always continue
    echo "================================"
    echo -e "${GREEN}Rendering complete!${NC}"
    echo "STL: ${OUTPUT_DIR}/${BASENAME}.stl"
    if [ -f "${PNG_DIR}/${BASENAME}.png" ]; then
        echo "PNG: ${PNG_DIR}/${BASENAME}.png"
    fi
    mqtt_publish "result" "{\"file\":\"$DESIGN_FILE\",\"status\":\"success\",\"timestamp\":\"$(date -Iseconds)\"}"
    exit 0
else
    echo "Rendering failed"
    mqtt_publish "result" "{\"file\":\"$DESIGN_FILE\",\"status\":\"failed\",\"timestamp\":\"$(date -Iseconds)\"}"
    exit 1
fi
