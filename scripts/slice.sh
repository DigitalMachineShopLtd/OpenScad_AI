#!/bin/bash
# Don't use set -e

# Slicing Script — Currently a manual-step placeholder
# Usage: ./scripts/slice.sh output/stl/file.stl [--profile "Profile Name"]
#
# Slicing is skipped for now. This script validates the STL exists
# and publishes its readiness to MQTT for downstream consumers.

STL_FILE="$1"
OUTPUT_DIR="output/gcode"

# MQTT configuration
MQTT_BROKER="${MQTT_BROKER:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_TOPIC_BASE="openscad/slice"

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

if [ -z "$STL_FILE" ]; then
    echo "Usage: $0 <file.stl>"
    exit 1
fi

if [ ! -f "$STL_FILE" ]; then
    echo "Error: File not found: $STL_FILE"
    exit 1
fi

BASENAME=$(basename "$STL_FILE" .stl)

echo "================================"
echo "Slice check: $STL_FILE"

mkdir -p "$OUTPUT_DIR"

# Verify STL is valid (non-empty)
if [ ! -s "$STL_FILE" ]; then
    echo "Error: STL file is empty"
    mqtt_publish "result" "{\"file\":\"$STL_FILE\",\"status\":\"failed\",\"reason\":\"empty STL\",\"timestamp\":\"$(date -Iseconds)\"}"
    exit 1
fi

SIZE=$(du -h "$STL_FILE" | cut -f1)
echo -e "${GREEN}✓ STL ready for slicing: $STL_FILE ($SIZE)${NC}"
echo ""
echo -e "${YELLOW}Slicing is not automated yet.${NC}"
echo "  Transfer $STL_FILE to a machine with a slicer (Bambu Studio, OrcaSlicer, PrusaSlicer)."
echo ""

mqtt_publish "ready" "{\"file\":\"$STL_FILE\",\"size\":\"$SIZE\",\"basename\":\"$BASENAME\",\"timestamp\":\"$(date -Iseconds)\"}"

echo "================================"
