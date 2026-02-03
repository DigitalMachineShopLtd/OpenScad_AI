#!/bin/bash
# Don't use set -e - conflicts with error handling

# OpenSCAD High-Quality STL Rendering Script
# Usage: ./scripts/render.sh designs/path/to/file.scad

OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
DESIGN_FILE="$1"
OUTPUT_DIR="output/stl"
PNG_DIR="output/png"

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
    ERROR_OUTPUT=$("$OPENSCAD" \
        --render \
        -o "$OUTPUT_FILE" \
        "$DESIGN_FILE" 2>&1)
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ] && [ -f "$OUTPUT_FILE" ] && [ -s "$OUTPUT_FILE" ]; then
        SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo -e "${GREEN}✓ STL created: $OUTPUT_FILE ($SIZE)${NC}"
        return 0
    else
        echo "Error: Failed to create STL"
        if [ -n "$ERROR_OUTPUT" ]; then
            echo "$ERROR_OUTPUT" | grep -i "error\|warning"
        fi
        return 1
    fi
}

render_png() {
    echo "Rendering preview image..."

    OUTPUT_FILE="${PNG_DIR}/${BASENAME}.png"

    "$OPENSCAD" \
        --render \
        --imgsize=1024,768 \
        --colorscheme=Tomorrow \
        --view=axes,scales \
        -o "$OUTPUT_FILE" \
        "$DESIGN_FILE"

    if [ -f "$OUTPUT_FILE" ]; then
        echo -e "${GREEN}✓ Preview created: $OUTPUT_FILE${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Preview creation failed (non-critical)${NC}"
        return 0
    fi
}

echo "Rendering: $DESIGN_FILE"
echo "================================"

mkdir -p "$OUTPUT_DIR" "$PNG_DIR"

if render_stl; then
    render_png  # Non-critical, always continue
    echo "================================"
    echo -e "${GREEN}Rendering complete!${NC}"
    echo "STL: ${OUTPUT_DIR}/${BASENAME}.stl"
    if [ -f "${PNG_DIR}/${BASENAME}.png" ]; then
        echo "PNG: ${PNG_DIR}/${BASENAME}.png"
    fi
    exit 0
else
    echo "Rendering failed"
    exit 1
fi
