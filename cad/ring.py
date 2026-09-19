"""Fixed CadQuery ring template for GridMend.

Revolves an (r, z) rectangle (with an optional inner groove) around Z.
All units are mm. Angles are degrees, counter-clockwise, 0 = +X.
No model-written code runs here: inputs are typed fields only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cadquery as cq
import trimesh

from api.schemas import CadCheck, GenerateRequest

MAX_OUTER_MM = 200.0
MAX_THICKNESS_MM = 50.0
MIN_WALL_MM = 0.8
BBOX_TOL_MM = 0.05
STL_BOUNDS_TOL_MM = 0.1
VOLUME_REL_TOL = 1e-3
STL_LINEAR_TOL = 0.05
STL_ANGULAR_TOL = 0.2

LIMIT_PHOTO = "Photo-derived dimensions are estimates; no physical fit verified."
LIMIT_RECT = "Profile simplified to a rectangle."
LIMIT_GROOVE = "Inner groove modeled as a rectangular cut."
LIMIT_MISSING = "Missing segment assumes the ring was a full circle."


class CadError(Exception):
    """CAD input is invalid or a check failed. Message is user-facing."""


class NeedsInput(Exception):
    """A required value is missing or not confirmed. Message lists what is missing."""


@dataclass
class RingOutput:
    step_path: Path
    stl_path: Path
    missing_stl_path: Path | None
    checks: list[CadCheck] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _arc_span(arc: tuple[float, float]) -> float:
    start, end = arc
    return (end - start) % 360.0


def validate_request(req: GenerateRequest) -> None:
    missing: list[str] = []
    for name in ("outer_diameter", "inner_diameter", "thickness"):
        dim = getattr(req, name)
        if dim.value_mm is None:
            missing.append(f"{name} (no value)")
        elif not dim.confirmed:
            missing.append(f"{name} (not confirmed)")
    if not req.profile_confirmed:
        missing.append("profile (not confirmed)")
    if missing:
        raise NeedsInput("Please give and confirm: " + ", ".join(missing) + ".")

    outer = float(req.outer_diameter.value_mm)
    inner = float(req.inner_diameter.value_mm)
    t = float(req.thickness.value_mm)
    for label, v in (("Outer diameter", outer), ("Inner diameter", inner), ("Thickness", t)):
        if not math.isfinite(v):
            raise CadError(f"{label} must be a real number.")
    if inner <= 0:
        raise CadError("Inner diameter must be greater than 0 mm.")
    if outer <= inner:
        raise CadError("Outer diameter must be greater than inner diameter.")
    if outer > MAX_OUTER_MM:
        raise CadError(f"Outer diameter must be {MAX_OUTER_MM:g} mm or less.")
    if t <= 0:
        raise CadError("Thickness must be greater than 0 mm.")
    if t > MAX_THICKNESS_MM:
        raise CadError(f"Thickness must be {MAX_THICKNESS_MM:g} mm or less.")

    if req.profile_rz_mm is not None:
        raise CadError("Custom profiles are not supported yet. Use the simplified rectangle.")

    if req.groove is not None:
        d, w = req.groove.depth_mm, req.groove.width_mm
        if not (math.isfinite(d) and math.isfinite(w)) or d <= 0 or w <= 0:
            raise CadError("Groove depth and width must be greater than 0 mm.")
        if w >= t:
            raise CadError("Groove width must be smaller than the thickness.")
        wall = (outer - inner) / 2.0 - d
        if wall < MIN_WALL_MM:
            raise CadError(
                f"Groove is too deep. The wall left is {wall:.2f} mm; "
                f"it must be at least {MIN_WALL_MM} mm."
            )

    if req.missing_arc_deg is not None:
        start, end = req.missing_arc_deg
        if not (math.isfinite(start) and math.isfinite(end)):
            raise CadError("Missing arc angles must be real numbers.")
        span = _arc_span(req.missing_arc_deg)
        if not (1.0 < span < 359.0):
            raise CadError("Missing arc must be between 1 and 359 degrees.")


def _profile_points(inner_r: float, outer_r: float, t: float, groove) -> list[tuple[float, float]]:
    """Closed (r, z) outline, counter-clockwise in the r-z plane."""
    if groove is None:
        return [(inner_r, 0.0), (outer_r, 0.0), (outer_r, t), (inner_r, t)]
    z0 = t / 2.0 - groove.width_mm / 2.0
    z1 = t / 2.0 + groove.width_mm / 2.0
    rg = inner_r + groove.depth_mm
    return [
        (inner_r, 0.0), (outer_r, 0.0), (outer_r, t), (inner_r, t),
        (inner_r, z1), (rg, z1), (rg, z0), (inner_r, z0),
    ]


def _revolve(points, angle_deg: float, start_deg: float = 0.0) -> cq.Workplane:
    # XZ workplane: local x = global X (radius), local y = global Z (height).
    # Revolving about local y = global Z sweeps CCW from +X (seen from +Z).
    wp = cq.Workplane("XZ").polyline(points).close().revolve(angle_deg, (0, 0, 0), (0, 1, 0))
    if start_deg:
        wp = wp.rotate((0, 0, 0), (0, 0, 1), start_deg)
    return wp


def _tight_bbox(shape):
    """Exact (optimal) bounding box, not the loose default one."""
    # useTriangulation=False: ignore any mesh left on the shape by STL export.
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    return cq.occ_impl.geom.BoundBox(box)


def _bbox_ok(bb, outer: float, t: float, tol: float) -> tuple[bool, str]:
    size = (bb.xlen, bb.ylen, bb.zlen)
    ok = (
        abs(bb.xlen - outer) <= tol
        and abs(bb.ylen - outer) <= tol
        and abs(bb.zlen - t) <= tol
        and abs(bb.zmin) <= tol
    )
    return ok, f"bbox {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f} mm (nominal {outer:.3f} x {outer:.3f} x {t:.3f})"


def generate_ring(req: GenerateRequest, out_dir: Path, design_id: str) -> RingOutput:
    validate_request(req)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outer = float(req.outer_diameter.value_mm)
    inner = float(req.inner_diameter.value_mm)
    t = float(req.thickness.value_mm)
    outer_r, inner_r = outer / 2.0, inner / 2.0
    groove = req.groove
    pts = _profile_points(inner_r, outer_r, t, groove)

    try:
        ring = _revolve(pts, 360.0)
        step_path = out_dir / f"{design_id}.step"
        stl_path = out_dir / f"{design_id}.stl"
        cq.exporters.export(ring, str(step_path))
        cq.exporters.export(ring, str(stl_path), tolerance=STL_LINEAR_TOL, angularTolerance=STL_ANGULAR_TOL)

        missing_stl_path: Path | None = None
        if req.missing_arc_deg is not None:
            start = req.missing_arc_deg[0] % 360.0
            seg = _revolve(pts, _arc_span(req.missing_arc_deg), start)
            missing_stl_path = out_dir / f"{design_id}-missing.stl"
            cq.exporters.export(seg, str(missing_stl_path), tolerance=STL_LINEAR_TOL, angularTolerance=STL_ANGULAR_TOL)
    except Exception as exc:  # noqa: BLE001 - CAD kernel errors become user-facing errors
        raise CadError(f"CAD build failed: {exc}") from exc

    checks: list[CadCheck] = []

    # SOLID
    solids = ring.solids().vals()
    solid_ok = len(solids) == 1 and solids[0].isValid()
    checks.append(CadCheck(name="SOLID", passed=solid_ok,
                           detail=f"{len(solids)} solid(s), valid={solid_ok}"))
    shape = ring.val()

    # DIMENSIONS
    dim_ok, dim_detail = _bbox_ok(_tight_bbox(shape), outer, t, BBOX_TOL_MM)
    checks.append(CadCheck(name="DIMENSIONS", passed=dim_ok, detail=dim_detail))

    # PROFILE (volume vs analytic)
    expected = math.pi * (outer_r**2 - inner_r**2) * t
    if groove is not None:
        expected -= math.pi * ((inner_r + groove.depth_mm) ** 2 - inner_r**2) * groove.width_mm
    vol = shape.Volume()
    rel = abs(vol - expected) / expected
    checks.append(CadCheck(name="PROFILE", passed=rel <= VOLUME_REL_TOL,
                           detail=f"volume {vol:.2f} mm3 vs analytic {expected:.2f} mm3 (diff {rel * 100:.4f}%)"))

    # STEP_REIMPORT
    try:
        re = cq.importers.importStep(str(step_path))
        re_solids = re.solids().vals()
        re_ok = len(re_solids) == 1 and re_solids[0].isValid()
        re_vol = re_solids[0].Volume() if re_solids else 0.0
        re_rel = abs(re_vol - vol) / vol
        bb_ok, bb_detail = _bbox_ok(_tight_bbox(re_solids[0]), outer, t, BBOX_TOL_MM) if re_solids else (False, "no solid")
        step_ok = re_ok and re_rel <= VOLUME_REL_TOL and bb_ok
        step_detail = f"{len(re_solids)} solid(s), volume diff {re_rel * 100:.4f}%, {bb_detail}"
    except Exception as exc:  # noqa: BLE001
        step_ok, step_detail = False, f"STEP re-import failed: {exc}"
    checks.append(CadCheck(name="STEP_REIMPORT", passed=step_ok, detail=step_detail))

    # STL_MESH
    try:
        mesh = trimesh.load(str(stl_path), force="mesh")
        ext = mesh.bounds[1] - mesh.bounds[0]
        bounds_ok = (
            abs(ext[0] - outer) <= STL_BOUNDS_TOL_MM
            and abs(ext[1] - outer) <= STL_BOUNDS_TOL_MM
            and abs(ext[2] - t) <= STL_BOUNDS_TOL_MM
        )
        mesh_ok = bool(mesh.is_watertight) and mesh.volume > 0 and bounds_ok
        mesh_detail = (f"watertight={mesh.is_watertight}, volume {mesh.volume:.2f} mm3, "
                       f"extent {ext[0]:.3f} x {ext[1]:.3f} x {ext[2]:.3f} mm, {len(mesh.faces)} faces")
        if missing_stl_path is not None:
            seg_mesh = trimesh.load(str(missing_stl_path), force="mesh")
            seg_ok = bool(seg_mesh.is_watertight) and seg_mesh.volume > 0
            mesh_ok = mesh_ok and seg_ok
            mesh_detail += f"; missing segment watertight={seg_mesh.is_watertight}, volume {seg_mesh.volume:.2f} mm3"
    except Exception as exc:  # noqa: BLE001
        mesh_ok, mesh_detail = False, f"STL load failed: {exc}"
    checks.append(CadCheck(name="STL_MESH", passed=mesh_ok, detail=mesh_detail))

    failed = [c for c in checks if not c.passed]
    if failed:
        raise CadError("CAD checks failed: " + "; ".join(f"{c.name}: {c.detail}" for c in failed))

    limitations = [LIMIT_PHOTO, LIMIT_RECT]
    if groove is not None:
        limitations.append(LIMIT_GROOVE)
    if missing_stl_path is not None:
        limitations.append(LIMIT_MISSING)

    return RingOutput(step_path=step_path, stl_path=stl_path, missing_stl_path=missing_stl_path,
                      checks=checks, limitations=limitations)
