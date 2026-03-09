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
