# Pathway 5: Agentic Visual Feedback Loop — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Claude to generate OpenSCAD code from image descriptions, render multi-view previews, self-critique the renders, and iterate — all through MCP tools.

**Architecture:** Extends the existing MCP server (`mcp_server/server.py`) with new tools for multi-view rendering and design iteration, plus new resources for image-to-code prompting. The OpenSCAD wrapper (`mcp_server/openscad.py`) gets a `render_multi_view()` function. A new `versioning.py` module handles design iteration tracking with auto-numbered file copies.

**Tech Stack:** Python 3.12, FastMCP 3.1, OpenSCAD 2025.05.02 AppImage, xvfb-run (headless), paho-mqtt 2.1

---

## Phase 1: Core Feedback Loop

### Task 1: Add `render_multi_view()` to OpenSCAD wrapper

**Files:**
- Modify: `mcp_server/openscad.py` (add function after `render_png` at line ~240)
- Test: `tests/test_openscad.py` (create)

**Step 1: Write the failing test**

Create `tests/test_openscad.py`:

```python
"""Tests for OpenSCAD wrapper — multi-view rendering."""
import os
import tempfile
from pathlib import Path

from mcp_server.openscad import render_multi_view, PROJECT_DIR

SAMPLE_BRACKET = str(PROJECT_DIR / "designs" / "examples" / "sample-bracket.scad")


def test_render_multi_view_returns_all_views():
    """render_multi_view should return front, top, right, and isometric PNGs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = render_multi_view(SAMPLE_BRACKET, output_dir=tmpdir)

        assert result["success"] is True
        assert len(result["views"]) == 4

        expected_views = {"front", "top", "right", "isometric"}
        actual_views = {v["view"] for v in result["views"]}
        assert actual_views == expected_views

        for view in result["views"]:
            assert Path(view["file_path"]).is_file()
            assert Path(view["file_path"]).stat().st_size > 0


def test_render_multi_view_file_not_found():
    """render_multi_view should return error for missing file."""
    result = render_multi_view("/nonexistent/file.scad")
    assert result["success"] is False
    assert "not found" in result["errors"][0].lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_openscad.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_multi_view'`

**Step 3: Write minimal implementation**

Add to `mcp_server/openscad.py` after the `render_png` function (after line 240):

```python
# Camera angles: translate_x,y,z,rot_x,y,z,distance
# rot_x = pitch (tilt up/down), rot_y = roll, rot_z = yaw (rotate around vertical)
MULTI_VIEW_CAMERAS = {
    "front":     "0,0,0,90,0,0,0",     # Looking at front face (XZ plane)
    "top":       "0,0,0,0,0,0,0",       # Looking down (XY plane)
    "right":     "0,0,0,90,0,90,0",     # Looking at right face (YZ plane)
    "isometric": "0,0,0,55,0,25,0",     # Classic isometric angle
}


def render_multi_view(
    scad_file: str,
    output_dir: str | None = None,
    imgsize: str = "800,600",
    colorscheme: str = "Tomorrow",
) -> dict:
    """Render front, top, right, and isometric PNG views of a design.

    Returns dict with 'success', 'views' (list of per-view results), 'errors'.
    Each view entry has: 'view', 'file_path', 'size_bytes'.
    """
    scad_path = Path(scad_file)
    if not scad_path.is_file():
        return {"success": False, "views": [], "errors": [f"File not found: {scad_file}"]}

    if output_dir is None:
        output_dir = str(PROJECT_DIR / "output" / "png")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    views = []
    errors = []

    for view_name, camera in MULTI_VIEW_CAMERAS.items():
        out_file = Path(output_dir) / f"{scad_path.stem}_{view_name}.png"

        args = [
            "--render",
            f"--imgsize={imgsize}",
            f"--colorscheme={colorscheme}",
            f"--camera={camera}",
            "--viewall",
            "--autocenter",
            "-o", str(out_file),
            str(scad_path),
        ]

        import time
        start = time.monotonic()
        result = _run_openscad(args, timeout=120)
        elapsed = int((time.monotonic() - start) * 1000)

        if out_file.is_file() and out_file.stat().st_size > 0:
            views.append({
                "view": view_name,
                "file_path": str(out_file),
                "size_bytes": out_file.stat().st_size,
                "duration_ms": elapsed,
            })
            log.info("Multi-view %s rendered: %s (%dms)", view_name, out_file, elapsed)
        else:
            err_msgs, _ = _parse_output(result.stderr)
            errors.extend(err_msgs or [f"{view_name} render failed"])

    success = len(views) == len(MULTI_VIEW_CAMERAS)
    return {"success": success, "views": views, "errors": errors or None}
```

**Step 4: Run test to verify it passes**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_openscad.py -v`
Expected: PASS (both tests)

**Step 5: Commit**

```bash
git add mcp_server/openscad.py tests/test_openscad.py
git commit -m "feat: add render_multi_view to OpenSCAD wrapper"
```

---

### Task 2: Add `render_multi_view` MCP tool to server

**Files:**
- Modify: `mcp_server/server.py` (add tool, add import)
- Test: `tests/test_server_tools.py` (create)

**Step 1: Write the failing test**

Create `tests/test_server_tools.py`:

```python
"""Tests for MCP server tools — multi-view rendering."""
import json
import subprocess
import time


def _call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool via JSON-RPC stdio and return the parsed result."""
    init = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    })
    notify = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    call = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}
    })

    proc = subprocess.Popen(
        [".venv/bin/python", "-m", "mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd="/home/tie/OpenScad_AI",
    )
    proc.stdin.write(init + "\n" + notify + "\n" + call + "\n")
    proc.stdin.close()
    time.sleep(8)  # Allow time for OpenSCAD renders
    output = proc.stdout.read()
    proc.terminate()

    for line in output.strip().split("\n"):
        data = json.loads(line)
        if data.get("id") == 2:
            content = data["result"]["content"][0]["text"]
            return json.loads(content)
    raise RuntimeError("No response for tool call")


def test_render_multi_view_tool():
    """The render_multi_view MCP tool should return 4 views."""
    result = _call_mcp_tool("render_multi_view", {
        "file_path": "designs/examples/sample-bracket.scad"
    })
    assert result["success"] is True
    assert len(result["views"]) == 4
    view_names = {v["view"] for v in result["views"]}
    assert "front" in view_names
    assert "isometric" in view_names
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_server_tools.py::test_render_multi_view_tool -v`
Expected: FAIL (tool "render_multi_view" not found)

**Step 3: Write minimal implementation**

Add to `mcp_server/server.py`:

1. Update import at line 16 to include `render_multi_view`:
```python
from mcp_server.openscad import (
    PROJECT_DIR,
    find_bosl2,
    get_version,
    render_multi_view,
    render_png,
    render_stl,
    validate,
)
```

2. Add new tool after `render_png_preview` (after line 108):
```python
@mcp.tool()
def render_multi_view(
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
    from mcp_server.openscad import render_multi_view as _render_multi_view

    resolved = _resolve_path(file_path)
    result = _render_multi_view(resolved, imgsize=imgsize, colorscheme=colorscheme)

    mqtt_client.publish_event("render", "multi_view", {
        "file": resolved,
        "status": "success" if result["success"] else "failed",
        "view_count": len(result["views"]),
    })

    return result
```

**Note:** The tool function name will shadow the import. Use a local import alias inside the tool to avoid the collision. Alternatively, name the tool function `render_multi_view_tool` but set a display name. The simplest fix: rename the tool function to `render_design_views`.

Corrected tool definition:
```python
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
```

Update the test to call `render_design_views` instead of `render_multi_view`.

**Step 4: Run test to verify it passes**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_server_tools.py::test_render_multi_view_tool -v`
Expected: PASS

**Step 5: Commit**

```bash
git add mcp_server/server.py tests/test_server_tools.py
git commit -m "feat: add render_design_views MCP tool for multi-angle preview"
```

---

### Task 3: Add `bosl2://prompts/image-to-code` resource

**Files:**
- Modify: `mcp_server/server.py` (add resource after existing resources, ~line 530)

**Step 1: Write the failing test**

Add to `tests/test_server_tools.py`:

```python
def test_image_to_code_resource_exists():
    """The bosl2://prompts/image-to-code resource should be listed."""
    init = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    })
    notify = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    resources = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "resources/list"})

    proc = subprocess.Popen(
        [".venv/bin/python", "-m", "mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd="/home/tie/OpenScad_AI",
    )
    proc.stdin.write(init + "\n" + notify + "\n" + resources + "\n")
    proc.stdin.close()
    time.sleep(2)
    output = proc.stdout.read()
    proc.terminate()

    for line in output.strip().split("\n"):
        data = json.loads(line)
        if data.get("id") == 2:
            uris = [r["uri"] for r in data["result"]["resources"]]
            assert "bosl2://prompts/image-to-code" in uris
            return
    raise RuntimeError("No response for resources/list")
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_server_tools.py::test_image_to_code_resource_exists -v`
Expected: FAIL (`bosl2://prompts/image-to-code` not in list)

**Step 3: Write minimal implementation**

Add to `mcp_server/server.py` in the RESOURCES section:

```python
@mcp.resource("bosl2://prompts/image-to-code")
def prompt_image_to_code() -> str:
    """Structured prompt template for generating OpenSCAD code from an image or sketch description."""
    return """# Image/Sketch → OpenSCAD Code: Prompt Template

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
// Overall dimensions
width = 60;       // [mm] Measured or estimated
depth = 40;       // [mm]
height = 10;      // [mm]

// Feature dimensions
hole_diameter = 3.2;    // M3 clearance
wall_thickness = 2.5;   // Minimum for FDM printing
rounding = 2;           // Edge rounding radius

// Print settings
$fn = 32;  // Preview quality (use 64+ for final render)

// === Design ===
// [Your BOSL2 code here using diff(), attach(), grid_copies(), etc.]
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

## Tips for Better Results

- **Decompose complex objects:** Build each major section as a separate module
- **Start with the base shape:** Get the overall envelope right before adding features
- **Use BOSL2 attachments:** `attach(TOP)`, `attach(RIGHT)` instead of manual positioning
- **Boolean ops last:** Add all positive geometry first, then subtract holes/slots with `diff()`
- **Explicit over implicit:** Name every dimension as a parameter, even if estimated
- **Print-friendly defaults:** chamfer bottoms (0.5mm), round tops, min 2mm walls

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

### Cylindrical Standoff
```openscad
diff()
  cyl(d=outer_d, h=standoff_h)
    attach(TOP) tag("remove") cyl(d=hole_d, h=standoff_h+2, anchor=TOP);
```
"""
```

**Step 4: Run test to verify it passes**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_server_tools.py::test_image_to_code_resource_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add mcp_server/server.py tests/test_server_tools.py
git commit -m "feat: add image-to-code prompt template as MCP resource"
```

---

## Phase 2: Iteration Support

### Task 4: Add `versioning.py` module for design iteration tracking

**Files:**
- Create: `mcp_server/versioning.py`
- Test: `tests/test_versioning.py` (create)

**Step 1: Write the failing test**

Create `tests/test_versioning.py`:

```python
"""Tests for design versioning — auto-numbered iteration copies."""
import tempfile
from pathlib import Path

from mcp_server.versioning import (
    save_iteration,
    list_iterations,
    get_latest_iteration,
)


def test_save_first_iteration():
    """First save creates design_v001.scad."""
    with tempfile.TemporaryDirectory() as tmpdir:
        design = Path(tmpdir) / "bracket.scad"
        design.write_text("// v1 code")

        result = save_iteration(str(design), tmpdir)
        assert result["version"] == 1
        assert result["file_path"].endswith("bracket_v001.scad")
        assert Path(result["file_path"]).read_text() == "// v1 code"


def test_save_increments_version():
    """Each save increments version number."""
    with tempfile.TemporaryDirectory() as tmpdir:
        design = Path(tmpdir) / "bracket.scad"
        design.write_text("// v1")
        save_iteration(str(design), tmpdir)

        design.write_text("// v2")
        result = save_iteration(str(design), tmpdir)
        assert result["version"] == 2
        assert result["file_path"].endswith("bracket_v002.scad")
        assert Path(result["file_path"]).read_text() == "// v2"


def test_list_iterations():
    """list_iterations returns all saved versions in order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        design = Path(tmpdir) / "widget.scad"
        for i in range(3):
            design.write_text(f"// version {i+1}")
            save_iteration(str(design), tmpdir)

        versions = list_iterations("widget", tmpdir)
        assert len(versions) == 3
        assert versions[0]["version"] == 1
        assert versions[2]["version"] == 3


def test_get_latest_iteration():
    """get_latest_iteration returns the highest version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        design = Path(tmpdir) / "part.scad"
        design.write_text("// v1")
        save_iteration(str(design), tmpdir)
        design.write_text("// v2")
        save_iteration(str(design), tmpdir)

        latest = get_latest_iteration("part", tmpdir)
        assert latest["version"] == 2
        assert Path(latest["file_path"]).read_text() == "// v2"


def test_get_latest_iteration_none():
    """get_latest_iteration returns None when no versions exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_latest_iteration("nonexistent", tmpdir)
        assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_versioning.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mcp_server.versioning'`

**Step 3: Write minimal implementation**

Create `mcp_server/versioning.py`:

```python
"""Design iteration versioning — auto-numbered copies for tracking design evolution."""

import logging
import re
import shutil
from pathlib import Path

log = logging.getLogger(__name__)


def save_iteration(scad_file: str, iterations_dir: str) -> dict:
    """Save a numbered copy of the current design file.

    Creates: {stem}_v001.scad, {stem}_v002.scad, etc.
    Returns: {"version": int, "file_path": str}
    """
    src = Path(scad_file)
    dest_dir = Path(iterations_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    stem = src.stem
    next_version = _next_version(stem, dest_dir)
    dest = dest_dir / f"{stem}_v{next_version:03d}.scad"

    shutil.copy2(str(src), str(dest))
    log.info("Saved iteration: %s (v%03d)", dest, next_version)

    return {"version": next_version, "file_path": str(dest)}


def list_iterations(design_name: str, iterations_dir: str) -> list[dict]:
    """List all saved iterations of a design, ordered by version.

    Returns: [{"version": int, "file_path": str, "size_bytes": int, "modified": float}]
    """
    dest_dir = Path(iterations_dir)
    if not dest_dir.is_dir():
        return []

    pattern = re.compile(rf"^{re.escape(design_name)}_v(\d{{3}})\.scad$")
    versions = []

    for f in sorted(dest_dir.iterdir()):
        match = pattern.match(f.name)
        if match:
            stat = f.stat()
            versions.append({
                "version": int(match.group(1)),
                "file_path": str(f),
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })

    return versions


def get_latest_iteration(design_name: str, iterations_dir: str) -> dict | None:
    """Return the latest iteration of a design, or None if none exist."""
    versions = list_iterations(design_name, iterations_dir)
    return versions[-1] if versions else None


def _next_version(stem: str, dest_dir: Path) -> int:
    """Determine the next version number by scanning existing files."""
    pattern = re.compile(rf"^{re.escape(stem)}_v(\d{{3}})\.scad$")
    max_version = 0
    for f in dest_dir.iterdir():
        match = pattern.match(f.name)
        if match:
            max_version = max(max_version, int(match.group(1)))
    return max_version + 1
```

**Step 4: Run test to verify it passes**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_versioning.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add mcp_server/versioning.py tests/test_versioning.py
git commit -m "feat: add design versioning module for iteration tracking"
```

---

### Task 5: Add versioning MCP tools to server

**Files:**
- Modify: `mcp_server/server.py` (add 3 tools, add import)

**Step 1: Write the failing test**

Add to `tests/test_server_tools.py`:

```python
def test_save_design_iteration_tool():
    """The save_design_iteration tool should create a versioned copy."""
    result = _call_mcp_tool("save_design_iteration", {
        "file_path": "designs/examples/sample-bracket.scad"
    })
    assert result["version"] >= 1
    assert "sample-bracket_v" in result["file_path"]


def test_list_design_iterations_tool():
    """The list_design_iterations tool should return saved versions."""
    # First save one to make sure there's at least one
    _call_mcp_tool("save_design_iteration", {
        "file_path": "designs/examples/sample-bracket.scad"
    })
    result = _call_mcp_tool("list_design_iterations", {
        "design_name": "sample-bracket"
    })
    assert len(result["iterations"]) >= 1
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_server_tools.py::test_save_design_iteration_tool -v`
Expected: FAIL (tool not found)

**Step 3: Write minimal implementation**

Add imports to `mcp_server/server.py`:
```python
from mcp_server.versioning import (
    save_iteration,
    list_iterations,
    get_latest_iteration,
)
```

Add tools:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_server_tools.py -v`
Expected: PASS (all tests)

**Step 5: Add `output/iterations/` to .gitignore and commit**

Add to `.gitignore`:
```
output/iterations/
```

```bash
git add mcp_server/server.py mcp_server/versioning.py tests/test_server_tools.py .gitignore
git commit -m "feat: add design iteration versioning tools to MCP server"
```

---

### Task 6: Final integration test — full feedback loop

**Files:**
- Test: `tests/test_feedback_loop.py` (create)

**Step 1: Write the integration test**

Create `tests/test_feedback_loop.py`:

```python
"""Integration test: full agentic visual feedback loop.

Simulates the complete Pathway 5 cycle:
1. Create design from template
2. Save initial iteration
3. Render multi-view
4. Validate design
5. Render STL
"""
import json
import subprocess
import time


def _call_tool(name: str, args: dict) -> dict:
    init = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    })
    notify = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    call = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": name, "arguments": args}
    })

    proc = subprocess.Popen(
        [".venv/bin/python", "-m", "mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd="/home/tie/OpenScad_AI",
    )
    proc.stdin.write(init + "\n" + notify + "\n" + call + "\n")
    proc.stdin.close()
    time.sleep(12)
    output = proc.stdout.read()
    proc.terminate()

    for line in output.strip().split("\n"):
        data = json.loads(line)
        if data.get("id") == 2:
            content = data["result"]["content"][0]["text"]
            return json.loads(content)
    raise RuntimeError(f"No response for {name}")


def test_full_feedback_loop():
    """End-to-end: validate → multi-view render → save iteration → render STL."""
    design = "designs/examples/sample-bracket.scad"

    # Step 1: Validate
    result = _call_tool("validate_design", {"file_path": design})
    assert result["overall"] is True, f"Validation failed: {result['errors']}"

    # Step 2: Multi-view render
    result = _call_tool("render_design_views", {"file_path": design})
    assert result["success"] is True
    assert len(result["views"]) == 4

    # Step 3: Save iteration
    result = _call_tool("save_design_iteration", {"file_path": design})
    assert result["version"] >= 1

    # Step 4: Render STL
    result = _call_tool("render_stl_file", {"file_path": design})
    assert result["success"] is True
    assert result["size_bytes"] > 0
```

**Step 2: Run the integration test**

Run: `cd /home/tie/OpenScad_AI && source .venv/bin/activate && python -m pytest tests/test_feedback_loop.py -v --timeout=120`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_feedback_loop.py
git commit -m "test: add end-to-end integration test for visual feedback loop"
```

---

## Verification Checklist

After all tasks complete, verify:

```bash
# All tests pass
cd /home/tie/OpenScad_AI && source .venv/bin/activate
python -m pytest tests/ -v

# MCP server lists all tools
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | .venv/bin/python -m mcp_server 2>/dev/null | python -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    if d.get('id') == 2:
        for t in d['result']['tools']:
            print(f'  {t[\"name\"]}')"
```

Expected tools (11 total):
```
  validate_design
  render_stl_file
  render_png_preview
  render_design_views        ← NEW
  list_designs
  create_from_template
  get_design_status
  check_environment
  save_design_iteration      ← NEW
  list_design_iterations     ← NEW
  get_latest_design_iteration ← NEW
```

Expected resources (7 total):
```
  bosl2://quickref
  bosl2://attachments
  bosl2://threading
  bosl2://rounding
  bosl2://patterns
  bosl2://examples/mounting-plate
  bosl2://prompts/image-to-code   ← NEW
```
