# MCP Server API Reference

**OpenScad_AI MCP Server** — 17 tools and 7 resources for AI-assisted 3D design.

Server name: `OpenScad_AI`
Protocol: MCP (JSON-RPC over stdio)
Entry point: `python -m mcp_server`

---

## Tools

Tools are model-controlled — Claude invokes them automatically based on conversation context.

---

### validate_design

Validate an OpenSCAD design file. Runs three checks in sequence: syntax validation, STL export test, and manifold geometry check.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | yes | Path to `.scad` file (relative to project root or absolute) |

**Returns:**

```json
{
  "syntax_ok": true,
  "export_ok": true,
  "manifold_ok": true,
  "overall": true,
  "errors": [],
  "warnings": []
}
```

**MQTT event:** `openscad/validate/result`

---

### render_stl_file

Render a high-quality STL file from an OpenSCAD design. Output is written to `output/stl/`.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | yes | Path to `.scad` file |

**Returns:**

```json
{
  "success": true,
  "file_path": "output/stl/my-part.stl",
  "size_bytes": 48256,
  "duration_ms": 3420,
  "errors": null,
  "warnings": null
}
```

**MQTT events:** `openscad/render/started`, `openscad/render/stl`

---

### render_png_preview

Render a single PNG preview image of an OpenSCAD design. Output goes to `output/png/`.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file_path` | string | yes | — | Path to `.scad` file |
| `imgsize` | string | no | `"1024,768"` | Image dimensions as `"width,height"` |
| `colorscheme` | string | no | `"Tomorrow"` | OpenSCAD color scheme name |
| `camera` | string | no | `null` | Camera parameters: `"translateX,Y,Z,rotX,Y,Z,distance"` |

**Returns:**

```json
{
  "success": true,
  "file_path": "output/png/my-part.png",
  "size_bytes": 15234,
  "duration_ms": 2100,
  "warnings": null
}
```

**MQTT event:** `openscad/render/png`

---

### render_design_views

Render four orthographic + isometric PNG views of a design for visual self-critique. This is the core tool for the visual feedback loop — examining all four views reveals proportion, alignment, and feature placement issues that a single view would miss.

**Camera angles:**

| View | Rotation (pitch, roll, yaw) | Purpose |
|------|----------------------------|---------|
| `front` | 90, 0, 0 | Verify height and width proportions |
| `top` | 0, 0, 0 | Verify layout, hole placement, symmetry |
| `right` | 90, 0, 90 | Verify depth and feature positions |
| `isometric` | 55, 0, 25 | Overall 3D impression |

All views use `--viewall --autocenter` to auto-fit the object in frame.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file_path` | string | yes | — | Path to `.scad` file |
| `imgsize` | string | no | `"800,600"` | Image dimensions |
| `colorscheme` | string | no | `"Tomorrow"` | Color scheme |

**Returns:**

```json
{
  "success": true,
  "views": [
    {
      "view": "front",
      "file_path": "/path/to/my-part_front.png",
      "size_bytes": 12345,
      "duration_ms": 1800
    },
    { "view": "top", "..." : "..." },
    { "view": "right", "..." : "..." },
    { "view": "isometric", "..." : "..." }
  ],
  "errors": null
}
```

**MQTT event:** `openscad/render/multi_view`

---

### list_designs

List all `.scad` design files in the project, recursively.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `directory` | string | no | `"designs"` | Subdirectory to search (relative to project root) |

**Returns:**

```json
{
  "count": 3,
  "designs": [
    {
      "name": "sample-bracket",
      "path": "designs/examples/sample-bracket.scad",
      "size_bytes": 1234,
      "modified": 1741392000.0
    }
  ]
}
```

---

### create_from_template

Create a new design file by copying a template.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `template` | string | yes | — | Template name: `"basic"`, `"mechanical-part"` (or `"mechanical"`), `"parametric"` |
| `name` | string | yes | — | Design name without `.scad` extension |
| `directory` | string | no | `"designs/mechanical"` | Target directory (relative to project root) |

**Returns:**

```json
{
  "success": true,
  "file_path": "designs/mechanical/motor-mount.scad",
  "template_used": "mechanical-part"
}
```

**Error conditions:** Unknown template name, file already exists, template file missing.

**MQTT event:** `openscad/design/created`

---

### get_design_status

Check the current status of a design file — file info, existing render outputs, and whether outputs are stale (source modified after last render).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | yes | Path to `.scad` file |

**Returns:**

```json
{
  "file": "designs/mechanical/my-part.scad",
  "size_bytes": 2048,
  "modified": 1741392000.0,
  "stl": {
    "path": "output/stl/my-part.stl",
    "size_bytes": 48256,
    "stale": false
  },
  "png": {
    "path": "output/png/my-part.png",
    "size_bytes": 15234,
    "stale": true
  }
}
```

`stl` and `png` are `null` if no output exists. `stale: true` means the source `.scad` was modified after the output was generated.

---

### check_environment

Verify that OpenSCAD, BOSL2, and all dependencies are properly installed and accessible.

**Parameters:** None

**Returns:**

```json
{
  "openscad_ok": true,
  "openscad_version": "OpenSCAD version 2025.05.02",
  "bosl2_ok": true,
  "bosl2_path": "/home/user/.local/share/OpenSCAD/libraries/BOSL2",
  "display": "none (headless)",
  "xvfb": true,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883
}
```

---

### save_design_iteration

Save a numbered snapshot of the current design for iteration tracking. Creates files like `bracket_v001.scad`, `bracket_v002.scad` in `output/iterations/`. Use this before making significant changes to preserve rollback points.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | yes | Path to `.scad` file to snapshot |

**Returns:**

```json
{
  "version": 3,
  "file_path": "/path/to/output/iterations/bracket_v003.scad"
}
```

Version numbers auto-increment by scanning existing files. The highest existing version + 1 is used.

**MQTT event:** `openscad/design/iteration_saved`

---

### list_design_iterations

List all saved iteration snapshots of a design, ordered by version number.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `design_name` | string | yes | Design stem name without extension (e.g., `"bracket"`) |

**Returns:**

```json
{
  "design": "bracket",
  "count": 3,
  "iterations": [
    {
      "version": 1,
      "file_path": "/path/to/output/iterations/bracket_v001.scad",
      "size_bytes": 1024,
      "modified": 1741392000.0
    },
    { "version": 2, "..." : "..." },
    { "version": 3, "..." : "..." }
  ]
}
```

---

### get_latest_design_iteration

Get the most recent saved iteration of a design.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `design_name` | string | yes | Design stem name without extension |

**Returns:** Same structure as a single entry from `list_design_iterations`, or `{"error": "No iterations found for 'name'"}` if none exist.

---

### search_knowledge_base

Semantic search across all or specific RAG collections. Uses ChromaDB vector store to find relevant OpenSCAD code, project documentation, schemas, or design history.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | yes | — | Search query |
| `collection` | string\|null | no | `null` | Specific collection to search, or `null` for all |
| `n_results` | integer | no | `5` | Number of results to return |

**Collections:** `openscad_code`, `project_docs`, `schemas_config`, `design_history`

**Returns:**

```json
{
  "results": [
    {
      "content": "...",
      "metadata": { "source": "...", "collection": "..." },
      "distance": 0.23
    }
  ],
  "count": 3,
  "collection": "openscad_code"
}
```

**MQTT event:** `openscad/rag/search`

---

### ingest_document

On-demand ingestion of a single file into the RAG knowledge base. The file is chunked and embedded into ChromaDB for later semantic search.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file_path` | string | yes | — | Path to file to ingest |
| `collection` | string\|null | no | `null` | Target collection (auto-detected from file type if not specified) |

**Returns:**

```json
{
  "success": true,
  "chunks": 12,
  "collection": "openscad_code"
}
```

**MQTT event:** `openscad/rag/ingested`

---

### ingest_directory

Bulk ingest a directory of files into the RAG knowledge base with glob pattern filtering.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `directory` | string | yes | — | Directory path to ingest |
| `pattern` | string | no | `"**/*"` | Glob pattern for file filtering |
| `collection` | string\|null | no | `null` | Target collection (auto-detected per file if not specified) |

**Returns:**

```json
{
  "success": true,
  "files": 8,
  "chunks": 94
}
```

**MQTT event:** `openscad/rag/bulk_ingested`

---

### analyze_stl

Analyze an STL file: extract metadata (bounding box, volume, face count, manifold status, convex hull ratio), render multi-view PNGs, generate import wrapper, store results in RAG.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | yes | Path to `.stl` file |

**Returns:**

```json
{
  "success": true,
  "metadata": { "..." : "..." },
  "views": ["..."],
  "scad_path": "output/stl/my-part_import.scad"
}
```

**MQTT event:** `openscad/stl/analyzed`

---

### convert_stl_to_scad

Attempt primitive fitting on an STL — fits cuboid, cylinder, or sphere based on bounding box and convex hull ratio. Only works for simple convex shapes (ratio > 0.85).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | yes | Path to `.stl` file |

**Returns:**

```json
{
  "success": true,
  "primitive": "cuboid",
  "scad_code": "cuboid([10,20,30]);",
  "confidence": 0.92,
  "scad_path": "output/stl/my-part_primitive.scad",
  "metadata": { "..." : "..." }
}
```

**MQTT event:** `openscad/stl/converted`

---

### reverse_engineer_stl

Prepare STL for AI-driven visual reverse engineering. Renders multi-view PNGs and returns metadata so Claude can generate parametric BOSL2 code using the visual feedback loop.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file_path` | string | yes | — | Path to `.stl` file |
| `description` | string | no | `null` | Description of the object |

**Returns:**

```json
{
  "success": true,
  "metadata": { "..." : "..." },
  "views": ["..."],
  "description": "A motor mount bracket",
  "instructions": "..."
}
```

**MQTT event:** `openscad/stl/reverse_engineer_started`

---

## Resources

Resources are user/app-controlled — they are loaded into Claude's context on demand to provide reference material for better code generation.

---

### bosl2://quickref

**BOSL2 quick reference card.** Loaded from `docs/bosl2-quickref.md`. Covers basic shapes, positioning, boolean operations, array patterns, rounding, mechanical parts, and print-friendly tips.

---

### bosl2://attachments

**BOSL2 attachment system.** Inline reference covering:
- Anchor names: `TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `FRONT`, `BACK`, and combinations
- `attach(FROM)` and `attach(FROM, TO)` syntax
- `position()` for placement without reorientation
- `diff()` + `tag("remove")` / `tag("keep")` for boolean operations
- `overlap=0.01` to prevent Z-fighting
- Common patterns: mounting holes, stacked shapes

---

### bosl2://threading

**Threading and screws.** Inline reference covering:
- Screw clearance hole diameters (M2 through M5)
- Countersunk hole dimensions and depths
- Heat-set insert hole sizing
- Standoff construction patterns
- Requires `include <BOSL2/screws.scad>`

---

### bosl2://rounding

**Rounding and chamfering.** Inline reference covering:
- `cuboid()` rounding: all edges, specific edges (`edges=TOP`), specific edge pairs
- `cyl()` rounding: `rounding1` (bottom), `rounding2` (top)
- Chamfer syntax as alternative to rounding
- Print-friendly rules: chamfer bottoms for bed adhesion, round tops freely, `$fn` impact on smoothness

---

### bosl2://patterns

**Array patterns and distribution.** Inline reference covering:
- `grid_copies(spacing, n)` — rectangular grid
- `linear_copies(spacing, n, dir)` — along a line or vector
- `rot_copies(n, r, sa, ea)` — circular/arc distribution
- `path_copies(path)` — along an arbitrary path
- Combining patterns with `diff()` for hole arrays

---

### bosl2://examples/mounting-plate

**Parametric mounting plate example.** Complete working OpenSCAD code demonstrating:
- Parameterized dimensions, hole spacing, rounding
- `diff()` + `attach()` + `grid_copies()` pattern
- Print-friendly edge treatments (`edges="Z"` for vertical only, chamfer for bed adhesion)
- `anchor=BOTTOM` on holes for correct start position
- `h = plate_height + 2` for full penetration

---

### bosl2://prompts/image-to-code

**Image/sketch to OpenSCAD prompt template.** Structured workflow for generating BOSL2 code from a photo, sketch, or verbal description of a physical object:

1. **Analyze** — identify primary shape, features, symmetry, construction sequence
2. **Gather dimensions** — ask user to measure or make documented estimates
3. **Generate code** — parameterized BOSL2 with user-adjustable values
4. **Self-critique via multi-view render** — use `render_design_views`, check proportions across all 4 views, iterate 2-4 times

Includes starter patterns for common objects: enclosures, L-brackets, mounting plates.

---

## OpenSCAD Wrapper Details

The `mcp_server/openscad.py` module handles all OpenSCAD CLI interaction.

### Binary Detection Priority

1. `bin/OpenSCAD-latest.AppImage` (project-local AppImage)
2. `openscad` on `$PATH` (system install)
3. `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD` (macOS)

### Headless Rendering

If `$DISPLAY` is unset and `xvfb-run` is available, all OpenSCAD commands are wrapped with `xvfb-run -a` for virtual framebuffer rendering.

### Multi-View Camera Parameters

Camera string format: `translateX,translateY,translateZ,rotationX,rotationY,rotationZ,distance`

With `--viewall --autocenter`, the distance field is ignored (set to 0) and OpenSCAD auto-fits the object.

| View | Camera String | Rotation Meaning |
|------|--------------|-----------------|
| front | `0,0,0,90,0,0,0` | Pitch 90° (look from front) |
| top | `0,0,0,0,0,0,0` | No rotation (look from above) |
| right | `0,0,0,90,0,90,0` | Pitch 90° + Yaw 90° (look from right) |
| isometric | `0,0,0,55,0,25,0` | Pitch 55° + Yaw 25° (3D perspective) |

---

## MQTT Client Details

The `mcp_server/mqtt_client.py` module provides persistent MQTT with graceful degradation.

- **Connection:** Lazy, thread-safe, created on first publish
- **Protocol:** MQTT v3.1.1 with QoS 1 (at-least-once delivery)
- **Client ID:** `openscad-mcp`
- **Payload:** JSON with auto-appended `timestamp` (ISO 8601 UTC)
- **Failure mode:** Logs warning on broker unavailability, returns `False`, server continues normally
- **Publish timeout:** 5 seconds per message

---

## Versioning Module Details

The `mcp_server/versioning.py` module manages design iteration snapshots.

- **Storage:** `output/iterations/` directory
- **Naming:** `{stem}_v{NNN}.scad` where NNN is zero-padded to 3 digits (001-999)
- **Version detection:** Scans existing files matching `{stem}_v\d{3}\.scad` regex, takes max + 1
- **Copy method:** `shutil.copy2` (preserves metadata)
- **Thread safety:** File-system based, no locks needed for single-writer

---

## RAG Configuration

The RAG (Retrieval-Augmented Generation) subsystem uses ChromaDB for vector storage and semantic search.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHROMADB_HOST` | `10.0.1.81` | ChromaDB server hostname |
| `CHROMADB_PORT` | `8000` | ChromaDB server port |
| `RAG_ENABLED` | `true` | Enable/disable RAG features |
| `RAG_AUTO_INJECT` | `true` | Enable automatic context injection on tool calls |
| `RAG_N_RESULTS` | `5` | Default number of results for semantic search |

### Collections

| Collection | Content |
|------------|---------|
| `openscad_code` | OpenSCAD source files and BOSL2 patterns |
| `project_docs` | Project documentation and guides |
| `schemas_config` | JSON schemas and configuration files |
| `design_history` | Rendered design snapshots and iteration metadata |

### Auto-Injection

When `RAG_AUTO_INJECT` is enabled, relevant knowledge is silently injected into context during these tool calls:

- **`create_from_template`** — injects from `openscad_code` (relevant patterns for the template type)
- **`render_design_views`** — injects from `design_history` (prior design context)
- **`validate_design`** — injects from `schemas_config` (relevant validation rules)
