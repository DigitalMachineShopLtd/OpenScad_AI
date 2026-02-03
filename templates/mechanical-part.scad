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
