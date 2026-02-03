#!/bin/bash
# Don't use set -e - conflicts with || FAILED=1 pattern

# OpenSCAD BOSL2 Design Validation Script
# Usage: ./scripts/validate.sh designs/path/to/file.scad

OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
DESIGN_FILE="$1"

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

# Syntax check function
validate_syntax() {
    echo -n "Checking syntax... "

    # Try to compile without rendering
    if "$OPENSCAD" -o /dev/null "$DESIGN_FILE" 2>&1 | grep -q "ERROR\|WARNING"; then
        echo -e "${RED}FAILED${NC}"
        "$OPENSCAD" -o /dev/null "$DESIGN_FILE" 2>&1 | grep "ERROR\|WARNING"
        return 1
    else
        echo -e "${GREEN}OK${NC}"
        return 0
    fi
}

# STL export validation
validate_stl_export() {
    echo -n "Checking STL export... "

    TEMP_STL=$(mktemp /tmp/validate_XXXXXX.stl)
    TEMP_FILES+=("$TEMP_STL")

    if "$OPENSCAD" -o "$TEMP_STL" "$DESIGN_FILE" 2>&1 | grep -q "ERROR"; then
        echo -e "${RED}FAILED${NC}"
        return 1
    else
        if [ -f "$TEMP_STL" ] && [ -s "$TEMP_STL" ]; then
            echo -e "${GREEN}OK${NC}"
            return 0
        else
            echo -e "${RED}FAILED (empty output)${NC}"
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
    OUTPUT=$("$OPENSCAD" -o "$TEMP_STL" "$DESIGN_FILE" 2>&1)

    if echo "$OUTPUT" | grep -q "WARNING: Object may not be a valid 2-manifold"; then
        echo -e "${YELLOW}WARNING: Non-manifold geometry detected${NC}"
        echo "  This may cause slicing issues. Review your model."
        return 0  # Warning, not error
    else
        echo -e "${GREEN}OK${NC}"
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
    exit 0
else
    echo -e "${RED}Validation failed. Fix errors before printing.${NC}"
    exit 1
fi
