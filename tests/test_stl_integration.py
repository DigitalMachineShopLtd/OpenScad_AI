"""Integration tests for STL converter — require OpenSCAD installed."""

import os
import tempfile

import pytest
import trimesh
from unittest.mock import patch

from mcp_server.stl_converter import (
    extract_metadata,
    generate_import_wrapper,
    analyze_stl,
    convert_stl,
)
from mcp_server.openscad import render_multi_view, validate, _find_openscad


# Skip all tests if OpenSCAD not available
pytestmark = pytest.mark.skipif(
    _find_openscad() is None,
    reason="OpenSCAD not installed"
)


def _make_test_stl(mesh: trimesh.Trimesh) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".stl", delete=False)
    mesh.export(f.name, file_type="stl")
    f.close()
    return f.name


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
        if scad_path and os.path.isfile(scad_path):
            os.unlink(scad_path)


def test_generated_cuboid_code_compiles():
    """BOSL2 cuboid code from convert_stl compiles in OpenSCAD."""
    mesh = trimesh.creation.box(extents=[30, 20, 10])
    stl_path = _make_test_stl(mesh)

    try:
        with patch("mcp_server.stl_converter.rag_client") as mock_rag:
            mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 2}
            result = convert_stl(stl_path)

        assert result["scad_path"] is not None

        validation = validate(result["scad_path"])
        assert validation.syntax_ok is True

        if result["scad_path"] and os.path.isfile(result["scad_path"]):
            os.unlink(result["scad_path"])
    finally:
        os.unlink(stl_path)


def test_analyze_stl_end_to_end():
    """Full Tier A: STL → metadata + wrapper + 4 views (real OpenSCAD)."""
    mesh = trimesh.creation.cylinder(radius=15, height=25)
    stl_path = _make_test_stl(mesh)

    try:
        with patch("mcp_server.stl_converter.rag_client") as mock_rag:
            mock_rag.store_chunks.return_value = {"success": True, "chunks_sent": 2}
            result = analyze_stl(stl_path)

        assert result["success"] is True
        assert result["metadata"]["bbox"][2] == pytest.approx(25.0, abs=0.5)
        assert len(result["views"]) == 4
        assert os.path.isfile(result["scad_path"])
    finally:
        os.unlink(stl_path)
        if result.get("scad_path") and os.path.isfile(result["scad_path"]):
            os.unlink(result["scad_path"])


def test_non_manifold_stl_metadata_extraction():
    """Non-manifold mesh → metadata extracted, is_manifold=False."""
    import numpy as np

    box = trimesh.creation.box(extents=[10, 10, 10])
    # Remove two faces to break watertightness
    faces = box.faces[:-2]
    broken = trimesh.Trimesh(vertices=box.vertices, faces=faces, process=False)

    stl_path = _make_test_stl(broken)
    try:
        meta = extract_metadata(stl_path)
        assert "error" not in meta
        assert meta["is_manifold"] is False
        assert meta["face_count"] == 10
    finally:
        os.unlink(stl_path)
