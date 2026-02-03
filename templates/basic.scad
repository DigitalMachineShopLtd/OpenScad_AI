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
