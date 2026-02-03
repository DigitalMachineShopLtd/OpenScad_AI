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
