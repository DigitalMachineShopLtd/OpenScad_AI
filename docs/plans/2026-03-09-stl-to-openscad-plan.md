# STL-to-OpenSCAD Conversion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three-tier STL-to-OpenSCAD conversion (import wrapper → primitive fitting → AI visual reverse engineering) with RAG storage in the `design_history` collection.

**Architecture:** New module `mcp_server/stl_converter.py` handles mesh analysis via `trimesh`, primitive fitting via bounding box / convex hull heuristics, and import wrapper `.scad` generation. Three new MCP tools (`analyze_stl`, `convert_stl_to_scad`, `reverse_engineer_stl`) are added to `server.py`. Multi-view rendering of STLs reuses the existing `render_multi_view()` pipeline by generating a temporary `.scad` file with `import()`. All results stored in RAG `design_history` collection via existing `rag_client.store_chunks()`.

**Tech Stack:** trimesh (mesh I/O + analysis), existing OpenSCAD CLI wrapper, existing RAG client, FastMCP 3.1.0

**Design doc:** `docs/plans/2026-03-09-stl-to-openscad-design.md`

---

### Task 1: Add trimesh Dependency

**Files:**
- Modify: `requirements.txt`

**Context:** `trimesh` is a pure-Python mesh library. We only need the core (numpy-based) — no rendering dependencies. The project already has `numpy==2.4.2`.

**Step 1: Install trimesh and freeze**

```bash
source .venv/bin/activate
pip install trimesh
```

**Step 2: Add to requirements.txt**

Add `trimesh` with pinned version after installing. Find the installed version:

```bash
pip show trimesh | grep Version
```

Add to `requirements.txt` in alphabetical position (after `tenacity`, before `typing-inspection`).

**Step 3: Verify import works**

```bash
python -c "import trimesh; print(trimesh.__version__)"
```

Expected: Version string printed, no errors.

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add trimesh for STL mesh analysis"
```

---

### Task 2: Create STL Converter Module — Metadata Extraction

**Files:**
- Create: `mcp_server/stl_converter.py`
- Create: `tests/test_stl_converter.py`

**Context:** This task builds the core metadata extraction function. `trimesh.load()` returns a `Trimesh` object with `.bounds`, `.volume`, `.area`, `.vertices`, `.faces`, `.is_watertight`, and `.convex_hull`. We need a helper to create a tiny STL for testing — `trimesh.creation.box()` creates a unit cube mesh.

**Step 1: Write the failing tests**

Create `tests/test_stl_converter.py`:

```python
"""Tests for STL converter — metadata extraction, primitive fitting, code generation."""

import json
import os
import tempfile

import pytest
import trimesh

from mcp_server.stl_converter import extract_metadata


# ── extract_metadata ─────────────────────────────────────────────────────────

def _make_test_stl(mesh: trimesh.Trimesh) -> str:
    """Write a trimesh mesh to a temporary STL file, return path."""
    f = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
    mesh.export(f.name, file_type="stl")
    f.close()
    return f.name


def test_extract_metadata_cube():
    """Cube STL → correct bounding box, volume, face count."""
    mesh = trimesh.creation.box(extents=[10, 20, 30])
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        assert meta["bbox"] == pytest.approx([10.0, 20.0, 30.0], abs=0.1)
        assert meta["volume"] == pytest.approx(6000.0, rel=0.01)
        assert meta["face_count"] == 12  # cube = 6 faces * 2 triangles
        assert meta["vertex_count"] == 8
        assert meta["is_manifold"] is True
        assert meta["convex_hull_ratio"] == pytest.approx(1.0, abs=0.01)
        assert "surface_area" in meta
    finally:
        os.unlink(path)


def test_extract_metadata_cylinder():
    """Cylinder STL → correct bounding box dimensions."""
    mesh = trimesh.creation.cylinder(radius=10, height=40)
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        # Bounding box should be ~20 x 20 x 40
        assert meta["bbox"][0] == pytest.approx(20.0, abs=0.5)
        assert meta["bbox"][1] == pytest.approx(20.0, abs=0.5)
        assert meta["bbox"][2] == pytest.approx(40.0, abs=0.5)
        assert meta["is_manifold"] is True
    finally:
        os.unlink(path)


def test_extract_metadata_file_not_found():
    """Non-existent file → returns dict with error key."""
    meta = extract_metadata("/nonexistent/file.stl")
    assert "error" in meta
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/tie/OpenScad_AI
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: FAIL — `ImportError: cannot import name 'extract_metadata' from 'mcp_server.stl_converter'`

**Step 3: Write minimal implementation**

Create `mcp_server/stl_converter.py`:

```python
"""STL-to-OpenSCAD conversion — metadata extraction, primitive fitting, code generation."""

import logging
import os
from pathlib import Path

import trimesh

log = logging.getLogger(__name__)


def extract_metadata(stl_path: str) -> dict:
    """Load an STL file and extract geometric metadata.

    Returns dict with bbox, volume, surface_area, face_count, vertex_count,
    convex_hull_ratio, is_manifold, and source path. Returns {"error": ...}
    on failure.
    """
    if not os.path.isfile(stl_path):
        return {"error": f"File not found: {stl_path}"}

    try:
        mesh = trimesh.load(stl_path, force="mesh")
    except Exception as e:
        return {"error": f"Failed to load STL: {e}"}

    bounds = mesh.bounds  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
    bbox = [
        float(bounds[1][0] - bounds[0][0]),
        float(bounds[1][1] - bounds[0][1]),
        float(bounds[1][2] - bounds[0][2]),
    ]

    # Convex hull ratio: object volume / convex hull volume
    try:
        hull_volume = mesh.convex_hull.volume
        convex_hull_ratio = float(mesh.volume / hull_volume) if hull_volume > 0 else 0.0
    except Exception:
        convex_hull_ratio = 0.0

    return {
        "bbox": bbox,
        "volume": float(mesh.volume),
        "surface_area": float(mesh.area),
        "face_count": len(mesh.faces),
        "vertex_count": len(mesh.vertices),
        "convex_hull_ratio": convex_hull_ratio,
        "is_manifold": bool(mesh.is_watertight),
        "original_path": stl_path,
    }
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add mcp_server/stl_converter.py tests/test_stl_converter.py
git commit -m "feat: add STL metadata extraction with trimesh"
```

---

### Task 3: Import Wrapper Generation

**Files:**
- Modify: `mcp_server/stl_converter.py`
- Modify: `tests/test_stl_converter.py`

**Context:** Generate a `.scad` file containing `import("absolute/path/to/file.stl");` so OpenSCAD can render views of the STL. The wrapper file is written to `output/stl_imports/` to keep it separate from user designs.

**Step 1: Write the failing tests**

Append to `tests/test_stl_converter.py`:

```python
from mcp_server.stl_converter import generate_import_wrapper


def test_generate_import_wrapper():
    """Import wrapper creates a .scad file with import() statement."""
    mesh = trimesh.creation.box(extents=[10, 10, 10])
    stl_path = _make_test_stl(mesh)
    try:
        scad_path = generate_import_wrapper(stl_path)
        assert os.path.isfile(scad_path)
        assert scad_path.endswith(".scad")

        content = open(scad_path).read()
        assert f'import("{stl_path}")' in content
        assert "BOSL2" not in content  # import wrapper should not use BOSL2

        os.unlink(scad_path)
    finally:
        os.unlink(stl_path)


def test_generate_import_wrapper_missing_stl():
    """Non-existent STL → returns None."""
    result = generate_import_wrapper("/nonexistent/file.stl")
    assert result is None
```

**Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py::test_generate_import_wrapper -v
```

Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `mcp_server/stl_converter.py`:

```python
from mcp_server.openscad import PROJECT_DIR


def generate_import_wrapper(stl_path: str) -> str | None:
    """Generate a .scad file that imports the STL for rendering.

    Returns path to generated .scad file, or None if STL not found.
    """
    if not os.path.isfile(stl_path):
        return None

    abs_stl = os.path.abspath(stl_path)
    stem = Path(stl_path).stem

    output_dir = PROJECT_DIR / "output" / "stl_imports"
    output_dir.mkdir(parents=True, exist_ok=True)

    scad_path = output_dir / f"{stem}_import.scad"
    scad_content = (
        f'// Auto-generated import wrapper for {Path(stl_path).name}\n'
        f'// Source: {abs_stl}\n'
        f'\n'
        f'import("{abs_stl}");\n'
    )
    scad_path.write_text(scad_content)
    log.info("Generated import wrapper: %s", scad_path)

    return str(scad_path)
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 5 PASSED

**Step 5: Commit**

```bash
git add mcp_server/stl_converter.py tests/test_stl_converter.py
git commit -m "feat: add OpenSCAD import wrapper generation for STL files"
```

---

### Task 4: Primitive Fitting (Tier B)

**Files:**
- Modify: `mcp_server/stl_converter.py`
- Modify: `tests/test_stl_converter.py`

**Context:** Given metadata from `extract_metadata()`, attempt to fit the closest BOSL2 primitive (cuboid, cylinder, or sphere). Only attempt fitting when `convex_hull_ratio > 0.85`. Aspect ratio of bounding box determines shape:
- All three axes within 20% of each other → sphere
- Two axes within 20%, third >1.5x those → cylinder
- Otherwise → cuboid

**Step 1: Write the failing tests**

Append to `tests/test_stl_converter.py`:

```python
from mcp_server.stl_converter import fit_primitive


def test_fit_primitive_cuboid():
    """Box mesh → cuboid primitive with correct dimensions."""
    mesh = trimesh.creation.box(extents=[30, 20, 10])
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        result = fit_primitive(meta)
        assert result["primitive"] == "cuboid"
        assert result["scad_code"] is not None
        assert "cuboid" in result["scad_code"]
        assert "30" in result["scad_code"]
        assert result["confidence"] > 0.8
    finally:
        os.unlink(path)


def test_fit_primitive_cylinder():
    """Cylinder mesh → cylinder primitive."""
    mesh = trimesh.creation.cylinder(radius=10, height=40)
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        result = fit_primitive(meta)
        assert result["primitive"] == "cylinder"
        assert "cyl" in result["scad_code"]
        assert result["confidence"] > 0.5
    finally:
        os.unlink(path)


def test_fit_primitive_sphere():
    """Sphere mesh → sphere primitive."""
    mesh = trimesh.creation.icosphere(radius=15)
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        result = fit_primitive(meta)
        assert result["primitive"] == "sphere"
        assert "sphere" in result["scad_code"]
    finally:
        os.unlink(path)


def test_fit_primitive_complex_shape_fails():
    """Complex non-convex shape → primitive is None."""
    # Create an L-shape by combining two boxes (non-convex)
    box1 = trimesh.creation.box(extents=[10, 10, 30])
    box2 = trimesh.creation.box(extents=[30, 10, 10])
    box2.apply_translation([10, 0, -10])
    combined = trimesh.util.concatenate([box1, box2])

    path = _make_test_stl(combined)
    try:
        meta = extract_metadata(path)
        # Concatenated meshes may have high or low hull ratio depending on geometry
        # Force a low ratio to test the guard
        meta["convex_hull_ratio"] = 0.5
        result = fit_primitive(meta)
        assert result["primitive"] is None
        assert result["scad_code"] is None
    finally:
        os.unlink(path)
```

**Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py::test_fit_primitive_cuboid -v
```

Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `mcp_server/stl_converter.py`:

```python
def fit_primitive(metadata: dict) -> dict:
    """Attempt to fit the closest BOSL2 primitive to the mesh.

    Only attempts fitting when convex_hull_ratio > 0.85.

    Returns dict with 'primitive' (str|None), 'scad_code' (str|None),
    'confidence' (float).
    """
    if "error" in metadata:
        return {"primitive": None, "scad_code": None, "confidence": 0.0}

    hull_ratio = metadata.get("convex_hull_ratio", 0.0)
    if hull_ratio < 0.85:
        return {"primitive": None, "scad_code": None, "confidence": 0.0}

    bbox = metadata["bbox"]  # [x, y, z]
    x, y, z = sorted(bbox)  # small, medium, large

    # Check aspect ratios
    if x == 0:
        return {"primitive": None, "scad_code": None, "confidence": 0.0}

    ratio_med_small = y / x  # how similar the two smallest are
    ratio_large_med = z / y if y > 0 else 999

    # Sphere: all three axes within 20% of each other
    if ratio_med_small <= 1.2 and ratio_large_med <= 1.2:
        diameter = max(bbox)
        scad = _sphere_code(diameter, metadata, hull_ratio)
        return {"primitive": "sphere", "scad_code": scad, "confidence": hull_ratio}

    # Cylinder: two axes within 20%, third >1.5x
    if ratio_med_small <= 1.2 and ratio_large_med > 1.5:
        # The two similar axes are the diameter, the long axis is height
        diameter = (x + y) / 2  # average of the two similar dims
        height = z
        # Map back to original bbox to get correct axis
        scad = _cylinder_code(diameter, height, bbox, metadata, hull_ratio)
        return {"primitive": "cylinder", "scad_code": scad, "confidence": hull_ratio * 0.9}

    # Default: cuboid
    scad = _cuboid_code(bbox, metadata, hull_ratio)
    return {"primitive": "cuboid", "scad_code": scad, "confidence": hull_ratio}


def _sphere_code(diameter: float, meta: dict, confidence: float) -> str:
    d = round(diameter, 1)
    return (
        f"// Approximate primitive fit from STL analysis\n"
        f"// Source: {Path(meta.get('original_path', 'unknown')).name}\n"
        f"// Confidence: {confidence:.2f} (sphere)\n"
        f"// Bounding box: {meta['bbox'][0]:.1f} x {meta['bbox'][1]:.1f} x {meta['bbox'][2]:.1f} mm\n"
        f"\n"
        f"include <BOSL2/std.scad>\n"
        f"\n"
        f"sphere(d={d}, $fn=64);\n"
    )


def _cylinder_code(diameter: float, height: float, bbox: list, meta: dict, confidence: float) -> str:
    d = round(diameter, 1)
    h = round(height, 1)
    return (
        f"// Approximate primitive fit from STL analysis\n"
        f"// Source: {Path(meta.get('original_path', 'unknown')).name}\n"
        f"// Confidence: {confidence:.2f} (cylinder)\n"
        f"// Bounding box: {bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f} mm\n"
        f"\n"
        f"include <BOSL2/std.scad>\n"
        f"\n"
        f"cyl(d={d}, h={h}, $fn=64);\n"
    )


def _cuboid_code(bbox: list, meta: dict, confidence: float) -> str:
    dims = [round(d, 1) for d in bbox]
    return (
        f"// Approximate primitive fit from STL analysis\n"
        f"// Source: {Path(meta.get('original_path', 'unknown')).name}\n"
        f"// Confidence: {confidence:.2f} (cuboid)\n"
        f"// Bounding box: {bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f} mm\n"
        f"\n"
        f"include <BOSL2/std.scad>\n"
        f"\n"
        f"cuboid([{dims[0]}, {dims[1]}, {dims[2]}]);\n"
    )
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 9 PASSED

**Step 5: Commit**

```bash
git add mcp_server/stl_converter.py tests/test_stl_converter.py
git commit -m "feat: add primitive fitting for STL-to-BOSL2 conversion"
```

---

### Task 5: RAG Chunk Generation for STL Conversions

**Files:**
- Modify: `mcp_server/stl_converter.py`
- Modify: `tests/test_stl_converter.py`

**Context:** Create chunks for RAG storage from STL analysis results. Two chunks per conversion: metadata (JSON) and generated code. Uses existing `chunking.make_doc_id()` for dedup IDs with prefix `openscad_ai:stl_conversions/`.

**Step 1: Write the failing tests**

Append to `tests/test_stl_converter.py`:

```python
from mcp_server.stl_converter import make_stl_chunks


def test_make_stl_chunks_with_code():
    """Metadata + code → 2 chunks with correct IDs and content."""
    metadata = {
        "bbox": [10.0, 20.0, 30.0],
        "volume": 6000.0,
        "surface_area": 2200.0,
        "face_count": 12,
        "vertex_count": 8,
        "convex_hull_ratio": 1.0,
        "is_manifold": True,
        "original_path": "/tmp/test-cube.stl",
    }
    scad_code = "cuboid([10, 20, 30]);"

    chunks = make_stl_chunks("test-cube.stl", metadata, scad_code=scad_code)
    assert len(chunks) == 2

    # First chunk: metadata
    assert chunks[0]["id"] == "openscad_ai:stl_conversions/test-cube.stl:0"
    assert "6000" in chunks[0]["document"]
    assert chunks[0]["metadata"]["file_type"] == "stl_metadata"

    # Second chunk: code
    assert chunks[1]["id"] == "openscad_ai:stl_conversions/test-cube.stl:1"
    assert "cuboid" in chunks[1]["document"]
    assert chunks[1]["metadata"]["file_type"] == "stl_code"


def test_make_stl_chunks_metadata_only():
    """No code → single metadata chunk."""
    metadata = {
        "bbox": [10.0, 10.0, 10.0],
        "volume": 1000.0,
        "surface_area": 600.0,
        "face_count": 12,
        "vertex_count": 8,
        "convex_hull_ratio": 1.0,
        "is_manifold": True,
        "original_path": "/tmp/test.stl",
    }

    chunks = make_stl_chunks("test.stl", metadata)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["file_type"] == "stl_metadata"
```

**Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py::test_make_stl_chunks_with_code -v
```

Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `mcp_server/stl_converter.py`:

```python
import json


def make_stl_chunks(
    stl_filename: str,
    metadata: dict,
    scad_code: str | None = None,
    view_descriptions: str | None = None,
) -> list[dict]:
    """Create RAG chunks from STL analysis results.

    Returns list of chunk dicts ready for rag_client.store_chunks().
    Chunk 0: metadata (JSON), Chunk 1: generated code (if any),
    Chunk 2: view descriptions (if any).
    """
    base_id = f"openscad_ai:stl_conversions/{stl_filename}"
    chunks = []

    # Chunk 0: metadata as readable JSON
    meta_text = json.dumps(metadata, indent=2, default=str)
    chunks.append({
        "id": f"{base_id}:0",
        "document": meta_text,
        "metadata": {
            "source_repo": "openscad_ai",
            "file_path": f"stl_conversions/{stl_filename}",
            "file_type": "stl_metadata",
            "chunk_index": 0,
        },
    })

    # Chunk 1: generated OpenSCAD code
    if scad_code:
        chunks.append({
            "id": f"{base_id}:1",
            "document": scad_code,
            "metadata": {
                "source_repo": "openscad_ai",
                "file_path": f"stl_conversions/{stl_filename}",
                "file_type": "stl_code",
                "chunk_index": 1,
            },
        })

    # Chunk 2: view descriptions (for Tier C AI analysis)
    if view_descriptions:
        chunks.append({
            "id": f"{base_id}:{len(chunks)}",
            "document": view_descriptions,
            "metadata": {
                "source_repo": "openscad_ai",
                "file_path": f"stl_conversions/{stl_filename}",
                "file_type": "stl_views",
                "chunk_index": len(chunks),
            },
        })

    return chunks
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 11 PASSED

**Step 5: Commit**

```bash
git add mcp_server/stl_converter.py tests/test_stl_converter.py
git commit -m "feat: add RAG chunk generation for STL conversion results"
```

---

### Task 6: Add `analyze_stl` MCP Tool

**Files:**
- Modify: `mcp_server/server.py`
- Modify: `tests/test_stl_converter.py`

**Context:** This is the Tier A tool — always runs, extracts metadata, generates import wrapper, renders 4 multi-view PNGs, stores results in RAG. It calls `extract_metadata()`, `generate_import_wrapper()`, `render_multi_view()` (existing), `make_stl_chunks()`, and `rag_client.store_chunks()`.

Existing patterns in `server.py`:
- Tools use `_resolve_path()` for file resolution
- `mqtt_client.publish_event()` for MQTT events
- `rag_client.store_chunks()` for RAG storage
- Return dicts with `success`, relevant fields, and optional `error`

**Step 1: Write the failing test**

Append to `tests/test_stl_converter.py`:

```python
from unittest.mock import patch, MagicMock


def test_analyze_stl_tool_extracts_metadata():
    """analyze_stl extracts metadata and returns correct structure."""
    mesh = trimesh.creation.box(extents=[20, 15, 10])
    stl_path = _make_test_stl(mesh)

    try:
        # Mock render_multi_view to avoid needing OpenSCAD
        mock_views = {
            "success": True,
            "views": [
                {"view": "front", "file_path": "/tmp/front.png", "size_bytes": 100, "duration_ms": 50},
            ],
            "errors": None,
        }
        with patch("mcp_server.stl_converter.render_multi_view", return_value=mock_views):
            with patch("mcp_server.stl_converter.rag_client") as mock_rag:
                mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 2}
                mock_rag.is_rag_enabled.return_value = True

                from mcp_server.stl_converter import analyze_stl
                result = analyze_stl(stl_path)

        assert result["success"] is True
        assert "metadata" in result
        assert result["metadata"]["bbox"] == pytest.approx([20.0, 15.0, 10.0], abs=0.1)
        assert "views" in result
        assert "scad_path" in result
    finally:
        # Cleanup
        os.unlink(stl_path)
        import glob
        for f in glob.glob("/home/tie/OpenScad_AI/output/stl_imports/*.scad"):
            os.unlink(f)
```

**Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py::test_analyze_stl_tool_extracts_metadata -v
```

Expected: FAIL — `ImportError: cannot import name 'analyze_stl'`

**Step 3: Write implementation**

Add to `mcp_server/stl_converter.py` (add imports at top):

```python
from mcp_server.openscad import render_multi_view
from mcp_server import rag_client


def analyze_stl(stl_path: str) -> dict:
    """Tier A: Load STL, extract metadata, generate import wrapper, render views, store in RAG.

    Returns dict with success, metadata, views, scad_path.
    """
    # Extract metadata
    metadata = extract_metadata(stl_path)
    if "error" in metadata:
        return {"success": False, "error": metadata["error"]}

    # Generate import wrapper .scad
    scad_path = generate_import_wrapper(stl_path)
    if scad_path is None:
        return {"success": False, "error": "Failed to generate import wrapper", "metadata": metadata}

    # Render multi-view PNGs using existing pipeline
    views_result = {"success": False, "views": [], "errors": ["Rendering skipped"]}
    try:
        views_result = render_multi_view(scad_path)
    except Exception as e:
        log.warning("Multi-view render failed for STL %s: %s", stl_path, e)

    # Store in RAG
    stl_filename = Path(stl_path).name
    try:
        # Generate import wrapper code for RAG storage
        scad_code = Path(scad_path).read_text() if scad_path else None
        chunks = make_stl_chunks(stl_filename, metadata, scad_code=scad_code)
        rag_client.store_chunks(chunks, "design_history")
    except Exception as e:
        log.warning("RAG storage failed for STL %s: %s", stl_path, e)

    return {
        "success": True,
        "metadata": metadata,
        "views": views_result.get("views", []),
        "scad_path": scad_path,
    }
```

Now register it as an MCP tool in `server.py`. Add to `mcp_server/server.py` after the existing RAG tools (after `ingest_directory`), before the `prompt_image_to_code` resource:

```python
from mcp_server.stl_converter import (
    analyze_stl as _analyze_stl,
    fit_primitive,
    make_stl_chunks,
)


@mcp.tool()
def analyze_stl(file_path: str) -> dict:
    """Analyze an STL file: extract metadata, render multi-view PNGs, generate import wrapper, store in RAG.

    This is Tier A of STL-to-OpenSCAD conversion. Always runs first.
    Extracts bounding box, volume, face count, manifold status, and convex hull ratio.
    Renders 4 views (front/top/right/isometric) for visual analysis.

    Args:
        file_path: Path to .stl file (relative to project root or absolute)
    """
    resolved = _resolve_path(file_path)
    result = _analyze_stl(resolved)

    mqtt_client.publish_event("stl", "analyzed", {
        "file": resolved,
        "success": result["success"],
        "bbox": result.get("metadata", {}).get("bbox"),
    })

    return result
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 12 PASSED

**Step 5: Commit**

```bash
git add mcp_server/stl_converter.py mcp_server/server.py tests/test_stl_converter.py
git commit -m "feat: add analyze_stl MCP tool — Tier A STL analysis"
```

---

### Task 7: Add `convert_stl_to_scad` MCP Tool

**Files:**
- Modify: `mcp_server/server.py`
- Modify: `tests/test_stl_converter.py`

**Context:** Tier B tool — attempts primitive fitting on an STL. Calls `extract_metadata()` then `fit_primitive()`. Writes generated BOSL2 code to `output/stl_conversions/`. Updates RAG entry.

**Step 1: Write the failing test**

Append to `tests/test_stl_converter.py`:

```python
def test_convert_stl_produces_scad_file():
    """convert_stl_to_scad writes a .scad file with BOSL2 primitive."""
    mesh = trimesh.creation.box(extents=[30, 20, 10])
    stl_path = _make_test_stl(mesh)

    try:
        with patch("mcp_server.stl_converter.rag_client") as mock_rag:
            mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 2}

            from mcp_server.stl_converter import convert_stl
            result = convert_stl(stl_path)

        assert result["success"] is True
        assert result["primitive"] == "cuboid"
        assert result["scad_path"] is not None
        assert os.path.isfile(result["scad_path"])

        content = open(result["scad_path"]).read()
        assert "cuboid" in content
        assert "BOSL2" in content

        os.unlink(result["scad_path"])
    finally:
        os.unlink(stl_path)


def test_convert_stl_complex_shape_returns_null_primitive():
    """Complex shape → success but primitive is None."""
    mesh = trimesh.creation.box(extents=[10, 10, 10])
    stl_path = _make_test_stl(mesh)

    try:
        with patch("mcp_server.stl_converter.extract_metadata") as mock_meta:
            mock_meta.return_value = {
                "bbox": [10.0, 10.0, 10.0],
                "volume": 500.0,
                "surface_area": 600.0,
                "face_count": 100,
                "vertex_count": 50,
                "convex_hull_ratio": 0.5,  # Force complex
                "is_manifold": True,
                "original_path": stl_path,
            }
            with patch("mcp_server.stl_converter.rag_client"):
                from mcp_server.stl_converter import convert_stl
                result = convert_stl(stl_path)

        assert result["success"] is True
        assert result["primitive"] is None
        assert result["scad_path"] is None
    finally:
        os.unlink(stl_path)
```

**Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py::test_convert_stl_produces_scad_file -v
```

Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `mcp_server/stl_converter.py`:

```python
def convert_stl(stl_path: str) -> dict:
    """Tier B: Attempt primitive fitting on an STL file.

    Returns dict with success, primitive, scad_code, confidence, scad_path.
    """
    metadata = extract_metadata(stl_path)
    if "error" in metadata:
        return {"success": False, "error": metadata["error"]}

    fit_result = fit_primitive(metadata)

    scad_path = None
    if fit_result["scad_code"]:
        output_dir = PROJECT_DIR / "output" / "stl_conversions"
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(stl_path).stem
        scad_path = str(output_dir / f"{stem}_primitive.scad")
        Path(scad_path).write_text(fit_result["scad_code"])
        log.info("Primitive fit written: %s (%s)", scad_path, fit_result["primitive"])

    # Update RAG
    stl_filename = Path(stl_path).name
    try:
        chunks = make_stl_chunks(stl_filename, metadata, scad_code=fit_result["scad_code"])
        rag_client.store_chunks(chunks, "design_history")
    except Exception as e:
        log.warning("RAG storage failed for STL conversion %s: %s", stl_path, e)

    return {
        "success": True,
        "primitive": fit_result["primitive"],
        "scad_code": fit_result["scad_code"],
        "confidence": fit_result["confidence"],
        "scad_path": scad_path,
        "metadata": metadata,
    }
```

Add the MCP tool to `server.py` after `analyze_stl`:

```python
@mcp.tool()
def convert_stl_to_scad(file_path: str) -> dict:
    """Attempt to convert an STL file to approximate BOSL2 code via primitive fitting.

    This is Tier B of STL-to-OpenSCAD conversion. Analyzes the mesh geometry
    and fits the closest primitive shape (cuboid, cylinder, or sphere).
    Only works for simple convex shapes (convex hull ratio > 0.85).

    Args:
        file_path: Path to .stl file (relative to project root or absolute)
    """
    from mcp_server.stl_converter import convert_stl
    resolved = _resolve_path(file_path)
    result = convert_stl(resolved)

    mqtt_client.publish_event("stl", "converted", {
        "file": resolved,
        "success": result["success"],
        "primitive": result.get("primitive"),
        "confidence": result.get("confidence"),
    })

    return result
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 14 PASSED

**Step 5: Commit**

```bash
git add mcp_server/stl_converter.py mcp_server/server.py tests/test_stl_converter.py
git commit -m "feat: add convert_stl_to_scad MCP tool — Tier B primitive fitting"
```

---

### Task 8: Add `reverse_engineer_stl` MCP Tool

**Files:**
- Modify: `mcp_server/server.py`
- Modify: `tests/test_stl_converter.py`

**Context:** Tier C orchestration tool. Ensures multi-view PNGs exist (calls `analyze_stl` if needed), returns view paths + metadata so Claude can drive the Pathway 5 visual feedback loop. This tool does NOT generate BOSL2 code itself — Claude does that by examining the views and iterating.

**Step 1: Write the failing test**

Append to `tests/test_stl_converter.py`:

```python
def test_reverse_engineer_returns_views_and_metadata():
    """reverse_engineer_stl returns views + metadata for Claude."""
    mesh = trimesh.creation.box(extents=[25, 15, 10])
    stl_path = _make_test_stl(mesh)

    try:
        mock_views = {
            "success": True,
            "views": [
                {"view": "front", "file_path": "/tmp/front.png", "size_bytes": 100, "duration_ms": 50},
                {"view": "top", "file_path": "/tmp/top.png", "size_bytes": 100, "duration_ms": 50},
                {"view": "right", "file_path": "/tmp/right.png", "size_bytes": 100, "duration_ms": 50},
                {"view": "isometric", "file_path": "/tmp/iso.png", "size_bytes": 100, "duration_ms": 50},
            ],
            "errors": None,
        }
        with patch("mcp_server.stl_converter.render_multi_view", return_value=mock_views):
            with patch("mcp_server.stl_converter.rag_client") as mock_rag:
                mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 1}
                mock_rag.is_rag_enabled.return_value = True

                from mcp_server.stl_converter import reverse_engineer
                result = reverse_engineer(stl_path, description="test cube")

        assert result["success"] is True
        assert result["metadata"]["bbox"] == pytest.approx([25.0, 15.0, 10.0], abs=0.1)
        assert len(result["views"]) == 4
        assert result["description"] == "test cube"
    finally:
        os.unlink(stl_path)
        import glob
        for f in glob.glob("/home/tie/OpenScad_AI/output/stl_imports/*.scad"):
            os.unlink(f)
```

**Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py::test_reverse_engineer_returns_views_and_metadata -v
```

Expected: FAIL — `ImportError`

**Step 3: Write implementation**

Add to `mcp_server/stl_converter.py`:

```python
def reverse_engineer(stl_path: str, description: str = "") -> dict:
    """Tier C: Prepare STL for AI visual reverse engineering.

    Ensures multi-view PNGs exist and returns everything Claude needs
    to drive the Pathway 5 visual feedback loop.

    Returns dict with success, metadata, views, description.
    """
    # Run Tier A analysis to get metadata and views
    analysis = analyze_stl(stl_path)
    if not analysis["success"]:
        return analysis

    return {
        "success": True,
        "metadata": analysis["metadata"],
        "views": analysis["views"],
        "scad_path": analysis.get("scad_path"),
        "description": description,
        "instructions": (
            "Examine the 4 rendered views of this STL file. "
            "Generate parametric BOSL2 code that recreates this shape. "
            "Use render_design_views to compare your code against the original views. "
            "Iterate 2-4 times until proportions match."
        ),
    }
```

Add the MCP tool to `server.py` after `convert_stl_to_scad`:

```python
@mcp.tool()
def reverse_engineer_stl(file_path: str, description: str = "") -> dict:
    """Prepare an STL file for AI-driven visual reverse engineering.

    This is Tier C — renders multi-view PNGs and returns them with metadata
    so you can analyze the shape visually and generate parametric BOSL2 code.
    After receiving the views, write BOSL2 code, use render_design_views to
    compare, and iterate until proportions match.

    Args:
        file_path: Path to .stl file (relative to project root or absolute)
        description: Optional description of the object for context
    """
    from mcp_server.stl_converter import reverse_engineer
    resolved = _resolve_path(file_path)
    result = reverse_engineer(resolved, description=description)

    mqtt_client.publish_event("stl", "reverse_engineer_started", {
        "file": resolved,
        "success": result["success"],
        "description": description,
    })

    return result
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_stl_converter.py -v
```

Expected: 15 PASSED

**Step 5: Run full test suite to verify no regressions**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: All existing 29 tests + 15 new = 44 PASSED

**Step 6: Commit**

```bash
git add mcp_server/stl_converter.py mcp_server/server.py tests/test_stl_converter.py
git commit -m "feat: add reverse_engineer_stl MCP tool — Tier C visual analysis"
```

---

### Task 9: Update Documentation

**Files:**
- Modify: `docs/mcp-api-reference.md`
- Modify: `docs/HOW-TO-USE.md`
- Modify: `README.md`

**Context:** Add the 3 new tools to docs. Update tool counts from 14 to 17. Add STL conversion section.

**Step 1: Update `docs/mcp-api-reference.md`**

Add sections for `analyze_stl`, `convert_stl_to_scad`, `reverse_engineer_stl` before the Resources section. Update header from "14 tools" to "17 tools".

Each tool section should follow the existing format:
- Tool name as `###` heading
- Description paragraph
- Parameters table
- Returns JSON example
- MQTT event line

**Step 2: Update `docs/HOW-TO-USE.md`**

Add an "STL-to-OpenSCAD Conversion" subsection under "Working with the MCP Server". Cover the three tiers briefly with example prompts. Update tool count references.

**Step 3: Update `README.md`**

- Update architecture diagram to show 17 Tools
- Add 3 new tools to the tools table
- Add STL MQTT topics to the MQTT table
- Update all "14 tools" references to "17 tools"
- Add `trimesh` to the requirements table

**Step 4: Commit**

```bash
git add docs/mcp-api-reference.md docs/HOW-TO-USE.md README.md
git commit -m "docs: add STL-to-OpenSCAD tools to API reference and guides"
```

---

### Task 10: Final Verification and Push

**Step 1: Run full test suite**

```bash
cd /home/tie/OpenScad_AI
.venv/bin/python -m pytest tests/ -v
```

Expected: 44 tests PASSED (29 existing + 15 new)

**Step 2: Verify tool registration count**

```bash
.venv/bin/python -c "
from mcp_server.server import mcp
# FastMCP lists tools internally
print('Server name:', mcp.name)
"
```

**Step 3: Verify imports work**

```bash
.venv/bin/python -c "
from mcp_server.stl_converter import (
    extract_metadata,
    generate_import_wrapper,
    fit_primitive,
    make_stl_chunks,
    analyze_stl,
    convert_stl,
    reverse_engineer,
)
print('All STL converter functions importable')
"
```

**Step 4: Check no files left unstaged**

```bash
git status
```

Expected: Clean working tree

**Step 5: Push to remote**

```bash
git push
```

---

## Summary

| Task | What It Builds | Tests Added |
|------|---------------|-------------|
| 1 | trimesh dependency | 0 |
| 2 | `extract_metadata()` — load STL, get bbox/volume/faces/hull ratio | 3 |
| 3 | `generate_import_wrapper()` — create .scad with `import()` | 2 |
| 4 | `fit_primitive()` — cuboid/cylinder/sphere fitting from metadata | 4 |
| 5 | `make_stl_chunks()` — RAG chunk creation for STL results | 2 |
| 6 | `analyze_stl` MCP tool (Tier A) | 1 |
| 7 | `convert_stl_to_scad` MCP tool (Tier B) | 2 |
| 8 | `reverse_engineer_stl` MCP tool (Tier C) | 1 |
| 9 | Documentation updates | 0 |
| 10 | Final verification + push | 0 |

**Total: 10 tasks, 15 new tests, 3 new MCP tools, 1 new module**
