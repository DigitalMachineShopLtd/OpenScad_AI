"""STL-to-OpenSCAD conversion — metadata extraction, primitive fitting, code generation."""

import json
import logging
import os
from pathlib import Path

import trimesh

from mcp_server.openscad import PROJECT_DIR, render_multi_view
from mcp_server import rag_client

log = logging.getLogger(__name__)


def extract_metadata(stl_path: str) -> dict:
    """Load an STL file and extract geometric metadata.

    Returns dict with bbox, volume, surface_area, face_count, vertex_count,
    convex_hull_ratio, is_manifold, and source path. Returns {"error": ...} on failure.
    """
    if not os.path.isfile(stl_path):
        return {"error": f"File not found: {stl_path}"}

    try:
        mesh = trimesh.load(stl_path, force="mesh")
    except Exception as e:
        return {"error": f"Failed to load STL: {e}"}

    bounds = mesh.bounds
    if bounds is None:
        return {"error": f"Empty or corrupt STL file: {stl_path}"}

    bbox = [
        float(bounds[1][0] - bounds[0][0]),
        float(bounds[1][1] - bounds[0][1]),
        float(bounds[1][2] - bounds[0][2]),
    ]

    try:
        hull_volume = mesh.convex_hull.volume
        convex_hull_ratio = float(mesh.volume / hull_volume) if hull_volume > 0 else 0.0
    except Exception:
        convex_hull_ratio = 0.0

    # Detect symmetry axes by comparing bounding box dimensions
    symmetry = []
    if abs(bbox[0] - bbox[1]) / max(bbox[0], bbox[1], 1e-9) < 0.05:
        symmetry.append("Z")
    if abs(bbox[0] - bbox[2]) / max(bbox[0], bbox[2], 1e-9) < 0.05:
        symmetry.append("Y")
    if abs(bbox[1] - bbox[2]) / max(bbox[1], bbox[2], 1e-9) < 0.05:
        symmetry.append("X")

    return {
        "bbox": bbox,
        "volume": float(mesh.volume),
        "surface_area": float(mesh.area),
        "face_count": len(mesh.faces),
        "vertex_count": len(mesh.vertices),
        "convex_hull_ratio": convex_hull_ratio,
        "is_manifold": bool(mesh.is_watertight),
        "symmetry": symmetry,
        "source": "external",
        "original_path": stl_path,
    }


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


def fit_primitive(metadata: dict) -> dict:
    """Attempt to fit the closest BOSL2 primitive to the mesh.

    Only attempts fitting when convex_hull_ratio > 0.85.

    Returns dict with 'primitive' (str|None), 'scad_code' (str|None),
    'confidence' (float).
    """
    if "error" in metadata:
        return {"primitive": None, "scad_code": None, "confidence": 0.0}

    hull_ratio = metadata.get("convex_hull_ratio", 0.0)
    if hull_ratio <= 0.85:
        return {"primitive": None, "scad_code": None, "confidence": 0.0}

    bbox = metadata["bbox"]
    x, y, z = sorted(bbox)

    if x == 0:
        return {"primitive": None, "scad_code": None, "confidence": 0.0}

    ratio_med_small = y / x
    ratio_large_med = z / y if y > 0 else 999

    # Sphere: all three axes within 20% of each other
    if ratio_med_small <= 1.2 and ratio_large_med <= 1.2:
        diameter = max(bbox)
        scad = _sphere_code(diameter, metadata, hull_ratio)
        return {"primitive": "sphere", "scad_code": scad, "confidence": hull_ratio}

    # Cylinder: two axes within 20%, third >1.5x
    if ratio_med_small <= 1.2 and ratio_large_med > 1.5:
        diameter = (x + y) / 2
        height = z
        scad = _cylinder_code(diameter, height, bbox, metadata, hull_ratio)
        return {"primitive": "cylinder", "scad_code": scad, "confidence": hull_ratio * 0.9}

    # Default: cuboid
    scad = _cuboid_code(bbox, metadata, hull_ratio)
    return {"primitive": "cuboid", "scad_code": scad, "confidence": hull_ratio}


def _sphere_code(diameter, meta, confidence):
    d = round(diameter, 1)
    return (
        f"// Approximate primitive fit from STL analysis\n"
        f"// Source: {Path(meta.get('original_path', 'unknown')).name}\n"
        f"// Confidence: {confidence:.2f} (sphere)\n"
        f"// Bounding box: {meta['bbox'][0]:.1f} x {meta['bbox'][1]:.1f} x {meta['bbox'][2]:.1f} mm\n"
        f"\ninclude <BOSL2/std.scad>\n\n"
        f"sphere(d={d}, $fn=64);\n"
    )


def _cylinder_code(diameter, height, bbox, meta, confidence):
    d = round(diameter, 1)
    h = round(height, 1)
    return (
        f"// Approximate primitive fit from STL analysis\n"
        f"// Source: {Path(meta.get('original_path', 'unknown')).name}\n"
        f"// Confidence: {confidence:.2f} (cylinder)\n"
        f"// Bounding box: {bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f} mm\n"
        f"\ninclude <BOSL2/std.scad>\n\n"
        f"cyl(d={d}, h={h}, $fn=64);\n"
    )


def _cuboid_code(bbox, meta, confidence):
    dims = [round(d, 1) for d in bbox]
    return (
        f"// Approximate primitive fit from STL analysis\n"
        f"// Source: {Path(meta.get('original_path', 'unknown')).name}\n"
        f"// Confidence: {confidence:.2f} (cuboid)\n"
        f"// Bounding box: {bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f} mm\n"
        f"\ninclude <BOSL2/std.scad>\n\n"
        f"cuboid([{dims[0]}, {dims[1]}, {dims[2]}]);\n"
    )


def make_stl_chunks(
    stl_filename: str,
    metadata: dict,
    scad_code: str | None = None,
    view_descriptions: str | None = None,
) -> list[dict]:
    """Create RAG chunks from STL analysis results.

    Returns list of chunk dicts ready for rag_client.store_chunks().
    """
    base_id = f"openscad_ai:stl_conversions/{stl_filename}"
    chunks = []

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


def analyze_stl(stl_path: str) -> dict:
    """Tier A: Load STL, extract metadata, generate import wrapper, render views, store in RAG."""
    metadata = extract_metadata(stl_path)
    if "error" in metadata:
        return {"success": False, "error": metadata["error"]}

    scad_path = generate_import_wrapper(stl_path)
    if scad_path is None:
        return {"success": False, "error": "Failed to generate import wrapper", "metadata": metadata}

    views_result = {"success": False, "views": [], "errors": ["Rendering skipped"]}
    try:
        views_result = render_multi_view(scad_path)
    except Exception as e:
        log.warning("Multi-view render failed for STL %s: %s", stl_path, e)

    stl_filename = Path(stl_path).name
    try:
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


def convert_stl(stl_path: str) -> dict:
    """Tier B: Attempt primitive fitting on an STL file."""
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


def reverse_engineer(stl_path: str, description: str = "") -> dict:
    """Tier C: Prepare STL for AI visual reverse engineering."""
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
