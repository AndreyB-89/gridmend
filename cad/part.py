"""General CadQuery part template for GridMend.

A ring is one shape. This builder takes any outline the detector measured in
card-plane millimetres, cuts its holes, and extrudes it by the thickness the
engineer measured. `cad/ring.py` stays for the ring path, where a circle fit gives
a cleaner number than a traced contour, plus the groove and the missing arc.

All units are mm. No model-written code runs here: inputs are typed fields only.

Coordinates: the card plane is an image plane, so y grows downward. CAD seen from
+Z has y growing upward. Every outline is flipped in y on the way in, or the STEP
would be a mirror of the photo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

from api.schemas import CadCheck
from cad.ring import (
    BBOX_TOL_MM,
    MAX_OUTER_MM,
    MAX_THICKNESS_MM,
    STL_ANGULAR_TOL,
    STL_BOUNDS_TOL_MM,
    STL_LINEAR_TOL,
    VOLUME_REL_TOL,
    CadError,
    NeedsInput,
    _tight_bbox,
)

# A traced contour has hundreds of points with sub-millimetre wobble. Extruding all
# of them makes a heavy and fragile solid, so the outline is simplified first. The
# volume check then uses the SAME simplified polygon, never an ideal shape.
SIMPLIFY_MM = 0.4
MIN_POINTS = 3
MIN_AREA_MM2 = 4.0

LIMIT_PHOTO = "Shape traced from one photo; no physical fit verified."
LIMIT_FLAT = "The part is assumed flat on the table and of one even thickness."
LIMIT_HOLES = "Holes are cut straight through, square to the face."


@dataclass
class PartOutput:
    step_path: Path
    stl_path: Path
    checks: list[CadCheck] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _polygon(points, label: str) -> np.ndarray:
    """Clean one closed polygon: flip y, simplify, check it is a real simple loop."""
    arr = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    if len(arr) < MIN_POINTS:
        raise NeedsInput(f"The {label} needs at least {MIN_POINTS} points.")
    if not np.all(np.isfinite(arr)):
        raise CadError(f"The {label} has a point that is not a real number.")
    arr = arr * (1.0, -1.0)  # image y-down -> CAD y-up
    import cv2

    simple = cv2.approxPolyDP(arr.astype(np.float32).reshape(-1, 1, 2), SIMPLIFY_MM, True)
    arr = simple.reshape(-1, 2).astype(np.float64)
    if len(arr) < MIN_POINTS:
        raise CadError(f"The {label} is too small or too thin to build.")
    if _self_crosses(arr):
        raise CadError(f"The {label} crosses itself. The photo trace is not a clean loop.")
    if abs(_area(arr)) < MIN_AREA_MM2:
        raise CadError(f"The {label} encloses almost no area ({abs(_area(arr)):.2f} mm2).")
    return arr


def _area(poly: np.ndarray) -> float:
    """Signed area, shoelace. Positive means counter-clockwise."""
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def _segments_cross(a, b, c, d) -> bool:
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2, d3, d4 = side(c, d, a), side(c, d, b), side(a, b, c), side(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _self_crosses(poly: np.ndarray) -> bool:
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue
            if _segments_cross(a, b, poly[j], poly[(j + 1) % n]):
                return True
    return False


def _inside(poly: np.ndarray, point) -> bool:
    import cv2

    return cv2.pointPolygonTest(poly.astype(np.float32), (float(point[0]), float(point[1])), False) > 0


def _wire(wp: cq.Workplane, poly: np.ndarray) -> cq.Workplane:
    return wp.polyline([(float(x), float(y)) for x, y in poly]).close()


def validate(outline, holes, thickness_mm) -> tuple[np.ndarray, list[np.ndarray], float]:
    if thickness_mm is None:
        raise NeedsInput("Please give and confirm the thickness.")
    t = float(thickness_mm)
    if not math.isfinite(t):
        raise CadError("Thickness must be a real number.")
    if t <= 0:
        raise CadError("Thickness must be greater than 0 mm.")
    if t > MAX_THICKNESS_MM:
        raise CadError(f"Thickness must be {MAX_THICKNESS_MM:g} mm or less.")

    outer = _polygon(outline, "outline")
    span = outer.max(axis=0) - outer.min(axis=0)
    if max(span) > MAX_OUTER_MM:
        raise CadError(f"The part is {max(span):.0f} mm long. It must be {MAX_OUTER_MM:g} mm or less.")

    cut: list[np.ndarray] = []
    for i, hole in enumerate(holes or []):
        try:
            poly = _polygon(hole, f"hole {i + 1}")
        except (CadError, NeedsInput):
            continue  # a hole too small or too ragged to trust is left out, not fatal
        if not all(_inside(outer, p) for p in poly):
            raise CadError(f"Hole {i + 1} is not fully inside the part. Check the photo trace.")
        cut.append(poly)
    return outer, cut, t


def generate_part(outline_mm, holes_mm, thickness_mm, out_dir, design_id: str) -> PartOutput:
    """Extrude one measured outline, with its holes cut through, to `thickness_mm`."""
    outer, holes, t = validate(outline_mm, holes_mm, thickness_mm)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Move the part so its bounding box starts at the origin: a STEP that opens in
    # the corner of the CAD grid, not a thousand millimetres away from it.
    shift = outer.min(axis=0)
    outer = outer - shift
    holes = [h - shift for h in holes]
    size = outer.max(axis=0)

    try:
        solid = _wire(cq.Workplane("XY"), outer).extrude(t)
        for hole in holes:
            solid = solid.cut(_wire(cq.Workplane("XY"), hole).extrude(t))
    except Exception as exc:  # noqa: BLE001 - CAD kernel errors become user-facing errors
        raise CadError(f"CAD build failed: {exc}") from exc

    step_path = out_dir / f"{design_id}.step"
    stl_path = out_dir / f"{design_id}.stl"
    try:
        cq.exporters.export(solid, str(step_path))
        cq.exporters.export(solid, str(stl_path), tolerance=STL_LINEAR_TOL, angularTolerance=STL_ANGULAR_TOL)
    except Exception as exc:  # noqa: BLE001
        raise CadError(f"Export failed: {exc}") from exc

    checks = _check(solid, step_path, stl_path, outer, holes, size, t)
    failed = [c for c in checks if not c.passed]
    if failed:
        raise CadError("CAD checks failed: " + "; ".join(f"{c.name}: {c.detail}" for c in failed))

    limitations = [LIMIT_PHOTO, LIMIT_FLAT]
    if holes:
        limitations.append(LIMIT_HOLES)
    return PartOutput(step_path=step_path, stl_path=stl_path, checks=checks, limitations=limitations)


def _bbox_ok(bb, size, t: float) -> tuple[bool, str]:
    ok = (
        abs(bb.xlen - size[0]) <= BBOX_TOL_MM
        and abs(bb.ylen - size[1]) <= BBOX_TOL_MM
        and abs(bb.zlen - t) <= BBOX_TOL_MM
        and abs(bb.zmin) <= BBOX_TOL_MM
    )
    return ok, (f"bbox {bb.xlen:.3f} x {bb.ylen:.3f} x {bb.zlen:.3f} mm "
                f"(nominal {size[0]:.3f} x {size[1]:.3f} x {t:.3f})")


def _check(solid, step_path, stl_path, outer, holes, size, t) -> list[CadCheck]:
    checks: list[CadCheck] = []

    solids = solid.solids().vals()
    solid_ok = len(solids) == 1 and solids[0].isValid()
    checks.append(CadCheck(name="SOLID", passed=solid_ok, detail=f"{len(solids)} solid(s), valid={solid_ok}"))
    shape = solid.val()

    dim_ok, dim_detail = _bbox_ok(_tight_bbox(shape), size, t)
    checks.append(CadCheck(name="DIMENSIONS", passed=dim_ok, detail=dim_detail))

    # The analytic volume uses the same simplified polygons that were extruded.
    expected = (abs(_area(outer)) - sum(abs(_area(h)) for h in holes)) * t
    vol = shape.Volume()
    rel = abs(vol - expected) / expected if expected > 0 else 1.0
    checks.append(CadCheck(name="PROFILE", passed=rel <= VOLUME_REL_TOL,
                           detail=f"volume {vol:.2f} mm3 vs outline area x thickness {expected:.2f} mm3 "
                                  f"(diff {rel * 100:.4f}%)"))

    try:
        re = cq.importers.importStep(str(step_path))
        re_solids = re.solids().vals()
        re_ok = len(re_solids) == 1 and re_solids[0].isValid()
        re_vol = re_solids[0].Volume() if re_solids else 0.0
        re_rel = abs(re_vol - vol) / vol if vol > 0 else 1.0
        bb_ok, bb_detail = _bbox_ok(_tight_bbox(re_solids[0]), size, t) if re_solids else (False, "no solid")
        step_ok = re_ok and re_rel <= VOLUME_REL_TOL and bb_ok
        step_detail = f"{len(re_solids)} solid(s), volume diff {re_rel * 100:.4f}%, {bb_detail}"
    except Exception as exc:  # noqa: BLE001
        step_ok, step_detail = False, f"STEP re-import failed: {exc}"
    checks.append(CadCheck(name="STEP_REIMPORT", passed=step_ok, detail=step_detail))

    try:
        mesh = trimesh.load(str(stl_path), force="mesh")
        ext = mesh.bounds[1] - mesh.bounds[0]
        bounds_ok = (
            abs(ext[0] - size[0]) <= STL_BOUNDS_TOL_MM
            and abs(ext[1] - size[1]) <= STL_BOUNDS_TOL_MM
            and abs(ext[2] - t) <= STL_BOUNDS_TOL_MM
        )
        mesh_ok = bool(mesh.is_watertight) and mesh.volume > 0 and bounds_ok
        mesh_detail = (f"watertight={mesh.is_watertight}, volume {mesh.volume:.2f} mm3, "
                       f"extent {ext[0]:.3f} x {ext[1]:.3f} x {ext[2]:.3f} mm, {len(mesh.faces)} faces")
    except Exception as exc:  # noqa: BLE001
        mesh_ok, mesh_detail = False, f"STL load failed: {exc}"
    checks.append(CadCheck(name="STL_MESH", passed=mesh_ok, detail=mesh_detail))
    return checks
