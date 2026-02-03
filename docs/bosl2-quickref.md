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
