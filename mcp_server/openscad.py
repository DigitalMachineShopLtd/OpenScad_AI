"""Centralized OpenSCAD CLI wrapper. Single source of truth for detection, invocation, and headless support."""

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class RenderResult:
    success: bool
    file_path: str | None = None
    size_bytes: int = 0
    duration_ms: int = 0
    errors: list[str] | None = None
    warnings: list[str] | None = None


@dataclass
class ValidationResult:
    syntax_ok: bool
    export_ok: bool
    manifold_ok: bool
    overall: bool
    errors: list[str]
    warnings: list[str]


def _find_openscad() -> str | None:
    """Find OpenSCAD binary. Priority: project AppImage > system > macOS app."""
    appimage = PROJECT_DIR / "bin" / "OpenSCAD-latest.AppImage"
    if appimage.is_file() and os.access(appimage, os.X_OK):
        return str(appimage)

    system = shutil.which("openscad")
    if system:
        return system

    macos = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    if os.path.isfile(macos):
        return macos

    return None


def _build_cmd(openscad_bin: str) -> list[str]:
    """Wrap with xvfb-run if headless."""
    if os.environ.get("DISPLAY") or not shutil.which("xvfb-run"):
        return [openscad_bin]
    return ["xvfb-run", "-a", openscad_bin]


_openscad_path: str | None = None
_base_cmd: list[str] | None = None


def get_openscad() -> tuple[str, list[str]]:
    """Return (openscad_path, base_command). Cached after first call."""
    global _openscad_path, _base_cmd
    if _openscad_path is None:
        _openscad_path = _find_openscad()
        if _openscad_path is None:
            raise FileNotFoundError("OpenSCAD not found. Run ./scripts/setup.sh")
        _base_cmd = _build_cmd(_openscad_path)
        log.info("OpenSCAD found: %s (cmd: %s)", _openscad_path, _base_cmd)
    return _openscad_path, _base_cmd


def get_version() -> str:
    """Return OpenSCAD version string."""
    _, cmd = get_openscad()
    result = subprocess.run(
        cmd + ["--version"], capture_output=True, text=True, timeout=15
    )
    version = (result.stdout.strip() or result.stderr.strip()).split("\n")[0]
    return version


def _run_openscad(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Run OpenSCAD with given args."""
    _, cmd = get_openscad()
    full_cmd = cmd + args
    log.debug("Running: %s", " ".join(full_cmd))
    return subprocess.run(
        full_cmd, capture_output=True, text=True, timeout=timeout
    )


def _parse_output(stderr: str) -> tuple[list[str], list[str]]:
    """Extract errors and warnings from OpenSCAD stderr."""
    errors = []
    warnings = []
    for line in stderr.splitlines():
        line_lower = line.lower()
        if "error" in line_lower:
            errors.append(line.strip())
        elif "warning" in line_lower:
            warnings.append(line.strip())
    return errors, warnings


def validate(scad_file: str) -> ValidationResult:
    """Three-stage validation: syntax, STL export, manifold check."""
    scad_path = Path(scad_file)
    if not scad_path.is_file():
        return ValidationResult(
            syntax_ok=False, export_ok=False, manifold_ok=False,
            overall=False, errors=[f"File not found: {scad_file}"], warnings=[]
        )

    all_errors = []
    all_warnings = []

    # 1. Syntax check
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=True) as tmp:
        result = _run_openscad(["-o", tmp.name, str(scad_path)], timeout=60)
        errors, warnings = _parse_output(result.stderr)
        syntax_ok = len(errors) == 0
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    # 2. STL export test
    export_ok = False
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = _run_openscad(["-o", tmp_path, str(scad_path)], timeout=120)
        errors, warnings = _parse_output(result.stderr)
        if not errors and Path(tmp_path).stat().st_size > 0:
            export_ok = True
        else:
            all_errors.extend(errors)
        all_warnings.extend(warnings)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 3. Manifold check
    manifold_ok = True
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = _run_openscad(["-o", tmp_path, str(scad_path)], timeout=120)
        if "WARNING: Object may not be a valid 2-manifold" in result.stderr:
            manifold_ok = False
            all_warnings.append("Non-manifold geometry detected — may cause slicing issues")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    overall = syntax_ok and export_ok and manifold_ok
    log.info("Validate %s: syntax=%s export=%s manifold=%s overall=%s",
             scad_file, syntax_ok, export_ok, manifold_ok, overall)
    return ValidationResult(
        syntax_ok=syntax_ok, export_ok=export_ok, manifold_ok=manifold_ok,
        overall=overall, errors=all_errors, warnings=all_warnings
    )


def render_stl(scad_file: str, output_dir: str | None = None) -> RenderResult:
    """Render high-quality STL."""
    scad_path = Path(scad_file)
    if not scad_path.is_file():
        return RenderResult(success=False, errors=[f"File not found: {scad_file}"])

    if output_dir is None:
        output_dir = str(PROJECT_DIR / "output" / "stl")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    out_file = Path(output_dir) / f"{scad_path.stem}.stl"

    import time
    start = time.monotonic()
    result = _run_openscad(["--render", "-o", str(out_file), str(scad_path)], timeout=600)
    elapsed = int((time.monotonic() - start) * 1000)

    errors, warnings = _parse_output(result.stderr)

    if result.returncode == 0 and out_file.is_file() and out_file.stat().st_size > 0:
        size = out_file.stat().st_size
        log.info("STL rendered: %s (%d bytes, %dms)", out_file, size, elapsed)
        return RenderResult(
            success=True, file_path=str(out_file),
            size_bytes=size, duration_ms=elapsed,
            errors=errors or None, warnings=warnings or None
        )
    else:
        log.error("STL render failed: %s", errors)
        return RenderResult(success=False, errors=errors, warnings=warnings or None, duration_ms=elapsed)


def render_png(
    scad_file: str,
    output_dir: str | None = None,
    imgsize: str = "1024,768",
    colorscheme: str = "Tomorrow",
    camera: str | None = None,
) -> RenderResult:
    """Render preview PNG."""
    scad_path = Path(scad_file)
    if not scad_path.is_file():
        return RenderResult(success=False, errors=[f"File not found: {scad_file}"])

    if output_dir is None:
        output_dir = str(PROJECT_DIR / "output" / "png")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    out_file = Path(output_dir) / f"{scad_path.stem}.png"

    args = [
        "--render",
        f"--imgsize={imgsize}",
        f"--colorscheme={colorscheme}",
        "--view=axes,scales",
    ]
    if camera:
        args.append(f"--camera={camera}")
    args.extend(["-o", str(out_file), str(scad_path)])

    import time
    start = time.monotonic()
    result = _run_openscad(args, timeout=300)
    elapsed = int((time.monotonic() - start) * 1000)

    errors, warnings = _parse_output(result.stderr)

    if out_file.is_file() and out_file.stat().st_size > 0:
        log.info("PNG rendered: %s (%dms)", out_file, elapsed)
        return RenderResult(
            success=True, file_path=str(out_file),
            size_bytes=out_file.stat().st_size, duration_ms=elapsed,
            warnings=warnings or None
        )
    else:
        return RenderResult(success=False, errors=errors or ["PNG render failed"], duration_ms=elapsed)


# Camera angles: translate_x,y,z,rot_x,y,z,distance
# rot_x = pitch (tilt up/down), rot_y = roll, rot_z = yaw (rotate around vertical)
MULTI_VIEW_CAMERAS = {
    "front":     "0,0,0,90,0,0,0",
    "top":       "0,0,0,0,0,0,0",
    "right":     "0,0,0,90,0,90,0",
    "isometric": "0,0,0,55,0,25,0",
}


def render_multi_view(
    scad_file: str,
    output_dir: str | None = None,
    imgsize: str = "800,600",
    colorscheme: str = "Tomorrow",
) -> dict:
    """Render front, top, right, and isometric PNG views of a design.

    Returns dict with 'success', 'views' (list of per-view results), 'errors'.
    Each view entry has: 'view', 'file_path', 'size_bytes', 'duration_ms'.
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


def find_bosl2() -> Path | None:
    """Find BOSL2 library installation."""
    candidates = [
        Path.home() / ".local" / "share" / "OpenSCAD" / "libraries" / "BOSL2",
        Path.home() / "Documents" / "OpenSCAD" / "libraries" / "BOSL2",
        Path("/usr/share/openscad/libraries/BOSL2"),
    ]
    for p in candidates:
        if p.is_dir() and (p / "std.scad").is_file():
            return p
    return None
