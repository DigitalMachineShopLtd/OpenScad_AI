# STL-to-OpenSCAD Conversion — Testing Plan

**Date:** 2026-03-09
**Feature:** Three-tier STL-to-OpenSCAD conversion with RAG storage
**Design:** `docs/plans/2026-03-09-stl-to-openscad-design.md`

---

## Test Inventory

### What's Already Tested (15 unit tests, all mocked)

| Test | Function | What It Verifies |
|------|----------|-----------------|
| `test_extract_metadata_cube` | `extract_metadata` | bbox, volume, face count, vertex count, manifold, hull ratio |
| `test_extract_metadata_cylinder` | `extract_metadata` | bbox dimensions for cylinder |
| `test_extract_metadata_file_not_found` | `extract_metadata` | Error dict on missing file |
| `test_generate_import_wrapper` | `generate_import_wrapper` | .scad file created with `import()` |
| `test_generate_import_wrapper_missing_stl` | `generate_import_wrapper` | Returns None on missing file |
| `test_fit_primitive_cuboid` | `fit_primitive` | Box → cuboid, correct code |
| `test_fit_primitive_cylinder` | `fit_primitive` | Cylinder → cylinder, correct code |
| `test_fit_primitive_sphere` | `fit_primitive` | Sphere → sphere, correct code |
| `test_fit_primitive_complex_shape_fails` | `fit_primitive` | Low hull ratio → None |
| `test_make_stl_chunks_with_code` | `make_stl_chunks` | 2 chunks, correct IDs and types |
| `test_make_stl_chunks_metadata_only` | `make_stl_chunks` | 1 chunk when no code |
| `test_analyze_stl_extracts_metadata` | `analyze_stl` | Success, metadata, views, scad_path (render mocked) |
| `test_convert_stl_produces_scad_file` | `convert_stl` | Writes .scad, detects cuboid (RAG mocked) |
| `test_convert_stl_complex_shape_returns_null_primitive` | `convert_stl` | Complex → null primitive |
| `test_reverse_engineer_returns_views_and_metadata` | `reverse_engineer` | Views + metadata returned (render mocked) |

### What's NOT Tested Yet

| Gap | Category | Risk |
|-----|----------|------|
| OpenSCAD actually renders an STL import wrapper | Integration | High — core Tier A functionality |
| RAG round-trip (store → search finds it) | Integration | Medium — RAG storage is fire-and-forget via MQTT |
| MQTT events published by MCP tools | Integration | Low — follows proven pattern from other tools |
| Non-manifold STL handling | Edge case | Medium — metadata should still extract |
| Symmetry detection accuracy | Unit | Low — basic bbox comparison |
| Source field propagation | Unit | Low — always "external" |
| Boundary: hull ratio exactly 0.85 | Unit | Low — recently fixed |
| Generated BOSL2 code compiles in OpenSCAD | Integration | High — never validated by OpenSCAD |
| Primitive fit dimension accuracy | Unit | Medium — dimensions flow into code but not asserted |
| Large STL performance | Performance | Low — trimesh handles large meshes well |
| Concurrent analyze_stl calls | Concurrency | Low — file-based, no shared state |
| Empty STL file | Edge case | Low — trimesh should error gracefully |
| Binary vs ASCII STL | Compatibility | Low — trimesh handles both |

---

## Phase 1: Unit Test Gaps (no infrastructure required)

Run with: `.venv/bin/python -m pytest tests/test_stl_converter.py -v`

### 1.1 Metadata Field Coverage

```python
def test_extract_metadata_symmetry_cylinder():
    """Cylinder has Z symmetry (X and Y bbox equal)."""
    mesh = trimesh.creation.cylinder(radius=10, height=40)
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        assert "symmetry" in meta
        assert "Z" in meta["symmetry"]
    finally:
        os.unlink(path)


def test_extract_metadata_source_field():
    """Source field defaults to 'external'."""
    mesh = trimesh.creation.box(extents=[10, 10, 10])
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        assert meta["source"] == "external"
    finally:
        os.unlink(path)
```

### 1.2 Boundary Condition

```python
def test_fit_primitive_boundary_at_085():
    """Hull ratio of exactly 0.85 → no primitive (boundary guard)."""
    meta = {
        "bbox": [10.0, 10.0, 10.0],
        "volume": 1000.0,
        "convex_hull_ratio": 0.85,
        "original_path": "/tmp/test.stl",
    }
    result = fit_primitive(meta)
    assert result["primitive"] is None
```

### 1.3 Dimension Accuracy in Generated Code

```python
def test_fit_primitive_cuboid_dimensions_in_code():
    """Cuboid code contains the actual bbox dimensions."""
    mesh = trimesh.creation.box(extents=[30, 20, 10])
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        result = fit_primitive(meta)
        assert "30.0" in result["scad_code"]
        assert "20.0" in result["scad_code"]
        assert "10.0" in result["scad_code"]
    finally:
        os.unlink(path)


def test_fit_primitive_cylinder_dimensions_in_code():
    """Cylinder code contains correct diameter and height."""
    mesh = trimesh.creation.cylinder(radius=10, height=40)
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        result = fit_primitive(meta)
        # Height should be ~40, diameter ~20
        assert "40.0" in result["scad_code"]
        assert "20.0" in result["scad_code"]
    finally:
        os.unlink(path)
```

### 1.4 Edge Cases

```python
def test_extract_metadata_empty_stl():
    """Empty/corrupt file → error dict."""
    f = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
    f.write(b"")
    f.close()
    try:
        meta = extract_metadata(f.name)
        assert "error" in meta
    finally:
        os.unlink(f.name)


def test_make_stl_chunks_with_view_descriptions():
    """View descriptions → 3 chunks."""
    metadata = {"bbox": [10, 10, 10], "volume": 1000}
    chunks = make_stl_chunks(
        "test.stl", metadata,
        scad_code="cube();",
        view_descriptions="A 10mm cube viewed from 4 angles"
    )
    assert len(chunks) == 3
    assert chunks[2]["metadata"]["file_type"] == "stl_views"


def test_analyze_stl_file_not_found():
    """analyze_stl on missing file → success=False with error."""
    result = analyze_stl("/nonexistent/path.stl")
    assert result["success"] is False
    assert "error" in result
```

---

## Phase 2: Integration Tests (require OpenSCAD)

These tests need the OpenSCAD AppImage installed at `bin/OpenSCAD-latest.AppImage` and `xvfb-run` for headless rendering. Mark with `@pytest.mark.integration`.

Run with: `.venv/bin/python -m pytest tests/test_stl_integration.py -v -m integration`

### 2.1 OpenSCAD Renders STL Import

**Purpose:** Verify OpenSCAD can actually render an `import()` wrapper and produce 4 PNGs.

```python
@pytest.mark.integration
def test_openscad_renders_stl_import():
    """OpenSCAD renders 4 multi-view PNGs from an STL import wrapper."""
    mesh = trimesh.creation.box(extents=[20, 15, 10])
    stl_path = _make_test_stl(mesh)

    try:
        scad_path = generate_import_wrapper(stl_path)
        views = render_multi_view(scad_path)

        assert views["success"] is True
        assert len(views["views"]) == 4

        for view in views["views"]:
            assert os.path.isfile(view["file_path"])
            assert view["size_bytes"] > 0
    finally:
        os.unlink(stl_path)
        # Cleanup generated files
```

**Expected:** 4 PNGs created in `output/png/`, each non-empty.
**Failure indicates:** OpenSCAD can't handle `import()` in headless mode, or STL path resolution issue.

### 2.2 Generated BOSL2 Code Compiles

**Purpose:** Verify that primitive fit output is valid OpenSCAD code.

```python
@pytest.mark.integration
def test_generated_cuboid_code_compiles():
    """BOSL2 cuboid code from fit_primitive compiles in OpenSCAD."""
    mesh = trimesh.creation.box(extents=[30, 20, 10])
    stl_path = _make_test_stl(mesh)

    try:
        result = convert_stl(stl_path)
        assert result["scad_path"] is not None

        # Validate the generated code compiles
        validation = validate(result["scad_path"])
        assert validation.syntax_ok is True
    finally:
        os.unlink(stl_path)
```

**Expected:** Syntax check passes. STL export may fail if BOSL2 not found — that's a setup issue, not a code issue.
**Failure indicates:** Generated BOSL2 code has syntax errors.

### 2.3 Full Tier A Pipeline (analyze_stl end-to-end)

**Purpose:** No mocks — call `analyze_stl` with real OpenSCAD and verify the full pipeline.

```python
@pytest.mark.integration
def test_analyze_stl_end_to_end():
    """Full Tier A: STL → metadata + wrapper + 4 views (no mocks)."""
    mesh = trimesh.creation.cylinder(radius=15, height=25)
    stl_path = _make_test_stl(mesh)

    try:
        # Mock only RAG (cluster may not be available)
        with patch("mcp_server.stl_converter.rag_client") as mock_rag:
            mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 2}
            result = analyze_stl(stl_path)

        assert result["success"] is True
        assert result["metadata"]["bbox"][2] == pytest.approx(25.0, abs=0.5)
        assert len(result["views"]) == 4
        assert os.path.isfile(result["scad_path"])
    finally:
        os.unlink(stl_path)
```

**Expected:** 4 views rendered, metadata correct.
**Failure indicates:** OpenSCAD rendering pipeline broken for STL imports.

### 2.4 Non-Manifold STL Handling

**Purpose:** Verify metadata still extracts from a non-manifold mesh.

```python
@pytest.mark.integration
def test_non_manifold_stl_metadata_extraction():
    """Non-manifold mesh → metadata extracted, is_manifold=False."""
    # Create two separate boxes (non-manifold since they don't share edges)
    box1 = trimesh.creation.box(extents=[10, 10, 10])
    box2 = trimesh.creation.box(extents=[10, 10, 10])
    box2.apply_translation([20, 0, 0])  # Floating, not connected
    combined = trimesh.util.concatenate([box1, box2])

    stl_path = _make_test_stl(combined)
    try:
        meta = extract_metadata(stl_path)
        assert "error" not in meta
        assert meta["is_manifold"] is False
        assert meta["face_count"] == 24  # 12 per cube
    finally:
        os.unlink(stl_path)
```

---

## Phase 3: Cluster Integration Tests (require ChromaDB + MQTT)

These tests need the AI cluster running: ChromaDB at 10.0.1.81:8000, MQTT at 10.0.1.82:1883. Mark with `@pytest.mark.cluster`.

Run with: `.venv/bin/python -m pytest tests/test_stl_integration.py -v -m cluster`

### 3.1 RAG Round-Trip

**Purpose:** Store STL analysis in RAG, then search for it.

```
1. Create a cube STL (known dimensions: 30x20x10)
2. Call analyze_stl (no mocks — real MQTT, real ChromaDB)
3. Wait 2 seconds for MQTT→bridge→ChromaDB pipeline
4. Call search_knowledge_base("30x20x10 cuboid", collection="design_history")
5. Verify the stored metadata appears in results
6. Cleanup: delete the RAG entry
```

**Expected:** Search returns the stored metadata chunk.
**Failure indicates:** MQTT bridge not processing store requests, or ChromaDB embedding/query mismatch.

### 3.2 MQTT Events Published

**Purpose:** Verify all 3 tools publish their MQTT events.

```
1. Subscribe to openscad/stl/# via mosquitto_sub (background)
2. Call analyze_stl on a test cube
3. Call convert_stl_to_scad on a test cube
4. Call reverse_engineer_stl on a test cube
5. Verify 3 messages received:
   - openscad/stl/analyzed
   - openscad/stl/converted
   - openscad/stl/reverse_engineer_started
6. Verify each message has correct payload structure
```

**Expected:** 3 JSON messages with correct topics.
**Failure indicates:** MQTT broker unreachable or publish_event not called.

### 3.3 Dedup on Re-Analysis

**Purpose:** Analyzing the same STL twice should upsert (not duplicate) in RAG.

```
1. Create a test cube STL
2. Call analyze_stl twice
3. Search RAG for the filename
4. Verify only 1 set of chunks (not 2)
```

**Expected:** Single entry — upsert by deterministic ID.
**Failure indicates:** Document ID format issue or ChromaDB bridge not handling upserts.

---

## Phase 4: Manual Verification Checklist

These require human judgment or visual inspection. Run interactively via Claude Code MCP.

| # | Test | How to Verify | Status |
|---|------|--------------|--------|
| 1 | `analyze_stl` on a real-world STL from Thingiverse | Download a simple bracket STL, run analyze_stl, check metadata makes sense | [ ] |
| 2 | Multi-view PNGs look correct | Open the 4 generated PNGs, verify front/top/right/iso angles are correct | [ ] |
| 3 | `convert_stl_to_scad` on a simple cube STL | Verify generated BOSL2 code renders a shape matching the original | [ ] |
| 4 | `reverse_engineer_stl` enables Claude feedback loop | Call the tool, then use returned views to write BOSL2 code, iterate | [ ] |
| 5 | RAG search finds past conversions | After analyzing 2-3 STLs, search_knowledge_base for "mounting bracket" | [ ] |
| 6 | Graceful degradation: kill ChromaDB | Set RAG_ENABLED=false, run analyze_stl, verify it still works | [ ] |
| 7 | Complex STL reports "too complex" | Use an organic/curved STL, verify convert_stl_to_scad returns null primitive | [ ] |
| 8 | check_environment shows STL capability | Run check_environment, verify trimesh-related info appears | [ ] |

---

## Phase 5: Performance Benchmarks

Not automated — run manually and record results.

| Test | STL Size | Expected | Metric |
|------|----------|----------|--------|
| Small cube (12 faces) | ~1 KB | < 100ms | `extract_metadata` time |
| Medium bracket (~5K faces) | ~250 KB | < 500ms | `extract_metadata` time |
| Large model (~100K faces) | ~5 MB | < 2s | `extract_metadata` time |
| Multi-view render (small) | ~1 KB | < 30s | `analyze_stl` total time |
| Multi-view render (medium) | ~250 KB | < 60s | `analyze_stl` total time |

---

## Test Execution Order

1. **Phase 1** — Run immediately, no infrastructure needed. Add missing unit tests to `tests/test_stl_converter.py`.
2. **Phase 2** — Run on any machine with OpenSCAD installed. Create `tests/test_stl_integration.py`.
3. **Phase 3** — Run when cluster is up (AI-03 ChromaDB, AI-02 MQTT broker).
4. **Phase 4** — Manual verification during first real usage session.
5. **Phase 5** — Run once with varied STL sizes to establish baselines.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OpenSCAD can't render STL imports headlessly | Low | High | Tested in Phase 2.1; fallback to trimesh renderer is designed but not yet implemented |
| Primitive fitting classifies shapes incorrectly | Medium | Low | User sees confidence score; can always fall back to Tier C |
| Large STLs cause OOM in trimesh | Very Low | Medium | trimesh is memory-efficient; would only happen with 500K+ face models |
| MQTT bridge drops store messages | Low | Low | Fire-and-forget design; analysis still works without RAG |
| Generated BOSL2 code doesn't compile | Low | Medium | Tested in Phase 2.2; code generation is template-based |
