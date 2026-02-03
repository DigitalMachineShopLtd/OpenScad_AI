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
