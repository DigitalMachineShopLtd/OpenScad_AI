#!/bin/bash
# Don't use set -e

# TODO: Full automation requires Bambu Studio profile export
# TODO: Add profile management commands
# TODO: Add automatic slicing when profiles are configured

# Bambu Studio Slicing Script
# Usage: ./scripts/slice.sh output/stl/file.stl [--profile "Profile Name"]

BAMBU="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
STL_FILE="$1"
OUTPUT_DIR="output/gcode"
PROFILE=""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "$STL_FILE" ]; then
    echo "Usage: $0 <file.stl> [--profile \"Profile Name\"]"
    exit 1
fi

if [ ! -f "$STL_FILE" ]; then
    echo "Error: File not found: $STL_FILE"
    exit 1
fi

BASENAME=$(basename "$STL_FILE" .stl)

# Parse profile argument
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

slice_file() {
    echo "Slicing: $STL_FILE"

    mkdir -p "$OUTPUT_DIR"

    OUTPUT_FILE="${OUTPUT_DIR}/${BASENAME}.3mf"

    # Basic slicing command
    # Note: Bambu Studio CLI may require specific profile files
    # Users will need to export their profiles from Bambu Studio GUI

    if [ -n "$PROFILE" ]; then
        echo "Using profile: $PROFILE"
        # Profile-based slicing would go here
        # This is a placeholder - actual implementation depends on
        # how user has configured their Bambu Studio profiles
        echo -e "${YELLOW}Note: Profile-based slicing requires profile export${NC}"
        echo "      Export profiles from Bambu Studio GUI first"
    fi

    echo -e "${GREEN}✓ Slicing command prepared${NC}"
    echo "  Input: $STL_FILE"
    echo "  Output: $OUTPUT_FILE"

    # For now, provide instructions for manual slicing
    echo ""
    echo "To complete slicing:"
    echo "  1. Open Bambu Studio"
    echo "  2. Import: $STL_FILE"
    echo "  3. Adjust settings as needed"
    echo "  4. Slice and export to: $OUTPUT_FILE"
    echo ""
    echo "Or drag the STL to Bambu Studio and slice there."

    return 0
}

echo "================================"
slice_file
echo "================================"
