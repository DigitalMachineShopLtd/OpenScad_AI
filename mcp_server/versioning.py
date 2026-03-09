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
