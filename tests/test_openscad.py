"""Tests for OpenSCAD wrapper — multi-view rendering."""
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
