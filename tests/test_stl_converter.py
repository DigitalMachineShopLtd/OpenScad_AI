"""Tests for STL converter — metadata extraction, primitive fitting, code generation."""

import json
import os
import tempfile
import glob

import pytest
import trimesh
from unittest.mock import patch, MagicMock

from mcp_server.stl_converter import (
    extract_metadata,
    generate_import_wrapper,
    fit_primitive,
    make_stl_chunks,
    analyze_stl,
    convert_stl,
    reverse_engineer,
)


def _make_test_stl(mesh: trimesh.Trimesh) -> str:
    """Write a trimesh mesh to a temporary STL file, return path."""
    f = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
    mesh.export(f.name, file_type="stl")
    f.close()
    return f.name


# ── extract_metadata ─────────────────────────────────────────────────────────

def test_extract_metadata_cube():
    """Cube STL → correct bounding box, volume, face count."""
    mesh = trimesh.creation.box(extents=[10, 20, 30])
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        assert meta["bbox"] == pytest.approx([10.0, 20.0, 30.0], abs=0.1)
        assert meta["volume"] == pytest.approx(6000.0, rel=0.01)
        assert meta["face_count"] == 12
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


# ── generate_import_wrapper ──────────────────────────────────────────────────

def test_generate_import_wrapper():
    """Import wrapper creates a .scad file with import() statement."""
    mesh = trimesh.creation.box(extents=[10, 10, 10])
    stl_path = _make_test_stl(mesh)
    try:
        scad_path = generate_import_wrapper(stl_path)
        assert os.path.isfile(scad_path)
        assert scad_path.endswith(".scad")

        content = open(scad_path).read()
        assert f'import("{stl_path}")' in content or f'import("{os.path.abspath(stl_path)}")' in content
        assert "BOSL2" not in content

        os.unlink(scad_path)
    finally:
        os.unlink(stl_path)


def test_generate_import_wrapper_missing_stl():
    """Non-existent STL → returns None."""
    result = generate_import_wrapper("/nonexistent/file.stl")
    assert result is None


# ── fit_primitive ────────────────────────────────────────────────────────────

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
    mesh = trimesh.creation.box(extents=[10, 10, 10])
    path = _make_test_stl(mesh)
    try:
        meta = extract_metadata(path)
        meta["convex_hull_ratio"] = 0.5  # Force complex
        result = fit_primitive(meta)
        assert result["primitive"] is None
        assert result["scad_code"] is None
    finally:
        os.unlink(path)


# ── make_stl_chunks ──────────────────────────────────────────────────────────

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

    assert chunks[0]["id"] == "openscad_ai:stl_conversions/test-cube.stl:0"
    assert "6000" in chunks[0]["document"]
    assert chunks[0]["metadata"]["file_type"] == "stl_metadata"

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


# ── analyze_stl ──────────────────────────────────────────────────────────────

def test_analyze_stl_extracts_metadata():
    """analyze_stl extracts metadata and returns correct structure."""
    mesh = trimesh.creation.box(extents=[20, 15, 10])
    stl_path = _make_test_stl(mesh)

    try:
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

                result = analyze_stl(stl_path)

        assert result["success"] is True
        assert "metadata" in result
        assert result["metadata"]["bbox"] == pytest.approx([20.0, 15.0, 10.0], abs=0.1)
        assert "views" in result
        assert "scad_path" in result
    finally:
        os.unlink(stl_path)
        for f in glob.glob("/home/tie/OpenScad_AI/output/stl_imports/*.scad"):
            os.unlink(f)


# ── convert_stl ──────────────────────────────────────────────────────────────

def test_convert_stl_produces_scad_file():
    """convert_stl writes a .scad file with BOSL2 primitive."""
    mesh = trimesh.creation.box(extents=[30, 20, 10])
    stl_path = _make_test_stl(mesh)

    try:
        with patch("mcp_server.stl_converter.rag_client") as mock_rag:
            mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 2}

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
                "convex_hull_ratio": 0.5,
                "is_manifold": True,
                "original_path": stl_path,
            }
            with patch("mcp_server.stl_converter.rag_client"):
                result = convert_stl(stl_path)

        assert result["success"] is True
        assert result["primitive"] is None
        assert result["scad_path"] is None
    finally:
        os.unlink(stl_path)


# ── reverse_engineer ─────────────────────────────────────────────────────────

def test_reverse_engineer_returns_views_and_metadata():
    """reverse_engineer returns views + metadata for Claude."""
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

                result = reverse_engineer(stl_path, description="test cube")

        assert result["success"] is True
        assert result["metadata"]["bbox"] == pytest.approx([25.0, 15.0, 10.0], abs=0.1)
        assert len(result["views"]) == 4
        assert result["description"] == "test cube"
    finally:
        os.unlink(stl_path)
        for f in glob.glob("/home/tie/OpenScad_AI/output/stl_imports/*.scad"):
            os.unlink(f)
