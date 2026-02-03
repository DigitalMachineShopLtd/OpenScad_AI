# OpenSCAD BOSL2 Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up a hybrid visual workflow for creating high-quality 3D printable models with OpenSCAD, BOSL2, and Bambu Studio integration.

**Architecture:** File-based workflow with OpenSCAD GUI providing live visual feedback while editing in Claude Code, backed by shell scripts for validation, rendering, and slicing automation.

**Tech Stack:** OpenSCAD 2024.10.18, BOSL2 v2.0.716, Bambu Studio CLI, Bash scripts

---

## Task 1: Project Structure Setup

**Files:**
- Create: `.gitignore`
- Create: `designs/mechanical/.keep`
- Create: `designs/artistic/.keep`
- Create: `designs/prototypes/.keep`
- Create: `output/stl/.keep`
- Create: `output/png/.keep`
- Create: `output/gcode/.keep`
- Create: `templates/.keep`
- Create: `scripts/.keep`

**Step 1: Create directory structure**

```bash
mkdir -p designs/mechanical designs/artistic designs/prototypes
mkdir -p output/stl output/png output/gcode
mkdir -p templates scripts docs
```

**Step 2: Create .keep files for empty directories**

```bash
touch designs/mechanical/.keep
touch designs/artistic/.keep
touch designs/prototypes/.keep
touch output/stl/.keep
touch output/png/.keep
touch output/gcode/.keep
touch templates/.keep
touch scripts/.keep
```

**Step 3: Create .gitignore**

Content:
```gitignore
# Generated output files
output/stl/*.stl
output/png/*.png
output/gcode/*.gcode
output/gcode/*.3mf

# Keep directory structure
!output/stl/.keep
!output/png/.keep
!output/gcode/.keep

# macOS
.DS_Store

# OpenSCAD backup files
*.scad~

# Editor files
*.swp
*.swo
*~
.vscode/
.idea/

# Temporary files
*.tmp
*.bak
```

**Step 4: Verify structure**

Run: `tree -a -L 2`

Expected: All directories present with .keep files

**Step 5: Commit**

```bash
git init
git add .
git commit -m "feat: initialize project structure

- Create designs/ directories for mechanical, artistic, prototypes
- Create output/ directories for stl, png, gcode
- Create templates/ and scripts/ directories
- Add .gitignore to exclude generated files"
```

---

## Task 2: Validation Script

**Files:**
- Create: `scripts/validate.sh`

**Step 1: Create validation script skeleton**

```bash
#!/bin/bash
set -e

# OpenSCAD BOSL2 Design Validation Script
# Usage: ./scripts/validate.sh designs/path/to/file.scad

OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
DESIGN_FILE="$1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation functions will go here
```

**Step 2: Add usage and validation checks**

```bash
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
```

**Step 3: Add syntax check function**

```bash
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
```

**Step 4: Add STL export validation**

```bash
validate_stl_export() {
    echo -n "Checking STL export... "

    TEMP_STL="/tmp/validate_$(basename "$DESIGN_FILE" .scad).stl"

    if "$OPENSCAD" -o "$TEMP_STL" "$DESIGN_FILE" 2>&1 | grep -q "ERROR"; then
        echo -e "${RED}FAILED${NC}"
        rm -f "$TEMP_STL"
        return 1
    else
        if [ -f "$TEMP_STL" ] && [ -s "$TEMP_STL" ]; then
            echo -e "${GREEN}OK${NC}"
            rm -f "$TEMP_STL"
            return 0
        else
            echo -e "${RED}FAILED (empty output)${NC}"
            return 1
        fi
    fi
}
```

**Step 5: Add manifold check**

```bash
check_manifold() {
    echo -n "Checking manifold geometry... "

    # OpenSCAD will warn about non-manifold edges in stderr
    TEMP_STL="/tmp/manifold_$(basename "$DESIGN_FILE" .scad).stl"
    OUTPUT=$("$OPENSCAD" -o "$TEMP_STL" "$DESIGN_FILE" 2>&1)

    if echo "$OUTPUT" | grep -q "WARNING: Object may not be a valid 2-manifold"; then
        echo -e "${YELLOW}WARNING: Non-manifold geometry detected${NC}"
        echo "  This may cause slicing issues. Review your model."
        rm -f "$TEMP_STL"
        return 0  # Warning, not error
    else
        echo -e "${GREEN}OK${NC}"
        rm -f "$TEMP_STL"
        return 0
    fi
}
```

**Step 6: Add main execution flow**

```bash
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
```

**Step 7: Make script executable**

Run: `chmod +x scripts/validate.sh`

**Step 8: Test with a simple valid file**

Create test file:
```bash
echo 'include <BOSL2/std.scad>
cube([10,10,10]);' > /tmp/test_valid.scad
```

Run: `./scripts/validate.sh /tmp/test_valid.scad`

Expected: All checks pass with green OK messages

**Step 9: Test with invalid file (syntax error)**

Create test file:
```bash
echo 'include <BOSL2/std.scad>
cube([10,10,10)' > /tmp/test_invalid.scad
```

Run: `./scripts/validate.sh /tmp/test_invalid.scad`

Expected: Syntax check fails with red FAILED message

**Step 10: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat: add validation script for design quality checks

- Syntax validation
- STL export verification
- Manifold geometry checking
- Color-coded output for easy reading"
```

---

## Task 3: Render Script

**Files:**
- Create: `scripts/render.sh`

**Step 1: Create render script skeleton**

```bash
#!/bin/bash
set -e

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
```

**Step 2: Add render function**

```bash
render_stl() {
    echo "Rendering STL (high quality)..."

    OUTPUT_FILE="${OUTPUT_DIR}/${BASENAME}.stl"

    # High-quality render settings
    # --render for full geometry (not preview)
    # --imgsize for preview quality
    "$OPENSCAD" \
        --render \
        -o "$OUTPUT_FILE" \
        "$DESIGN_FILE"

    if [ -f "$OUTPUT_FILE" ]; then
        SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo -e "${GREEN}✓ STL created: $OUTPUT_FILE ($SIZE)${NC}"
        return 0
    else
        echo "Error: Failed to create STL"
        return 1
    fi
}
```

**Step 3: Add PNG preview function**

```bash
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
```

**Step 4: Add main execution**

```bash
echo "Rendering: $DESIGN_FILE"
echo "================================"

mkdir -p "$OUTPUT_DIR" "$PNG_DIR"

if render_stl && render_png; then
    echo "================================"
    echo -e "${GREEN}Rendering complete!${NC}"
    echo "STL: ${OUTPUT_DIR}/${BASENAME}.stl"
    echo "PNG: ${PNG_DIR}/${BASENAME}.png"
    exit 0
else
    echo "Rendering failed"
    exit 1
fi
```

**Step 5: Make script executable**

Run: `chmod +x scripts/render.sh`

**Step 6: Test rendering**

Create test file:
```bash
echo 'include <BOSL2/std.scad>
cuboid([20,15,10], rounding=2);' > /tmp/test_render.scad
```

Run: `./scripts/render.sh /tmp/test_render.scad`

Expected: STL and PNG files created in output/ directories

**Step 7: Verify output files exist**

Run: `ls -lh output/stl/test_render.stl output/png/test_render.png`

Expected: Both files present with reasonable sizes

**Step 8: Commit**

```bash
git add scripts/render.sh
git commit -m "feat: add rendering script for high-quality STL generation

- High-quality STL rendering
- PNG preview generation
- Clear status output with file sizes"
```

---

## Task 4: Slicing Script

**Files:**
- Create: `scripts/slice.sh`

**Step 1: Create slice script skeleton**

```bash
#!/bin/bash
set -e

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
```

**Step 2: Add profile detection**

```bash
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
```

**Step 3: Add slicing function**

```bash
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
```

**Step 4: Add main execution**

```bash
echo "================================"
slice_file
echo "================================"
```

**Step 5: Make script executable**

Run: `chmod +x scripts/slice.sh`

**Step 6: Test basic functionality**

Create test STL (reuse from render test):
```bash
./scripts/render.sh /tmp/test_render.scad
```

Run: `./scripts/slice.sh output/stl/test_render.stl`

Expected: Instructions displayed for manual slicing

**Step 7: Add note about future enhancement**

```bash
# Add comment at top of file
# TODO: Full automation requires Bambu Studio profile export
# TODO: Add profile management commands
# TODO: Add automatic slicing when profiles are configured
```

**Step 8: Commit**

```bash
git add scripts/slice.sh
git commit -m "feat: add slicing script for Bambu Studio integration

- Prepares files for Bambu Studio slicing
- Profile support structure in place
- Provides clear manual slicing instructions
- Ready for future automation enhancement"
```

---

## Task 5: Basic Template

**Files:**
- Create: `templates/basic.scad`

**Step 1: Create basic template**

Content:
```scad
// Basic OpenSCAD Template with BOSL2
//
// This is a minimal starting point for simple designs.
// Modify the parameters and shapes below to create your design.

include <BOSL2/std.scad>

// ============================================
// PARAMETERS
// ============================================

// Dimensions (in mm)
width = 30;
height = 20;
depth = 10;

// Rounding radius for edges
rounding = 2;

// ============================================
// DESIGN
// ============================================

// Simple rounded box example
// Replace this with your own design
cuboid([width, depth, height], rounding=rounding);

// BOSL2 Quick Reference:
//
// Basic Shapes:
//   cuboid([x, y, z], rounding=r)  - Rounded box
//   cyl(d=diameter, h=height)       - Cylinder
//   sphere(d=diameter)              - Sphere
//
// Positioning:
//   left(x)   right(x)
//   fwd(y)    back(y)
//   up(z)     down(z)
//
// Operations:
//   diff()                          - Boolean difference
//   tag("remove") cube([10,10,10])  - Mark for removal in diff()
//
// Arrays:
//   grid_copies(spacing=s, n=[x,y]) - Create grid
//
// Learn more: https://github.com/BelfrySCAD/BOSL2/wiki
```

**Step 2: Test template compiles**

Run: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/basic_test.stl templates/basic.scad`

Expected: STL file created without errors

**Step 3: Validate template**

Run: `./scripts/validate.sh templates/basic.scad`

Expected: All validations pass

**Step 4: Commit**

```bash
git add templates/basic.scad
git commit -m "feat: add basic template for simple designs

- Minimal BOSL2 template
- Includes quick reference comments
- Validated and ready to use"
```

---

## Task 6: Mechanical Part Template

**Files:**
- Create: `templates/mechanical-part.scad`

**Step 1: Create mechanical template**

Content:
```scad
// Mechanical Part Template with BOSL2
//
// Template for functional mechanical parts with common features:
// - Parametric dimensions
// - Mounting holes
// - Rounded edges for strength
// - Assembly clearances

include <BOSL2/std.scad>

// ============================================
// PARAMETERS
// ============================================

// Main body dimensions (mm)
body_width = 50;
body_depth = 40;
body_height = 10;

// Edge rounding (for strength)
edge_rounding = 2;

// Mounting holes
hole_diameter = 3.2;  // M3 screw clearance
hole_spacing = 40;    // Distance between holes

// Clearances for assembly (mm)
clearance = 0.2;  // General clearance for fit

// ============================================
// DESIGN
// ============================================

// Main body with mounting holes
diff() {
    // Main body
    cuboid(
        [body_width, body_depth, body_height],
        rounding=edge_rounding,
        edges="Z"  // Round only vertical edges
    ) {
        // Mounting holes at corners
        attach(TOP, overlap=0.01)
        grid_copies(spacing=hole_spacing, n=[2,2])
        tag("remove")
        cyl(d=hole_diameter, h=body_height + 1, anchor=TOP);
    }
}

// ============================================
// USEFUL BOSL2 PATTERNS FOR MECHANICAL PARTS
// ============================================

// Countersunk holes:
// diff() {
//     cuboid([20,20,5]) {
//         attach(TOP)
//         tag("remove") {
//             cyl(d=3.2, h=6);  // Shaft
//             up(2) cyl(d1=3.2, d2=6.5, h=3);  // Countersink
//         }
//     }
// }

// Standoffs:
// cyl(d=6, h=10, rounding=1);

// Slots for adjustment:
// cuboid([10, 3.5, 5]);

// Chamfered edges:
// cuboid([20,20,10], chamfer=1, edges="Z");
```

**Step 2: Test template compiles**

Run: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/mechanical_test.stl templates/mechanical-part.scad`

Expected: STL file created without errors

**Step 3: Validate template**

Run: `./scripts/validate.sh templates/mechanical-part.scad`

Expected: All validations pass

**Step 4: Commit**

```bash
git add templates/mechanical-part.scad
git commit -m "feat: add mechanical part template with mounting holes

- Parametric dimensions
- Mounting hole pattern
- Edge rounding for strength
- Includes common mechanical part patterns"
```

---

## Task 7: Parametric Template

**Files:**
- Create: `templates/parametric.scad`

**Step 1: Create parametric template**

Content:
```scad
// Parametric Design Template with OpenSCAD Customizer
//
// This template shows how to create designs with adjustable parameters
// that appear in OpenSCAD's Customizer panel (Window → Customizer)

include <BOSL2/std.scad>

// ============================================
// CUSTOMIZABLE PARAMETERS
// ============================================
// Parameters in this section appear in the Customizer

/* [Dimensions] */
// Width of the object (mm)
width = 30;  // [10:100]

// Depth of the object (mm)
depth = 20;  // [10:100]

// Height of the object (mm)
height = 15;  // [5:50]

/* [Features] */
// Radius of rounded edges (0 = sharp)
rounding = 2;  // [0:0.5:10]

// Add mounting holes
add_holes = true;

// Hole diameter (mm)
hole_size = 3.2;  // [2:0.1:10]

/* [Advanced] */
// Number of holes on each side
holes_per_side = 2;  // [1:5]

// Wall thickness (mm)
wall_thickness = 2;  // [1:0.5:10]

/* [Hidden] */
// Parameters in Hidden section don't appear in Customizer
// but can still be used in calculations
$fn = 64;  // Render quality

// ============================================
// CALCULATED VALUES
// ============================================

hole_spacing = min(width, depth) * 0.7;

// ============================================
// DESIGN
// ============================================

diff() {
    // Main body
    cuboid([width, depth, height], rounding=rounding) {

        // Optional mounting holes
        if (add_holes) {
            attach(TOP, overlap=0.01)
            grid_copies(spacing=hole_spacing, n=[holes_per_side, holes_per_side])
            tag("remove")
            cyl(d=hole_size, h=height + 1, anchor=TOP);
        }
    }
}

// ============================================
// CUSTOMIZER TIPS
// ============================================

// 1. Use /* [Section Name] */ to group parameters
// 2. Add comments above parameters - they become labels
// 3. Use ranges: variable = default; // [min:step:max]
// 4. Use dropdowns: variable = "option"; // ["opt1", "opt2", "opt3"]
// 5. Use /* [Hidden] */ for internal variables
//
// Open Customizer: Window → Customizer in OpenSCAD GUI
// Changes update the preview automatically!
```

**Step 2: Test template compiles**

Run: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/parametric_test.stl templates/parametric.scad`

Expected: STL file created without errors

**Step 3: Validate template**

Run: `./scripts/validate.sh templates/parametric.scad`

Expected: All validations pass

**Step 4: Test with different parameters**

Run: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/parametric_test2.stl -D 'width=50' -D 'add_holes=false' templates/parametric.scad`

Expected: STL created with modified parameters

**Step 5: Commit**

```bash
git add templates/parametric.scad
git commit -m "feat: add parametric template with Customizer support

- OpenSCAD Customizer integration
- Adjustable parameters with ranges
- Grouped parameter sections
- Includes usage instructions"
```

---

## Task 8: BOSL2 Quick Reference

**Files:**
- Create: `docs/bosl2-quickref.md`

**Step 1: Create quick reference document**

Content:
```markdown
# BOSL2 Quick Reference

Essential BOSL2 functions and patterns for daily use.

## Getting Started

```scad
include <BOSL2/std.scad>
```

## Basic Shapes

### Cuboid (Rounded Box)
```scad
cuboid([width, depth, height], rounding=2);
cuboid([30, 20, 10], rounding=2, edges="Z");  // Round only vertical edges
```

### Cylinder
```scad
cyl(d=diameter, h=height);
cyl(d=10, h=20, rounding=1);  // Rounded ends
cyl(d1=10, d2=5, h=20);       // Tapered (cone)
```

### Sphere
```scad
sphere(d=20);
```

### Prismoid (Trapezoidal solid)
```scad
prismoid(size1=[20,20], size2=[10,10], h=15);
```

## Positioning & Orientation

### Basic Movement
```scad
left(10) cube([5,5,5]);    // Move -X
right(10) cube([5,5,5]);   // Move +X
fwd(10) cube([5,5,5]);     // Move -Y
back(10) cube([5,5,5]);    // Move +Y
up(10) cube([5,5,5]);      // Move +Z
down(10) cube([5,5,5]);    // Move -Z
```

### Attachments
```scad
cuboid([20,20,10]) {
    attach(TOP) cyl(d=5, h=10);      // Attach to top
    attach(BOTTOM) cyl(d=8, h=5);    // Attach to bottom
    attach(LEFT) sphere(d=6);         // Attach to left face
}
```

Attachment points: `TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `FRONT`, `BACK`

### Positioning on Attachments
```scad
cuboid([30,30,10]) {
    attach(TOP, CENTER) cyl(d=5, h=10);  // Center of top face
    position(TOP+LEFT) sphere(d=4);       // Top-left corner
}
```

## Boolean Operations

### Difference (Subtracting shapes)
```scad
diff() {
    cuboid([30,20,10]);                    // Main shape
    tag("remove") cyl(d=5, h=15);         // Subtract this
    tag("remove") right(10) sphere(d=8);  // And this
}
```

### Difference with Attachments
```scad
diff() {
    cuboid([30,20,10]) {
        attach(TOP, overlap=0.01)
        tag("remove")
        cyl(d=5, h=12);
    }
}
```

### Intersection
```scad
intersect() {
    sphere(d=30);
    cuboid([25,25,50]);
}
```

### Union (Default)
```scad
union() {
    cube([20,20,10]);
    right(15) cube([20,20,10]);
}
```

## Arrays & Patterns

### Grid
```scad
grid_copies(spacing=20, n=[3,2])
    sphere(d=5);

grid_copies(spacing=[20,15], n=[3,2])  // Different X and Y spacing
    cyl(d=4, h=10);
```

### Linear Array
```scad
linear_copies(spacing=15, n=5)
    cube([5,5,5]);

linear_copies(spacing=15, n=5, axis=BACK)  // Along Y axis
    sphere(d=4);
```

### Rotational Array
```scad
rotate_copies(n=6)
    right(20) cyl(d=5, h=10);

rotate_copies(n=8, r=25)  // 8 copies at radius 25
    cube([3,3,10]);
```

### Path Following
```scad
path = [[0,0], [10,10], [20,5], [30,0]];
path_copies(path)
    sphere(d=3);
```

## Rounding & Chamfering

### Edge Rounding
```scad
cuboid([30,20,10], rounding=2, edges="Z");     // Vertical edges only
cuboid([30,20,10], rounding=2, except="Z");     // All except vertical
cuboid([30,20,10], rounding=2);                 // All edges
```

Edge selectors: `"X"`, `"Y"`, `"Z"`, `"ALL"`, `"NONE"`

### Chamfering
```scad
cuboid([30,20,10], chamfer=2, edges="Z");
```

### Cylinder Rounding
```scad
cyl(d=20, h=30, rounding=2);           // Round top and bottom
cyl(d=20, h=30, rounding1=2);          // Round bottom only
cyl(d=20, h=30, chamfer=1);            // Chamfer edges
```

## Mechanical Parts

### Mounting Holes
```scad
diff() {
    cuboid([50,40,10], rounding=2) {
        attach(TOP, overlap=0.01)
        grid_copies(spacing=40, n=[2,2])
        tag("remove")
        cyl(d=3.2, h=12, anchor=TOP);  // M3 clearance holes
    }
}
```

### Countersunk Holes
```scad
diff() {
    cuboid([30,30,8]) {
        attach(TOP, overlap=0.01)
        tag("remove") {
            cyl(d=3.2, h=10);                    // Shaft
            up(5) cyl(d1=3.2, d2=6.5, h=3);     // Countersink
        }
    }
}
```

### Standoffs
```scad
cyl(d=6, h=15, rounding=1);
```

### Slots
```scad
cuboid([20, 3.5, 8]);  // Basic slot

// Rounded slot
hull() {
    left(5) cyl(d=3.5, h=8);
    right(5) cyl(d=3.5, h=8);
}
```

### Bosses (mounting posts)
```scad
cyl(d1=10, d2=6, h=8) {
    attach(TOP)
    cyl(d=3, h=5);  // Hole for screw
}
```

## Common Screw Sizes

| Screw | Clearance Hole | Close Fit | Countersink |
|-------|----------------|-----------|-------------|
| M2    | 2.2 mm         | 2.05 mm   | 4.4 mm      |
| M3    | 3.2 mm         | 3.05 mm   | 6.5 mm      |
| M4    | 4.3 mm         | 4.05 mm   | 8.5 mm      |
| M5    | 5.3 mm         | 5.05 mm   | 10.5 mm     |

## Print-in-Place Features

### Clearance Gaps
```scad
clearance = 0.2;  // Standard FDM clearance
clearance = 0.15; // Tight fit
clearance = 0.3;  // Loose fit
```

### Hinges
```scad
// Use BOSL2 hinges module
include <BOSL2/hinges.scad>
```

## Tips

1. **Always use `$fn` for final renders:** `$fn=64` or higher
2. **Use `overlap` in diff():** Prevents Z-fighting artifacts
3. **Clearances:** Add 0.2mm for FDM parts that need to fit together
4. **Wall thickness:** Minimum 1.2mm for PLA, 1.5mm+ recommended
5. **Overhangs:** Keep under 45° or use supports
6. **Anchor points:** Use `anchor=` to control where shapes are positioned

## Resources

- [BOSL2 Full Documentation](https://github.com/BelfrySCAD/BOSL2/wiki)
- [BOSL2 Tutorial](https://github.com/BelfrySCAD/BOSL2/wiki/Tutorial-Getting-Started)
- [Shape Reference](https://github.com/BelfrySCAD/BOSL2/wiki/shapes)
- [Attachment Reference](https://github.com/BelfrySCAD/BOSL2/wiki/attachments)
```

**Step 2: Commit**

```bash
git add docs/bosl2-quickref.md
git commit -m "docs: add BOSL2 quick reference guide

- Common shapes and operations
- Positioning and attachments
- Mechanical part patterns
- Screw size reference
- Print tips and best practices"
```

---

## Task 9: How-To Guide

**Files:**
- Create: `docs/HOW-TO-USE.md`

**Step 1: Create comprehensive how-to guide**

Content:
```markdown
# OpenSCAD BOSL2 Workflow - How-To Guide

Complete guide for designing 3D printable models with OpenSCAD, BOSL2, and Claude Code.

## Quick Start (5 Minutes)

### 1. Start a New Design

```bash
# Copy a template
cp templates/basic.scad designs/mechanical/my-part.scad

# Open in OpenSCAD GUI
open -a OpenSCAD designs/mechanical/my-part.scad
```

### 2. Enable Auto-Reload in OpenSCAD

1. In OpenSCAD: `Design → Automatic Reload and Preview`
2. Position the window where you can see it while coding

### 3. Edit with AI Assistance

In Claude Code, describe what you want:
- "I need a box with 4 mounting holes in the corners"
- "Create a bracket to hold a motor"
- "Add a cylindrical standoff on top"

AI generates BOSL2 code → You save → OpenSCAD updates instantly!

### 4. Validate and Print

```bash
# Check design quality
./scripts/validate.sh designs/mechanical/my-part.scad

# Create high-quality STL
./scripts/render.sh designs/mechanical/my-part.scad

# Prepare for printing
./scripts/slice.sh output/stl/my-part.stl
```

---

## Detailed Workflow

### The Edit-Preview Cycle

This is your main workflow loop:

1. **Edit** `.scad` file in your editor with AI assistance
2. **Save** the file (Cmd+S)
3. **Preview** updates automatically in OpenSCAD (1-2 seconds)
4. **Iterate** - make changes, save, see results

**Tips:**
- Keep OpenSCAD window visible while editing
- Use F5 in OpenSCAD for quick preview (fast)
- Use F6 for full render (slower, more accurate)
- Don't close OpenSCAD between edits - just keep it open

### Working with AI (Claude Code)

**Starting a design:**
```
You: "I need a parametric box with rounded corners and 4 mounting holes"

AI: [Generates BOSL2 code with explanations]

You: "Make the corners sharper and add a slot on the side"

AI: [Updates the code]
```

**What AI helps with:**
- Writing proper BOSL2 syntax
- Explaining what each function does
- Suggesting better approaches
- Debugging OpenSCAD errors
- Learning BOSL2 patterns through examples

**Best practices:**
- Describe what you want, not how to code it
- Ask for explanations if you don't understand
- Request alternatives: "What are other ways to do this?"
- Iterate in small steps for best visual feedback

### Templates

Choose the right starting point:

**`templates/basic.scad`** - Simple designs
- Single objects
- Quick prototypes
- Learning BOSL2

**`templates/mechanical-part.scad`** - Functional parts
- Brackets, mounts, enclosures
- Parts with mounting holes
- Mechanical assemblies

**`templates/parametric.scad`** - Configurable designs
- Multiple variations of same design
- Customizable parameters
- Designs you'll adjust often

**Using templates:**
```bash
# Copy template to your design directory
cp templates/mechanical-part.scad designs/mechanical/motor-mount.scad

# Open in OpenSCAD
open -a OpenSCAD designs/mechanical/motor-mount.scad

# Edit with AI assistance
```

### Validation

**Always validate before printing!**

```bash
./scripts/validate.sh designs/mechanical/my-part.scad
```

**What it checks:**
- ✓ Syntax errors - Will OpenSCAD compile it?
- ✓ STL export - Can it create a valid STL?
- ✓ Manifold geometry - Are all edges connected? (Critical!)
- ⚠️ Warnings about potential print issues

**Understanding results:**
- **Green OK** - Check passed
- **Red FAILED** - Must fix before printing
- **Yellow WARNING** - Review but may be intentional

**Common issues:**
- Non-manifold geometry: Gaps or holes in the mesh
- Syntax errors: Typos, missing brackets
- Invalid parameters: Negative sizes, impossible dimensions

### Rendering

**For final prints, render high-quality STL:**

```bash
./scripts/render.sh designs/mechanical/my-part.scad
```

**This creates:**
- `output/stl/my-part.stl` - High-quality STL for printing
- `output/png/my-part.png` - Preview image for documentation

**When to render:**
- Before slicing for printing
- When sharing designs
- For archiving completed work

**Don't render during iteration** - use OpenSCAD preview instead (much faster)

### Slicing

**Prepare validated STL for your printer:**

```bash
./scripts/slice.sh output/stl/my-part.stl
```

**Current functionality:**
- Prepares file for Bambu Studio
- Shows slicing instructions
- Sets up output paths

**Manual slicing steps:**
1. Open Bambu Studio
2. Import the STL from `output/stl/`
3. Choose your profile (material, quality)
4. Review preview (layers, supports)
5. Slice and send to printer or save to SD card

**Recommended Bambu Studio settings:**
- **Layer height:** 0.2mm (standard), 0.12mm (detailed), 0.28mm (draft)
- **Infill:** 15-20% (normal), 30%+ (strong parts)
- **Supports:** Auto-generate for overhangs > 45°
- **Material:** PLA (easy), PETG (strong), ASA (outdoor)

### Complete Pipeline Example

**Creating a motor mount from scratch:**

```bash
# 1. Start from template
cp templates/mechanical-part.scad designs/mechanical/nema17-mount.scad

# 2. Open in OpenSCAD GUI
open -a OpenSCAD designs/mechanical/nema17-mount.scad

# 3. Tell AI what you want
```

To Claude Code:
```
"I need a mount for a NEMA 17 stepper motor. It should have:
- 31mm square center opening for motor body
- 4 mounting holes in NEMA 17 pattern (31mm spacing, M3 holes)
- Base plate 50x50mm with its own 4 corner mounting holes
- 5mm thickness
- Rounded edges"
```

AI generates the code with proper BOSL2 functions.

```bash
# 4. Save and preview in OpenSCAD
# Make adjustments by describing changes to AI

# 5. When it looks good, validate
./scripts/validate.sh designs/mechanical/nema17-mount.scad

# 6. Render final STL
./scripts/render.sh designs/mechanical/nema17-mount.scad

# 7. Slice for printing
./scripts/slice.sh output/stl/nema17-mount.stl

# 8. Print!
```

---

## Tips & Tricks

### Preview Speed

**Fast iteration:**
- Use F5 (quick preview) during design
- Simple shapes preview in 1-2 seconds
- Complex models take longer

**Final check:**
- Use F6 (full render) before exporting
- More accurate but slower
- Shows exactly what will print

### BOSL2 Best Practices

**1. Start simple, add complexity:**
```scad
// Start with basic shape
cuboid([30,20,10]);

// Add rounding
cuboid([30,20,10], rounding=2);

// Add features
diff() {
    cuboid([30,20,10], rounding=2) {
        attach(TOP) tag("remove") cyl(d=3, h=12);
    }
}
```

**2. Use parameters for everything:**
```scad
// Good - easy to adjust
width = 30;
height = 20;
hole_size = 3.2;

cuboid([width, width, height]);

// Bad - hard to change
cuboid([30, 30, 20]);
```

**3. Add comments for future you:**
```scad
// M3 clearance hole (3.2mm for easy fit)
hole_diameter = 3.2;

// Wall thickness (minimum for PLA printing)
wall = 1.5;
```

### Common Patterns

**Mounting holes at corners:**
```scad
diff() {
    cuboid([50,40,10], rounding=2) {
        attach(TOP, overlap=0.01)
        grid_copies(spacing=40, n=[2,2])
        tag("remove")
        cyl(d=3.2, h=12, anchor=TOP);
    }
}
```

**Rounded slot:**
```scad
hull() {
    left(10) cyl(d=3.5, h=8);
    right(10) cyl(d=3.5, h=8);
}
```

**Text labels (remember to mirror for printing):**
```scad
linear_extrude(height=1)
    mirror([1,0,0])  // Mirror text so it reads correctly when printed
    text("Label", size=6, halign="center");
```

### Print Quality Tips

**Design for FDM printing:**
- **Wall thickness:** Minimum 1.2mm, 1.5mm+ recommended
- **Clearances:** Add 0.2mm between parts that need to fit
- **Overhangs:** Keep under 45° or plan for supports
- **Bridging:** Keep bridges under 20mm
- **Small features:** Details under 0.4mm may not print well

**Orientation matters:**
- Print flat faces down when possible
- Minimize supports
- Consider layer lines for strength
- Holes perpendicular to layers print cleaner

**Test fit:**
- Print a small test piece first for assembled parts
- Verify clearances before printing large parts
- Adjust if too tight or too loose

### Troubleshooting

**OpenSCAD shows yellow warnings:**
- Usually about manifold geometry
- Run validation script for details
- May need to adjust overlaps or fix intersections

**Preview is slow:**
- Reduce detail during design: `$fn=32` or lower
- Increase for final render: `$fn=64` or higher
- Complex BOSL2 operations take time

**STL has holes or gaps:**
- Non-manifold geometry
- Check for floating point issues
- Add `overlap` parameter to diff() operations
- Use validation script to identify problems

**Part doesn't fit together:**
- Add clearances (0.2mm for normal fit)
- Print test pieces first
- Adjust based on your printer's accuracy

---

## Resources

### Documentation
- [BOSL2 Quick Reference](bosl2-quickref.md) - Common patterns in this repo
- [BOSL2 Wiki](https://github.com/BelfrySCAD/BOSL2/wiki) - Complete documentation
- [OpenSCAD Manual](https://openscad.org/documentation.html) - Core language

### Learning
- [BOSL2 Tutorial](https://github.com/BelfrySCAD/BOSL2/wiki/Tutorial-Getting-Started)
- [OpenSCAD Cheat Sheet](https://openscad.org/cheatsheet/)

### Community
- [BOSL2 Issues](https://github.com/BelfrySCAD/BOSL2/issues) - Ask questions
- [r/openscad](https://reddit.com/r/openscad) - Share designs
- [OpenSCAD Forum](https://forum.openscad.org/)

---

## Project Structure Reference

```
OpenScad_AI/
├── designs/           # Your .scad source files (commit these!)
│   ├── mechanical/   # Functional parts
│   ├── artistic/     # Decorative objects
│   └── prototypes/   # Experimental designs
│
├── output/           # Generated files (gitignored)
│   ├── stl/         # Ready-to-print STL files
│   ├── png/         # Preview images
│   └── gcode/       # Sliced files
│
├── templates/        # Starting points
│   ├── basic.scad
│   ├── mechanical-part.scad
│   └── parametric.scad
│
├── scripts/          # Automation tools
│   ├── validate.sh  # Check design quality
│   ├── render.sh    # Generate STL
│   └── slice.sh     # Prepare for printing
│
└── docs/            # Documentation
    ├── HOW-TO-USE.md (this file)
    └── bosl2-quickref.md
```

---

## Need Help?

**Ask Claude Code!**
- "How do I create mounting holes?"
- "What's the best way to add threads?"
- "Why is my model not manifold?"
- "Explain this BOSL2 function"

Claude Code can help with:
- Writing and explaining BOSL2 code
- Debugging OpenSCAD errors
- Suggesting design improvements
- Learning best practices

**Check the quick reference:**
- `docs/bosl2-quickref.md` - Common patterns and examples

**Run validation:**
```bash
./scripts/validate.sh your-design.scad
```
Catches most issues before printing!
```

**Step 2: Commit**

```bash
git add docs/HOW-TO-USE.md
git commit -m "docs: add comprehensive how-to guide

- Quick start guide (5 minutes)
- Detailed workflow explanation
- AI assistance best practices
- Template usage guide
- Complete pipeline example
- Tips, tricks, and troubleshooting
- Resources and references"
```

---

## Task 10: Create Example Design

**Files:**
- Create: `designs/examples/sample-bracket.scad`

**Step 1: Create example directory and file**

```bash
mkdir -p designs/examples
```

Content for `designs/examples/sample-bracket.scad`:
```scad
// Sample Bracket - Example Design
//
// This example demonstrates:
// - Using BOSL2 for mechanical parts
// - Proper parametric design
// - Mounting holes
// - Edge rounding
// - Comments and organization

include <BOSL2/std.scad>

// ============================================
// PARAMETERS
// ============================================

// Bracket dimensions
bracket_width = 40;
bracket_depth = 30;
bracket_height = 8;
bracket_rounding = 2;

// Mounting holes (M3)
hole_diameter = 3.2;  // Clearance for M3 screws
hole_spacing = 30;

// Wall mount arm
arm_length = 25;
arm_thickness = 6;

// ============================================
// MAIN ASSEMBLY
// ============================================

// Base plate with mounting holes
base_plate();

// Vertical arm
wall_mount_arm();

// ============================================
// COMPONENTS
// ============================================

module base_plate() {
    diff() {
        // Main base
        cuboid(
            [bracket_width, bracket_depth, bracket_height],
            rounding=bracket_rounding,
            edges="Z"  // Round only vertical edges
        ) {
            // Corner mounting holes
            attach(TOP, overlap=0.01)
            grid_copies(spacing=hole_spacing, n=[2,2])
            tag("remove")
            cyl(d=hole_diameter, h=bracket_height + 2, anchor=TOP);
        }
    }
}

module wall_mount_arm() {
    // Position on back edge of base
    back(bracket_depth/2 - arm_thickness/2)
    up(bracket_height/2)
    diff() {
        // Vertical mounting arm
        cuboid(
            [bracket_width, arm_thickness, arm_length],
            rounding=bracket_rounding,
            edges="Z"
        ) {
            // Wall mounting holes
            attach(BACK, overlap=0.01)
            grid_copies(spacing=hole_spacing, n=[2,1])
            tag("remove")
            cyl(d=hole_diameter, h=arm_thickness + 2, anchor=BACK);
        }
    }
}

// ============================================
// RENDER QUALITY
// ============================================

// For final renders, use high quality
// Uncomment the line below:
// $fn = 64;

// For faster previews during design, use lower values:
$fn = 32;
```

**Step 2: Test example compiles**

Run: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/sample_bracket.stl designs/examples/sample-bracket.scad`

Expected: STL file created without errors

**Step 3: Validate example**

Run: `./scripts/validate.sh designs/examples/sample-bracket.scad`

Expected: All validations pass

**Step 4: Render example**

Run: `./scripts/render.sh designs/examples/sample-bracket.scad`

Expected: STL and PNG created in output/ directories

**Step 5: Verify outputs**

Run: `ls -lh output/stl/sample-bracket.stl output/png/sample-bracket.png`

Expected: Both files exist with reasonable sizes

**Step 6: Commit**

```bash
git add designs/examples/sample-bracket.scad
git commit -m "docs: add sample bracket example design

- Demonstrates BOSL2 mechanical part design
- Shows proper parametric structure
- Includes mounting holes and attachments
- Well-commented for learning
- Validated and tested"
```

---

## Task 11: README and Final Documentation

**Files:**
- Create: `README.md`

**Step 1: Create project README**

Content:
```markdown
# OpenSCAD BOSL2 Workflow

Professional workflow for creating high-quality 3D printable models with OpenSCAD, BOSL2, and AI assistance.

## Features

✨ **Hybrid Visual Workflow** - Edit with AI assistance, see changes instantly in OpenSCAD GUI
🤖 **AI-Powered Learning** - Learn BOSL2 through examples and explanations
✅ **Quality Validation** - Automated checks for manifold geometry and printability
🎯 **Ready-to-Use Templates** - Quick start for common design types
🔧 **Bambu Studio Integration** - Streamlined slicing pipeline
📚 **Comprehensive Docs** - How-to guide and BOSL2 quick reference

## Quick Start

### 1. Start a New Design

```bash
# Copy a template
cp templates/basic.scad designs/mechanical/my-part.scad

# Open in OpenSCAD GUI
open -a OpenSCAD designs/mechanical/my-part.scad

# Enable "Design → Automatic Reload and Preview"
```

### 2. Edit with AI Assistance

Describe what you want to Claude Code:
- "Create a bracket with 4 mounting holes"
- "Add a cylindrical standoff on top"
- "Make the edges more rounded"

AI generates BOSL2 code → Save → OpenSCAD updates instantly!

### 3. Validate and Print

```bash
# Check design quality
./scripts/validate.sh designs/mechanical/my-part.scad

# Create print-ready STL
./scripts/render.sh designs/mechanical/my-part.scad

# Slice for printing
./scripts/slice.sh output/stl/my-part.stl
```

## Project Structure

```
OpenScad_AI/
├── designs/          # Your .scad designs (version controlled)
│   ├── mechanical/  # Functional parts
│   ├── artistic/    # Decorative objects
│   └── prototypes/  # Experimental designs
│
├── output/          # Generated files (gitignored)
│   ├── stl/        # Print-ready STL files
│   ├── png/        # Preview images
│   └── gcode/      # Sliced files
│
├── templates/       # Starting points
│   ├── basic.scad
│   ├── mechanical-part.scad
│   └── parametric.scad
│
├── scripts/         # Automation tools
│   ├── validate.sh # Design quality checks
│   ├── render.sh   # STL generation
│   └── slice.sh    # Slicing preparation
│
└── docs/           # Documentation
    ├── HOW-TO-USE.md
    └── bosl2-quickref.md
```

## Documentation

- **[How-To Guide](docs/HOW-TO-USE.md)** - Complete workflow guide
- **[BOSL2 Quick Reference](docs/bosl2-quickref.md)** - Common patterns and examples
- **[Sample Bracket](designs/examples/sample-bracket.scad)** - Example design

## Scripts

### validate.sh - Design Quality Checks

```bash
./scripts/validate.sh designs/mechanical/my-part.scad
```

Validates:
- ✓ Syntax - Will OpenSCAD compile it?
- ✓ STL Export - Can it generate a valid STL?
- ✓ Manifold Geometry - Are all edges connected?

### render.sh - High-Quality STL Generation

```bash
./scripts/render.sh designs/mechanical/my-part.scad
```

Creates:
- `output/stl/my-part.stl` - Print-ready STL
- `output/png/my-part.png` - Preview image

### slice.sh - Slicing Preparation

```bash
./scripts/slice.sh output/stl/my-part.stl
```

Prepares file for Bambu Studio slicing.

## Templates

**basic.scad** - Simple designs, quick prototypes
**mechanical-part.scad** - Functional parts with mounting holes
**parametric.scad** - Configurable designs with Customizer support

## Requirements

- **OpenSCAD** 2024.10.18+ with CLI access
- **BOSL2** v2.0.716+ installed in OpenSCAD libraries
- **Bambu Studio** (for slicing)
- **macOS** (scripts use macOS paths)

## System Setup

OpenSCAD CLI: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD`
BOSL2 Location: `~/Documents/OpenSCAD/libraries/BOSL2`
Bambu Studio CLI: `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio`

## Workflow

1. **Design** - Edit .scad files with AI assistance
2. **Preview** - OpenSCAD GUI shows changes instantly (auto-reload)
3. **Iterate** - Make changes, save, see results in 1-2 seconds
4. **Validate** - Run quality checks before printing
5. **Render** - Generate high-quality STL
6. **Slice** - Prepare for your printer
7. **Print** - High-quality 3D prints!

## Tips

- Keep OpenSCAD GUI open with auto-reload enabled
- Use F5 for quick preview, F6 for full render
- Always validate before printing
- Start from templates for faster development
- Ask Claude Code for help with BOSL2 syntax
- Add 0.2mm clearance for parts that fit together

## Resources

- [BOSL2 Documentation](https://github.com/BelfrySCAD/BOSL2/wiki)
- [OpenSCAD Manual](https://openscad.org/documentation.html)
- [BOSL2 Tutorial](https://github.com/BelfrySCAD/BOSL2/wiki/Tutorial-Getting-Started)

## License

This workflow setup is provided as-is for personal and commercial use.

BOSL2 is licensed under BSD 2-Clause License.

---

**Ready to create amazing 3D prints! 🚀**

See [docs/HOW-TO-USE.md](docs/HOW-TO-USE.md) for the complete guide.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add project README with quick start guide

- Feature overview
- Quick start instructions
- Project structure explanation
- Script usage reference
- Template descriptions
- System requirements
- Links to detailed documentation"
```

---

## Task 12: Final Verification

**Step 1: Verify all directories exist**

Run: `tree -L 2 -a`

Expected output:
```
.
├── .git/
├── .gitignore
├── README.md
├── designs/
│   ├── examples/
│   ├── mechanical/
│   ├── artistic/
│   └── prototypes/
├── docs/
│   ├── HOW-TO-USE.md
│   ├── bosl2-quickref.md
│   └── plans/
├── output/
│   ├── stl/
│   ├── png/
│   └── gcode/
├── scripts/
│   ├── validate.sh
│   ├── render.sh
│   └── slice.sh
└── templates/
    ├── basic.scad
    ├── mechanical-part.scad
    └── parametric.scad
```

**Step 2: Verify all scripts are executable**

Run: `ls -l scripts/`

Expected: All .sh files have executable permissions (-rwxr-xr-x)

**Step 3: Test complete workflow with example**

```bash
# Validate example
./scripts/validate.sh designs/examples/sample-bracket.scad

# Render example
./scripts/render.sh designs/examples/sample-bracket.scad

# Verify outputs
ls -lh output/stl/sample-bracket.stl output/png/sample-bracket.png
```

Expected: All commands succeed, files created

**Step 4: Verify documentation**

Run: `ls -lh docs/`

Expected files:
- HOW-TO-USE.md
- bosl2-quickref.md
- plans/2026-02-02-openscad-bosl2-workflow-design.md
- plans/2026-02-02-openscad-bosl2-workflow.md

**Step 5: Test templates compile**

```bash
/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/test_basic.stl templates/basic.scad
/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/test_mechanical.stl templates/mechanical-part.scad
/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD -o /tmp/test_parametric.stl templates/parametric.scad
```

Expected: All three STL files created without errors

**Step 6: Review git status**

Run: `git status`

Expected: Working tree clean, all files committed

**Step 7: View commit history**

Run: `git log --oneline`

Expected: ~12 commits showing all implementation tasks

**Step 8: Create verification summary**

```bash
echo "==================================="
echo "OpenSCAD BOSL2 Workflow - Verification"
echo "==================================="
echo ""
echo "✓ Project structure created"
echo "✓ Scripts installed and tested"
echo "✓ Templates validated"
echo "✓ Documentation complete"
echo "✓ Example design working"
echo "✓ Git repository initialized"
echo ""
echo "Ready to use! See docs/HOW-TO-USE.md to get started."
```

**Step 9: Final commit (if needed)**

```bash
# If any verification fixes were needed
git add .
git commit -m "chore: final verification and cleanup"
```

**Step 10: Display completion message**

```bash
cat << 'EOF'

╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🎉  OpenSCAD BOSL2 Workflow Setup Complete!  🎉        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Next steps:

1. Read the guide:
   cat docs/HOW-TO-USE.md

2. Try the example:
   open -a OpenSCAD designs/examples/sample-bracket.scad
   Enable: Design → Automatic Reload and Preview

3. Start your first design:
   cp templates/mechanical-part.scad designs/mechanical/my-part.scad
   open -a OpenSCAD designs/mechanical/my-part.scad

4. Ask Claude Code for help:
   "Create a bracket with 4 mounting holes"

Happy designing! 🚀

EOF
```

---

## Summary

**Implementation complete!**

This plan creates:
- ✅ Complete project structure
- ✅ Three automation scripts (validate, render, slice)
- ✅ Three design templates (basic, mechanical, parametric)
- ✅ Comprehensive documentation (how-to, quick ref, README)
- ✅ Working example design
- ✅ Git repository with clean history

**Total tasks:** 12
**Estimated time:** 2-3 hours for careful implementation
**Testing:** Each task includes verification steps
**Result:** Production-ready workflow for 3D printing with OpenSCAD + BOSL2
