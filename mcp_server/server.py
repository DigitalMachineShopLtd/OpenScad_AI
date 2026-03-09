"""OpenScad_AI MCP Server — Tools and Resources for AI-assisted 3D design with BOSL2."""

import logging
import os
from dataclasses import asdict
from pathlib import Path

from fastmcp import FastMCP

from mcp_server import mqtt_client
from mcp_server.openscad import (
    PROJECT_DIR,
    find_bosl2,
    get_version,
    render_multi_view,
    render_png,
    render_stl,
    validate,
)
from mcp_server.versioning import (
    get_latest_iteration,
    list_iterations,
    save_iteration,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

mcp = FastMCP(
    "OpenScad_AI",
    instructions=(
        "MCP server for AI-assisted 3D design with OpenSCAD and BOSL2. "
        "Use tools to validate, render, and manage designs. "
        "Use resources to access BOSL2 documentation and design context."
    ),
)

# ---------------------------------------------------------------------------
# TOOLS — Model-controlled, Claude invokes these automatically
# ---------------------------------------------------------------------------


@mcp.tool()
def validate_design(file_path: str) -> dict:
    """Validate an OpenSCAD design file. Runs syntax check, STL export test, and manifold geometry check.

    Args:
        file_path: Path to .scad file (relative to project root or absolute)
    """
    resolved = _resolve_path(file_path)
    result = validate(resolved)

    mqtt_client.publish_event("validate", "result", {
        "file": resolved,
        "syntax_ok": result.syntax_ok,
        "export_ok": result.export_ok,
        "manifold_ok": result.manifold_ok,
        "overall": result.overall,
    })

    return asdict(result)


@mcp.tool()
def render_stl_file(file_path: str) -> dict:
    """Render a high-quality STL file from an OpenSCAD design. Output goes to output/stl/.

    Args:
        file_path: Path to .scad file (relative to project root or absolute)
    """
    resolved = _resolve_path(file_path)

    mqtt_client.publish_event("render", "started", {"file": resolved})
    result = render_stl(resolved)

    mqtt_client.publish_event("render", "stl", {
        "file": resolved,
        "status": "success" if result.success else "failed",
        "stl_path": result.file_path,
        "size_bytes": result.size_bytes,
        "duration_ms": result.duration_ms,
    })

    return asdict(result)


@mcp.tool()
def render_png_preview(
    file_path: str,
    imgsize: str = "1024,768",
    colorscheme: str = "Tomorrow",
    camera: str | None = None,
) -> dict:
    """Render a PNG preview image of an OpenSCAD design. Output goes to output/png/.

    Args:
        file_path: Path to .scad file (relative to project root or absolute)
        imgsize: Image dimensions as "width,height" (default: "1024,768")
        colorscheme: OpenSCAD color scheme (default: "Tomorrow")
        camera: Optional camera parameters "translateX,Y,Z,rotX,Y,Z,distance"
    """
    resolved = _resolve_path(file_path)
    result = render_png(resolved, imgsize=imgsize, colorscheme=colorscheme, camera=camera)

    mqtt_client.publish_event("render", "png", {
        "file": resolved,
        "status": "success" if result.success else "failed",
        "png_path": result.file_path,
    })

    return asdict(result)


@mcp.tool()
def render_design_views(
    file_path: str,
    imgsize: str = "800,600",
    colorscheme: str = "Tomorrow",
) -> dict:
    """Render front, top, right, and isometric PNG views of an OpenSCAD design.
    Use this for visual self-critique: examine all 4 views to identify proportion,
    alignment, and feature placement issues that a single view might miss.

    Args:
        file_path: Path to .scad file (relative to project root or absolute)
        imgsize: Image dimensions as "width,height" (default: "800,600")
        colorscheme: OpenSCAD color scheme (default: "Tomorrow")
    """
    resolved = _resolve_path(file_path)
    result = render_multi_view(resolved, imgsize=imgsize, colorscheme=colorscheme)

    mqtt_client.publish_event("render", "multi_view", {
        "file": resolved,
        "status": "success" if result["success"] else "failed",
        "view_count": len(result["views"]),
    })

    return result


@mcp.tool()
def list_designs(directory: str = "designs") -> dict:
    """List all .scad design files in the project.

    Args:
        directory: Subdirectory to search (default: "designs")
    """
    search_dir = PROJECT_DIR / directory
    if not search_dir.is_dir():
        return {"error": f"Directory not found: {directory}", "designs": []}

    designs = []
    for scad in sorted(search_dir.rglob("*.scad")):
        stat = scad.stat()
        designs.append({
            "name": scad.stem,
            "path": str(scad.relative_to(PROJECT_DIR)),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
        })

    return {"count": len(designs), "designs": designs}


@mcp.tool()
def create_from_template(template: str, name: str, directory: str = "designs/mechanical") -> dict:
    """Create a new design from a template.

    Args:
        template: Template name: "basic", "mechanical-part", or "parametric"
        name: Name for the new design (without .scad extension)
        directory: Target directory relative to project root (default: "designs/mechanical")
    """
    template_map = {
        "basic": "basic.scad",
        "mechanical-part": "mechanical-part.scad",
        "mechanical": "mechanical-part.scad",
        "parametric": "parametric.scad",
    }

    template_file = template_map.get(template)
    if not template_file:
        return {"error": f"Unknown template: {template}. Options: {list(template_map.keys())}"}

    src = PROJECT_DIR / "templates" / template_file
    if not src.is_file():
        return {"error": f"Template file not found: {src}"}

    dest_dir = PROJECT_DIR / directory
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}.scad"

    if dest.exists():
        return {"error": f"File already exists: {dest.relative_to(PROJECT_DIR)}"}

    dest.write_text(src.read_text())
    log.info("Created design from template: %s -> %s", template, dest)

    mqtt_client.publish_event("design", "created", {
        "template": template,
        "file": str(dest.relative_to(PROJECT_DIR)),
    })

    return {
        "success": True,
        "file_path": str(dest.relative_to(PROJECT_DIR)),
        "template_used": template,
    }


@mcp.tool()
def get_design_status(file_path: str) -> dict:
    """Check the current status of a design — file info, last render outputs, and whether outputs are stale.

    Args:
        file_path: Path to .scad file (relative to project root or absolute)
    """
    resolved = _resolve_path(file_path)
    scad = Path(resolved)

    if not scad.is_file():
        return {"error": f"File not found: {file_path}"}

    scad_mtime = scad.stat().st_mtime
    status = {
        "file": str(scad.relative_to(PROJECT_DIR)) if scad.is_relative_to(PROJECT_DIR) else resolved,
        "size_bytes": scad.stat().st_size,
        "modified": scad_mtime,
    }

    # Check for existing outputs
    stl_path = PROJECT_DIR / "output" / "stl" / f"{scad.stem}.stl"
    png_path = PROJECT_DIR / "output" / "png" / f"{scad.stem}.png"

    if stl_path.is_file():
        stl_mtime = stl_path.stat().st_mtime
        status["stl"] = {
            "path": str(stl_path.relative_to(PROJECT_DIR)),
            "size_bytes": stl_path.stat().st_size,
            "stale": stl_mtime < scad_mtime,
        }
    else:
        status["stl"] = None

    if png_path.is_file():
        png_mtime = png_path.stat().st_mtime
        status["png"] = {
            "path": str(png_path.relative_to(PROJECT_DIR)),
            "size_bytes": png_path.stat().st_size,
            "stale": png_mtime < scad_mtime,
        }
    else:
        status["png"] = None

    return status


@mcp.tool()
def check_environment() -> dict:
    """Check that OpenSCAD, BOSL2, and all dependencies are properly installed."""
    env = {}

    try:
        env["openscad_version"] = get_version()
        env["openscad_ok"] = True
    except Exception as e:
        env["openscad_ok"] = False
        env["openscad_error"] = str(e)

    bosl2 = find_bosl2()
    env["bosl2_ok"] = bosl2 is not None
    env["bosl2_path"] = str(bosl2) if bosl2 else None

    env["display"] = os.environ.get("DISPLAY", "none (headless)")
    env["xvfb"] = bool(os.popen("which xvfb-run 2>/dev/null").read().strip())
    env["mqtt_broker"] = os.environ.get("MQTT_BROKER", "localhost")
    env["mqtt_port"] = int(os.environ.get("MQTT_PORT", "1883"))

    return env


# ---------------------------------------------------------------------------
# RESOURCES — User/app-controlled, loaded into Claude's context on demand
# ---------------------------------------------------------------------------


@mcp.resource("bosl2://quickref")
def bosl2_quickref() -> str:
    """BOSL2 quick reference card — common functions, shapes, patterns, and mechanical parts."""
    ref_path = PROJECT_DIR / "docs" / "bosl2-quickref.md"
    if ref_path.is_file():
        return ref_path.read_text()
    return "BOSL2 quick reference not found at docs/bosl2-quickref.md"


@mcp.resource("bosl2://attachments")
def bosl2_attachments() -> str:
    """BOSL2 attachment system — anchors, positioning, and the attach() function."""
    return """# BOSL2 Attachment System

## Core Concept
Every BOSL2 shape has named anchor points. Use `attach()` to position children relative to parents.

## Anchor Names
- `TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `FRONT`, `BACK` — face centers
- `TOP+LEFT`, `BOTTOM+FRONT+RIGHT` — edge/corner anchors
- `CENTER` — origin

## attach() Function
```openscad
// Attach child's BOTTOM to parent's TOP
attach(TOP) cuboid([10,10,5]);

// Attach with specific child anchor
attach(TOP, BOTTOM) cyl(d=8, h=10);

// Position at anchor without reorienting
position(TOP) cuboid([5,5,5]);
```

## diff() with Attachments
```openscad
diff()
  cuboid([30,30,10]) {
    // Children with tag("remove") are subtracted
    attach(TOP) tag("remove") cyl(d=5, h=12, anchor=BOTTOM);
  }
```

## Key Rules
1. `attach(FROM)` — child's default anchor connects to parent's FROM anchor
2. `attach(FROM, TO)` — child's TO anchor connects to parent's FROM anchor
3. Use `overlap=0.01` in attach() to prevent Z-fighting in boolean ops
4. `tag("remove")` inside `diff()` marks geometry for subtraction
5. `tag("keep")` inside `diff()` prevents subtraction of specific children

## Common Patterns
```openscad
// Mounting holes in corners
diff()
  cuboid([40,40,5])
    attach(TOP) tag("remove")
      grid_copies(spacing=30, n=[2,2])
        cyl(d=3.2, h=8, anchor=BOTTOM);

// Stacked shapes
cuboid([20,20,10])
  attach(TOP) cyl(d=15, h=8, anchor=BOTTOM)
    attach(TOP) cuboid([10,10,5], anchor=BOTTOM);
```
"""


@mcp.resource("bosl2://threading")
def bosl2_threading() -> str:
    """BOSL2 threading and screws — threaded rods, nuts, and screw holes."""
    return """# BOSL2 Threading & Screws

## Include
```openscad
include <BOSL2/std.scad>
include <BOSL2/screws.scad>
```

## Screw Holes
```openscad
// Simple through-hole for M3 screw
cyl(d=3.2, h=10);  // 0.2mm clearance

// Countersunk hole
diff()
  cuboid([20,20,5])
    attach(TOP) tag("remove") {
      cyl(d=3.2, h=8, anchor=TOP);           // shaft
      cyl(d1=3.2, d2=6.4, h=1.8, anchor=TOP); // countersink
    }
```

## Common Screw Clearances
| Screw | Shaft Hole | Head Hole | Countersink Depth |
|-------|-----------|-----------|-------------------|
| M2    | 2.2mm     | 4.4mm     | 1.2mm            |
| M2.5  | 2.7mm     | 5.0mm     | 1.5mm            |
| M3    | 3.2mm     | 6.4mm     | 1.8mm            |
| M4    | 4.3mm     | 8.2mm     | 2.3mm            |
| M5    | 5.3mm     | 10.0mm    | 2.8mm            |

## Heat-Set Insert Holes
```openscad
// M3 heat-set insert (typical)
cyl(d=4.0, h=5.5);  // Check insert datasheet
```

## Standoffs
```openscad
// M3 standoff
diff()
  cyl(d=6, h=10)
    attach(TOP) tag("remove") cyl(d=3.2, h=12, anchor=TOP);
```
"""


@mcp.resource("bosl2://rounding")
def bosl2_rounding() -> str:
    """BOSL2 rounding and chamfering — edge treatments for printability and aesthetics."""
    return """# BOSL2 Rounding & Chamfering

## cuboid() Rounding
```openscad
// Round all edges
cuboid([30,20,10], rounding=2);

// Round only top edges (print-friendly)
cuboid([30,20,10], rounding=2, edges=TOP);

// Round specific edges
cuboid([30,20,10], rounding=2, edges=[TOP+FRONT, TOP+BACK]);

// Chamfer instead of round
cuboid([30,20,10], chamfer=1, edges=TOP);
```

## cyl() Rounding
```openscad
// Round top and bottom of cylinder
cyl(d=20, h=10, rounding1=2, rounding2=2);

// Round only top
cyl(d=20, h=10, rounding2=2);

// Chamfer
cyl(d=20, h=10, chamfer1=1);
```

## Print-Friendly Rules
1. **Bottom edges**: Use chamfer (not round) for bed adhesion: `chamfer1=0.5`
2. **Top edges**: Rounding is fine: `rounding2=2`
3. **Vertical edges**: Round freely: `rounding=2, edges="Z"`
4. **Max radius**: Keep rounding radius < half the shortest dimension
5. **$fn matters**: Higher $fn = smoother rounds but slower render
   - Preview: `$fn = 32`
   - Final render: `$fn = 64` or higher
"""


@mcp.resource("bosl2://patterns")
def bosl2_patterns() -> str:
    """BOSL2 array patterns — grid, linear, arc, and path distribution."""
    return """# BOSL2 Patterns & Arrays

## grid_copies()
```openscad
// 2x3 grid of cylinders
grid_copies(spacing=10, n=[2,3])
  cyl(d=5, h=3);

// Different X/Y spacing
grid_copies(spacing=[15,10], n=[3,2])
  cuboid([8,8,5]);
```

## linear_copies()
```openscad
// 5 items along X axis
linear_copies(spacing=12, n=5)
  cyl(d=5, h=10);

// Along arbitrary vector
linear_copies(spacing=10, n=4, dir=UP)
  sphere(d=5);
```

## rot_copies()
```openscad
// 6 items in a circle
rot_copies(n=6, r=20)
  cyl(d=5, h=10);

// Partial arc (90 degrees)
rot_copies(n=4, r=20, sa=0, ea=90)
  cuboid([5,5,10]);
```

## Combining with diff()
```openscad
// Hole pattern
diff()
  cuboid([60,40,5])
    attach(TOP) tag("remove")
      grid_copies(spacing=[20,15], n=[3,2])
        cyl(d=3.2, h=8, anchor=BOTTOM);
```

## path_copies()
```openscad
// Distribute along a path
path = arc(r=30, angle=180, n=8);
path_copies(path)
  cyl(d=3, h=5);
```
"""


@mcp.resource("bosl2://examples/mounting-plate")
def bosl2_example_mounting() -> str:
    """Example: parametric mounting plate with holes, rounding, and print-friendly design."""
    return """# Example: Parametric Mounting Plate

```openscad
include <BOSL2/std.scad>

// === Parameters ===
plate_width = 60;
plate_depth = 40;
plate_height = 4;
corner_rounding = 3;

hole_diameter = 3.2;      // M3 clearance
hole_spacing_x = 50;
hole_spacing_y = 30;
hole_count_x = 2;
hole_count_y = 2;

center_hole = true;
center_hole_dia = 8;

// === Design ===
diff()
  cuboid(
    [plate_width, plate_depth, plate_height],
    rounding = corner_rounding,
    edges = "Z",               // Only round vertical edges (print-friendly)
    chamfer = 0.5,
    except = "Z"               // Chamfer top/bottom edges
  ) {
    // Corner mounting holes
    attach(TOP) tag("remove")
      grid_copies(
        spacing = [hole_spacing_x, hole_spacing_y],
        n = [hole_count_x, hole_count_y]
      )
        cyl(d = hole_diameter, h = plate_height + 2, anchor = BOTTOM);

    // Optional center hole
    if (center_hole)
      attach(TOP) tag("remove")
        cyl(d = center_hole_dia, h = plate_height + 2, anchor = BOTTOM);
  }
```

## Key Patterns Used
- `diff()` + `tag("remove")` for boolean subtraction
- `grid_copies()` for hole arrays
- `edges = "Z"` for print-friendly rounding (vertical edges only)
- `chamfer` on top/bottom for bed adhesion
- `anchor = BOTTOM` on holes ensures they start at the surface
- `h = plate_height + 2` ensures holes fully penetrate (no thin skin)
"""


@mcp.tool()
def save_design_iteration(file_path: str) -> dict:
    """Save a numbered snapshot of the current design for iteration tracking.
    Creates files like design_v001.scad, design_v002.scad in output/iterations/.
    Use this before making significant changes to preserve rollback points.

    Args:
        file_path: Path to .scad file (relative to project root or absolute)
    """
    resolved = _resolve_path(file_path)
    iterations_dir = str(PROJECT_DIR / "output" / "iterations")
    result = save_iteration(resolved, iterations_dir)

    mqtt_client.publish_event("design", "iteration_saved", {
        "file": resolved,
        "version": result["version"],
        "iteration_file": result["file_path"],
    })

    return result


@mcp.tool()
def list_design_iterations(design_name: str) -> dict:
    """List all saved iteration snapshots of a design.

    Args:
        design_name: Design name without extension (e.g., "sample-bracket")
    """
    iterations_dir = str(PROJECT_DIR / "output" / "iterations")
    versions = list_iterations(design_name, iterations_dir)
    return {"design": design_name, "count": len(versions), "iterations": versions}


@mcp.tool()
def get_latest_design_iteration(design_name: str) -> dict:
    """Get the most recent saved iteration of a design.

    Args:
        design_name: Design name without extension (e.g., "sample-bracket")
    """
    iterations_dir = str(PROJECT_DIR / "output" / "iterations")
    latest = get_latest_iteration(design_name, iterations_dir)
    if latest is None:
        return {"error": f"No iterations found for '{design_name}'"}
    return latest


@mcp.resource("bosl2://prompts/image-to-code")
def prompt_image_to_code() -> str:
    """Structured prompt template for generating OpenSCAD code from an image or sketch description."""
    return """# Image/Sketch to OpenSCAD Code: Prompt Template

## When to Use
Use this template when you have a photo, sketch, or description of a physical object
and want to generate parametric OpenSCAD + BOSL2 code to recreate it.

## Step 1: Analyze the Image/Description

Before writing code, identify:
- **Primary shape:** What is the base geometry? (box, cylinder, L-bracket, plate, etc.)
- **Features:** What subtractive features exist? (holes, slots, cutouts, chamfers)
- **Additive features:** What is attached on top? (bosses, standoffs, ribs, walls)
- **Symmetry:** Is the object symmetric along any axis?
- **Construction sequence:** How would you build this from primitives?

## Step 2: Gather Dimensions

Critical: LLMs cannot measure from images. You MUST either:
- Ask the user for key dimensions (width, height, depth, hole diameters)
- Ask the user to measure the real object with calipers
- Make reasonable estimates and document them as parameters the user can adjust

## Step 3: Generate Code

Use this structure:

```openscad
include <BOSL2/std.scad>

// === Parameters (USER: adjust these to match your object) ===
width = 60;       // [mm] Measured or estimated
depth = 40;       // [mm]
height = 10;      // [mm]

hole_diameter = 3.2;    // M3 clearance
wall_thickness = 2.5;   // Minimum for FDM printing
rounding = 2;           // Edge rounding radius

$fn = 32;  // Preview quality (use 64+ for final render)

// === Design ===
// [BOSL2 code using diff(), attach(), grid_copies(), etc.]
```

## Step 4: Self-Critique via Multi-View Render

After generating code:
1. Use `render_design_views` to get front/top/right/isometric PNGs
2. Examine each view for:
   - **Proportions:** Do width/height/depth ratios match the reference?
   - **Feature placement:** Are holes, slots, and cutouts in the right positions?
   - **Missing features:** Is anything from the reference image not represented?
   - **Topology errors:** Are there floating geometry or Z-fighting artifacts?
3. Edit the code to fix issues
4. Re-render and re-examine (repeat 2-4 times)

## Common Object Patterns

### Enclosure / Box
```openscad
diff()
  cuboid([width, depth, height], rounding=2, edges="Z")
    attach(TOP) tag("remove")
      cuboid([width-wall*2, depth-wall*2, height], anchor=TOP);
```

### L-Bracket
```openscad
cuboid([base_w, base_d, base_h])
  attach(BACK, BOTTOM) cuboid([base_w, wall, arm_h]);
```

### Mounting Plate with Holes
```openscad
diff()
  cuboid([w, d, h], rounding=r, edges="Z")
    attach(TOP) tag("remove")
      grid_copies(spacing=[sx, sy], n=[2,2])
        cyl(d=hole_d, h=h+2, anchor=BOTTOM);
```
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_path(file_path: str) -> str:
    """Resolve a file path — if relative, prepend project root."""
    p = Path(file_path)
    if p.is_absolute():
        return str(p)
    resolved = PROJECT_DIR / p
    return str(resolved)
