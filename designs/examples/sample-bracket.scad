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
