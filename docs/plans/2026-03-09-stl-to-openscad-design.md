# STL-to-OpenSCAD Conversion with RAG Storage — Design

**Date:** 2026-03-09
**Status:** Approved
**Approach:** Three-tier conversion (import wrapper → primitive fitting → AI visual reverse engineering)

---

## Goal

Add a tiered STL-to-OpenSCAD conversion system that extracts metadata, generates approximate code, and stores everything in RAG for future reference. Works with both external STLs (reverse engineering) and our own renders (knowledge base building).

## Architecture — Three Tiers

```
STL Input (external or rendered)
    │
    ▼
┌─────────────────────────────────────────────┐
│ Tier A: Import Wrapper (always runs)        │
│ - trimesh loads STL → extract metadata      │
│   (bbox, volume, face count, symmetry)      │
│ - Generate import("file.stl") wrapper .scad │
│ - Render 4 multi-view PNGs via OpenSCAD     │
│ - Store metadata + code + view descriptions │
│   in RAG (design_history collection)        │
└──────────────────┬──────────────────────────┘
                   │ (user requests parametric)
                   ▼
┌─────────────────────────────────────────────┐
│ Tier B: Primitive Fitting (on demand)       │
│ - Analyze bounding box, convex hull ratio   │
│ - Fit closest primitive: cuboid/cyl/sphere  │
│ - Generate approximate BOSL2 code           │
│ - Falls back to Tier A if shape too complex │
│ - Update RAG entry with parametric code     │
└──────────────────┬──────────────────────────┘
                   │ (user requests AI conversion)
                   ▼
┌─────────────────────────────────────────────┐
│ Tier C: AI Visual Reverse Engineering       │
│ - Use multi-view PNGs from Tier A           │
│ - Claude analyzes views via Pathway 5       │
│ - Generates parametric BOSL2 code           │
│ - Iterates with render → critique loop      │
│ - Update RAG entry with final code          │
└─────────────────────────────────────────────┘
```

Rendering fallback: If OpenSCAD can't render the STL views (non-manifold), fall back to trimesh's built-in renderer.

---

## New Module

```
mcp_server/
└── stl_converter.py    # STL loading via trimesh
                        # Metadata extraction (bbox, volume, faces, symmetry)
                        # Primitive fitting (cuboid/cylinder/sphere)
                        # Import wrapper generation
                        # Multi-view rendering orchestration
                        # RAG storage of conversion results
```

---

## New MCP Tools (3)

### analyze_stl

Load an STL file, extract metadata, render multi-view PNGs, generate an `import()` wrapper, and store everything in RAG.

```python
@mcp.tool()
def analyze_stl(
    file_path: str,
) -> dict:
```

- Backend: trimesh for mesh analysis, OpenSCAD for multi-view rendering (fallback: trimesh renderer)
- Generates a temporary `.scad` file with `import("file.stl");` and renders 4 views via existing `render_views()`
- Stores 2 chunks in RAG `design_history`: metadata + import wrapper code
- Returns: `{"success": bool, "metadata": {...}, "views": [...], "scad_path": str}`
- MQTT event: `openscad/stl/analyzed`

### convert_stl_to_scad

Attempt primitive fitting on a previously analyzed STL and generate approximate BOSL2 code.

```python
@mcp.tool()
def convert_stl_to_scad(
    file_path: str,
) -> dict:
```

- Requires `analyze_stl` to have been run first (uses cached metadata)
- Fits closest primitive (cuboid, cylinder, sphere) based on bounding box and convex hull ratio
- Falls back gracefully if shape is too complex (convex_hull_ratio ≤ 0.85)
- Updates RAG entry with parametric code
- Returns: `{"success": bool, "primitive": str, "scad_code": str, "confidence": float, "scad_path": str}`
- MQTT event: `openscad/stl/converted`

### reverse_engineer_stl

Orchestration tool that prepares an STL for AI visual reverse engineering using the Pathway 5 feedback loop.

```python
@mcp.tool()
def reverse_engineer_stl(
    file_path: str,
    description: str = "",
) -> dict:
```

- Ensures multi-view PNGs exist (calls `analyze_stl` if needed)
- Returns view paths and metadata so Claude can drive the visual feedback loop
- Claude generates BOSL2 code, renders, critiques, iterates (2-4 rounds)
- Final code stored in RAG by Claude calling `ingest_document`
- Returns: `{"success": bool, "metadata": {...}, "views": [...], "description": str}`
- MQTT event: `openscad/stl/reverse_engineer_started`

---

## Metadata Extracted (Tier A)

| Field | Type | Description |
|-------|------|-------------|
| `bbox` | `[x, y, z]` | Bounding box dimensions in mm |
| `volume` | `float` | Volume in mm³ |
| `surface_area` | `float` | Surface area in mm² |
| `face_count` | `int` | Number of triangular faces |
| `vertex_count` | `int` | Number of vertices |
| `convex_hull_ratio` | `float` | Volume / convex hull volume (1.0 = fully convex) |
| `is_manifold` | `bool` | Whether mesh is watertight |
| `symmetry` | `list[str]` | Detected symmetry axes (X, Y, Z) |
| `source` | `str` | `"external"` or `"rendered"` |
| `original_path` | `str` | Original file path |

---

## Primitive Fitting Logic (Tier B)

```
convex_hull_ratio > 0.85 → attempt fitting
  bbox aspect ≈ 1:1:1 (within 20%) → sphere
  bbox aspect ≈ 1:1:N (two axes within 20%, third > 1.5x) → cylinder
  otherwise → cuboid
convex_hull_ratio ≤ 0.85 → too complex, stay at Tier A
```

Generated BOSL2 uses measured dimensions. Example output:

```scad
// Approximate primitive fit from STL analysis
// Source: motor-housing.stl
// Confidence: 0.82 (cylinder)
// Bounding box: 42.0 x 42.0 x 65.3 mm

include <BOSL2/std.scad>

cyl(d=42.0, h=65.3, $fn=64);
```

---

## RAG Storage (design_history collection)

Each conversion stores 2-3 chunks:

| Chunk | Content | Stored When |
|-------|---------|-------------|
| Metadata | JSON-formatted dimensions, volume, face count, convex ratio, source | Tier A (always) |
| Code | Generated OpenSCAD code (import wrapper, primitive fit, or AI-generated) | Tier A/B/C |
| View descriptions | Text descriptions of what each multi-view PNG shows | Tier C only |

Document ID format: `openscad_ai:stl_conversions/{stl_filename}:{chunk_index}`

Re-analyzing the same STL performs an upsert, keeping the index current.

---

## Multi-View Rendering from STL

Primary approach (OpenSCAD):
1. Write temporary `.scad` file: `import("/absolute/path/to/file.stl");`
2. Call existing `render_views()` with the temporary file
3. Returns 4 PNGs: front, top, right, isometric

Fallback (trimesh, if OpenSCAD fails):
1. Load mesh with `trimesh.load()`
2. Render scenes from 4 camera angles matching OpenSCAD's view parameters
3. Save PNGs to `output/png/`

---

## Configuration

Reuses existing RAG environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_ENABLED` | `true` | Kill switch — if false, analysis still works but RAG storage is skipped |
| `CHROMADB_HOST` | `10.0.1.81` | ChromaDB server for RAG storage |
| `CHROMADB_PORT` | `8000` | ChromaDB HTTP port |

No new environment variables needed.

---

## Dependencies

Add to `requirements.txt`:
- `trimesh` — STL loading, mesh analysis, convex hull, primitive fitting (~5MB, pure Python core with numpy)

trimesh's optional dependencies (pyglet, pyrender) are NOT required — we use OpenSCAD for rendering and only need trimesh for mesh analysis.

---

## Graceful Degradation

| Failure | Behavior |
|---------|----------|
| trimesh unavailable | Tools return error with install instructions, existing tools unaffected |
| STL non-manifold | Warn but still extract metadata and attempt rendering |
| OpenSCAD render fails | Fall back to trimesh renderer for views |
| Primitive fitting fails | Return Tier A results with `"primitive": null` |
| RAG unavailable | Conversion works, storage silently skipped |
| Complex geometry | convex_hull_ratio reported, user informed primitive fitting not suitable |

---

## Testing Strategy

### Unit Tests (no cluster required)

| Test File | Coverage |
|-----------|----------|
| `tests/test_stl_converter.py` | Metadata extraction, primitive fitting logic, import wrapper generation, BOSL2 code generation, RAG chunk creation |

Mock trimesh, ChromaDB, and MQTT connections. Use a small test STL (cube or cylinder, ~1KB).

### Integration Tests (require OpenSCAD + cluster)

| Test | Validates |
|------|-----------|
| Analyze cube STL | Metadata correct, 4 views rendered, RAG stored |
| Convert cube STL | Primitive detected as cuboid, BOSL2 code generated |
| Convert cylinder STL | Primitive detected as cylinder |
| Complex STL fallback | convex_hull_ratio < 0.85, primitive fitting skipped gracefully |
| Non-manifold STL | Warning logged, metadata still extracted |
| RAG round-trip | Analyze → search_knowledge_base finds it |

### Verification Checklist

- [ ] `analyze_stl` extracts correct metadata from a known STL
- [ ] Multi-view PNGs rendered from STL via OpenSCAD import
- [ ] `convert_stl_to_scad` detects cuboid from cube STL
- [ ] `convert_stl_to_scad` detects cylinder from cylinder STL
- [ ] Complex STL returns `"primitive": null` gracefully
- [ ] RAG storage works — metadata and code searchable via `search_knowledge_base`
- [ ] `reverse_engineer_stl` returns views for Claude to analyze
- [ ] trimesh unavailable → clear error, existing tools unaffected
- [ ] All existing 29 tests still pass
- [ ] All existing 14 tools still registered (17 total with 3 new)
- [ ] MQTT events published for all 3 new tools

---

## Input Sources

| Source | Use Case | Flow |
|--------|----------|------|
| External STL (Thingiverse, etc.) | Reverse engineer for modification | User provides path → analyze → convert/reverse_engineer |
| Our rendered STL | Build knowledge base | After `render_stl_file` → auto-analyze and store in RAG |
| Design iteration STL | Track geometry evolution | After `save_design_iteration` → optionally analyze |

---

## Existing Infrastructure Referenced

- `mcp_server/openscad.py` — `render_views()` for multi-view rendering, `render_stl()` for STL export
- `mcp_server/rag_client.py` — `store_chunks()` for RAG storage, `search()` for retrieval
- `mcp_server/chunking.py` — `make_doc_id()` for dedup IDs
- `mcp_server/server.py` — Tool registration, MQTT publishing
- `docs/image_to_code.md` — Pathway 5 (visual feedback loop) drives Tier C
