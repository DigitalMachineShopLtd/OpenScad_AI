# OpenSCAD BOSL2 Workflow — How-To Guide

Complete guide for designing 3D printable models with OpenSCAD, BOSL2, and the MCP server.

## Quick Start (5 Minutes)

### 1. Check Your Environment

```bash
./scripts/setup.sh
```

This verifies OpenSCAD (AppImage or system), BOSL2, xvfb (if headless), MQTT, and runs a compile test.

### 2. Start a New Design

**Option A — MCP (Claude does it for you):**
```
You: "Create a new mechanical design called motor-mount"
Claude: [uses create_from_template tool → designs/mechanical/motor-mount.scad]
```

**Option B — Manual:**
```bash
cp templates/mechanical-part.scad designs/mechanical/motor-mount.scad
```

### 3. Edit with AI Assistance

Describe what you want to Claude:
- "I need a box with 4 mounting holes in the corners"
- "Create a bracket to hold a NEMA 17 motor"
- "Add a cylindrical standoff on top"

Claude generates BOSL2 code using the `bosl2://` resources for accurate syntax.

### 4. Validate and Render

**Option A — MCP (Claude does it):**
```
You: "Validate and render the motor mount"
Claude: [uses validate_design → render_design_views → render_stl_file]
```

**Option B — Shell scripts:**
```bash
./scripts/validate.sh designs/mechanical/motor-mount.scad
./scripts/render.sh designs/mechanical/motor-mount.scad
```

---

## Working with the MCP Server

The MCP server gives Claude direct access to the OpenSCAD toolchain. Once registered (`claude mcp add openscad -- .venv/bin/python -m mcp_server`), Claude can:

### Validate Designs

Claude calls `validate_design` to run three checks:
1. **Syntax** — will OpenSCAD compile the file?
2. **STL export** — can it generate valid geometry?
3. **Manifold** — is the mesh watertight for slicing?

### Render Multi-View Previews

Claude calls `render_design_views` to get 4 PNGs:
- **Front** — verify height and width proportions
- **Top** — verify layout, hole placement, symmetry
- **Right** — verify depth and side features
- **Isometric** — overall 3D impression

Claude examines these views to self-critique and iterate on the design.

### Track Design Iterations

Claude calls `save_design_iteration` before making changes. This creates numbered copies:
```
output/iterations/
├── motor-mount_v001.scad   ← initial design
├── motor-mount_v002.scad   ← after fixing hole spacing
└── motor-mount_v003.scad   ← after adjusting thickness
```

Use `list_design_iterations` to see all versions, or `get_latest_design_iteration` to retrieve the most recent.

### Access BOSL2 Documentation

Claude loads resources on demand for accurate code generation:

| Resource | What Claude Learns |
|----------|-------------------|
| `bosl2://quickref` | All common BOSL2 functions |
| `bosl2://attachments` | How to use `attach()`, `position()`, anchors |
| `bosl2://threading` | Screw sizes, countersinks, heat-set inserts |
| `bosl2://rounding` | Rounding vs chamfering, print-friendly rules |
| `bosl2://patterns` | `grid_copies()`, `linear_copies()`, `rot_copies()` |
| `bosl2://prompts/image-to-code` | Workflow for generating code from a photo/sketch |

Full API documentation: [docs/mcp-api-reference.md](mcp-api-reference.md)

---

## The Visual Feedback Loop

This is the most powerful workflow — Claude generates code, renders views, critiques its own output, and iterates:

```
1. You describe the object
         │
         ▼
2. Claude writes BOSL2 code (using bosl2:// resources)
         │
         ▼
3. Claude renders 4 views (render_design_views)
         │
         ▼
4. Claude examines each view:
   Front:     "Holes are too close to the edge"
   Top:       "Layout is symmetric — good"
   Right:     "Wall thickness looks thin"
   Isometric: "Overall shape matches intent"
         │
         ▼
5. Claude saves current version (save_design_iteration)
         │
         ▼
6. Claude edits code to fix issues
         │
         ▼
7. Back to step 3 (typically 2-4 iterations)
         │
         ▼
8. Claude validates (validate_design) → renders STL (render_stl_file)
```

**To trigger this workflow:**
```
You: "Create a mounting bracket from this description: [details].
      Render views and iterate until it looks right."
```

---

## Working with Shell Scripts

All scripts support both Linux (headless) and macOS. They auto-detect the OpenSCAD binary (AppImage > system > macOS app) and wrap with `xvfb-run` when no display is available.

### setup.sh — Environment Check

```bash
./scripts/setup.sh
```

Checks:
- OpenSCAD binary (prefers `bin/OpenSCAD-latest.AppImage`)
- BOSL2 library installation
- `xvfb-run` availability (for headless rendering)
- `mosquitto_pub` for MQTT (optional)
- Output directory structure
- Script execute permissions
- BOSL2 compile test (creates and renders a test cube)

### validate.sh — Three-Stage Validation

```bash
./scripts/validate.sh designs/mechanical/my-part.scad
```

**Output:**
```
Validating: designs/mechanical/my-part.scad
================================
Checking syntax... OK
Checking STL export... OK
Checking manifold... OK
================================
All validations passed!
```

- **Green OK** — check passed
- **Red FAILED** — must fix before printing
- **Yellow WARNING** — review but may be intentional (e.g., non-manifold by design)

Publishes results to MQTT topics `openscad/validate/*`.

### render.sh — STL + PNG Rendering

```bash
./scripts/render.sh designs/mechanical/my-part.scad
```

Creates:
- `output/stl/my-part.stl` — print-ready STL
- `output/png/my-part.png` — preview image

Uses `xvfb-run` automatically on headless systems. Publishes to `openscad/render/*`.

### slice.sh — Slicing Readiness

```bash
./scripts/slice.sh output/stl/my-part.stl
```

Validates the STL is non-empty and publishes readiness to MQTT. Slicing is currently manual:
1. Transfer the STL to a machine with a slicer
2. Import into Bambu Studio, OrcaSlicer, or PrusaSlicer
3. Choose your material profile and slice

---

## Templates

Choose the right starting point for your design:

### basic.scad — Simple Designs
- Single objects, quick prototypes
- Learning BOSL2
- No mounting features

### mechanical-part.scad — Functional Parts
- Brackets, mounts, enclosures
- Parts with mounting holes
- Print-oriented design

### parametric.scad — Configurable Designs
- Multiple variations of same design
- Customizable parameters
- OpenSCAD Customizer support

**Using a template:**
```bash
cp templates/mechanical-part.scad designs/mechanical/motor-mount.scad
```

Or via MCP:
```
You: "Create a new design from the mechanical-part template called motor-mount"
```

---

## BOSL2 Best Practices

### Start Simple, Add Complexity

```scad
// Step 1: Basic shape
cuboid([30,20,10]);

// Step 2: Add rounding
cuboid([30,20,10], rounding=2);

// Step 3: Add features
diff() {
    cuboid([30,20,10], rounding=2) {
        attach(TOP) tag("remove") cyl(d=3.2, h=12);
    }
}
```

### Parameterize Everything

```scad
// Good — easy to adjust
width = 30;
height = 20;
hole_size = 3.2;  // M3 clearance
wall = 1.5;       // Minimum for FDM

cuboid([width, width, height]);

// Bad — magic numbers
cuboid([30, 30, 20]);
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

**Stacked shapes:**
```scad
cuboid([20,20,10])
    attach(TOP) cyl(d=15, h=8, anchor=BOTTOM)
        attach(TOP) cuboid([10,10,5], anchor=BOTTOM);
```

---

## Print Quality Tips

### Design for FDM Printing

| Parameter | Recommendation |
|-----------|---------------|
| Wall thickness | Minimum 1.2mm, 1.5mm+ recommended |
| Clearances | Add 0.2mm between mating parts |
| Overhangs | Keep under 45° or plan for supports |
| Bridging | Keep bridges under 20mm |
| Small features | Details under 0.4mm may not print |
| Hole orientation | Perpendicular to layers prints cleaner |
| Bottom edges | Chamfer for bed adhesion: `chamfer1=0.5` |

### Layer Height Reference

| Setting | Layer Height | Use Case |
|---------|-------------|----------|
| Draft | 0.28mm | Quick prototypes, test fits |
| Standard | 0.20mm | General purpose |
| Fine | 0.12mm | Visible parts, small features |

### Material Selection

| Material | Strength | Ease | Notes |
|----------|----------|------|-------|
| PLA | Medium | Easy | Best for prototypes, stiff |
| PETG | High | Medium | Strong, slight flex, heat resistant |
| ASA/ABS | High | Hard | Outdoor use, requires enclosure |
| TPU | Flex | Medium | Gaskets, grips, bumpers |

---

## Troubleshooting

### OpenSCAD Not Found

```
Error: OpenSCAD not found. Run ./scripts/setup.sh for install instructions.
```

**Fix:** Download the AppImage:
```bash
mkdir -p bin
wget -O bin/OpenSCAD-latest.AppImage \
  "https://files.openscad.org/snapshots/OpenSCAD-2025.05.02-x86_64.AppImage"
chmod +x bin/OpenSCAD-latest.AppImage
```

### Headless Rendering Fails

```
Error: Xvfb failed to start
```

**Fix:** Install xvfb:
```bash
sudo apt-get install xvfb
```

### BOSL2 Not Found

```
ERROR: Can't open include file 'BOSL2/std.scad'
```

**Fix:** Install BOSL2 to the correct path:
```bash
git clone https://github.com/BelfrySCAD/BOSL2.git \
  ~/.local/share/OpenSCAD/libraries/BOSL2
```

### Non-Manifold Geometry

```
WARNING: Object may not be a valid 2-manifold
```

**Common causes:**
- Missing `overlap` in boolean operations → add `overlap=0.01` to `attach()`
- Coincident faces → slightly offset one shape
- Floating geometry → ensure all parts are connected

### STL Has Holes or Gaps

**Causes:**
- Z-fighting in boolean operations
- Floating-point precision issues

**Fix:**
```scad
// Add overlap to prevent Z-fighting
diff()
  cuboid([30,20,10]) {
    attach(TOP, overlap=0.01)
    tag("remove") cyl(d=3, h=12);
  }
```

### MCP Server Won't Start

```bash
# Check Python venv is active
source .venv/bin/activate

# Verify FastMCP is installed
python -c "import fastmcp; print(fastmcp.__version__)"

# Run directly to see errors
python -m mcp_server
```

### MQTT Connection Refused

MQTT is optional. If you see:
```
MQTT unavailable (localhost:1883): Connection refused — publishing disabled
```

This is a warning, not an error. The server works without MQTT. To enable:
```bash
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

---

## Complete Pipeline Example

### Creating a Motor Mount from Scratch

**Step 1 — Tell Claude what you need:**
```
"I need a mount for a NEMA 17 stepper motor. It should have:
- 31mm square center opening for motor body
- 4 mounting holes in NEMA 17 pattern (31mm spacing, M3 holes)
- Base plate 50x50mm with its own 4 corner mounting holes
- 5mm thickness
- Rounded vertical edges

Render views, critique, and iterate until it looks right."
```

**Step 2 — Claude generates code, renders 4 views, iterates**

Claude will:
1. Load `bosl2://attachments` and `bosl2://patterns` for syntax reference
2. Generate parameterized BOSL2 code
3. Call `render_design_views` to get front/top/right/isometric PNGs
4. Self-critique: "Top view shows holes aren't centered — adjusting spacing"
5. Call `save_design_iteration` to preserve v001
6. Edit code and re-render (2-4 iterations)

**Step 3 — Validate and render final STL:**
```
You: "Looks good — validate and render the STL"
Claude: [validate_design → render_stl_file]
```

**Step 4 — Transfer to slicer:**
```bash
# STL is at output/stl/motor-mount.stl
# Transfer to slicer machine and print
```

---

## Resources

### Project Documentation
- [MCP API Reference](mcp-api-reference.md) — All 11 tools and 7 resources
- [BOSL2 Quick Reference](bosl2-quickref.md) — Common patterns and examples
- [Image to Code Research](image_to_code.md) — 5 pathways for image-to-OpenSCAD

### External References
- [BOSL2 Wiki](https://github.com/BelfrySCAD/BOSL2/wiki) — Complete documentation
- [BOSL2 Tutorial](https://github.com/BelfrySCAD/BOSL2/wiki/Tutorial-Getting-Started) — Getting started
- [OpenSCAD Manual](https://openscad.org/documentation.html) — Core language reference
- [OpenSCAD Cheat Sheet](https://openscad.org/cheatsheet/) — Quick syntax reference
- [MCP Specification](https://modelcontextprotocol.io) — Protocol documentation

### Community
- [BOSL2 Issues](https://github.com/BelfrySCAD/BOSL2/issues)
- [r/openscad](https://reddit.com/r/openscad)
- [OpenSCAD Forum](https://forum.openscad.org/)
