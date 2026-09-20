"""Tests for the ring CAD template. All values are SYNTHETIC test values, not measurements."""
from __future__ import annotations

import math

import pytest
import trimesh

from api.schemas import Dimension, GenerateRequest, Groove
from cad.ring import CadError, NeedsInput, generate_ring, validate_request

# SYNTHETIC values (not from any photo or real ring).
SYN_OUTER, SYN_INNER, SYN_T = 40.0, 30.0, 6.0
SYN_GROOVE = Groove(depth_mm=1.0, width_mm=2.0)
SYN_MISSING = (200.0, 340.0)


def _dim(v, confirmed=True):
    return Dimension(value_mm=v, source="MANUAL_MEASUREMENT" if v is not None else None, confirmed=confirmed)


def synthetic_request(**over) -> GenerateRequest:
    base = dict(
        outer_diameter=_dim(SYN_OUTER),
        inner_diameter=_dim(SYN_INNER),
        thickness=_dim(SYN_T),
        groove=SYN_GROOVE,
        profile_rz_mm=None,
        profile_basis="SIMPLIFIED_RECTANGLE",
        profile_confirmed=True,
        missing_arc_deg=SYN_MISSING,
        purpose="DEMO_CAD_ONLY",
    )
    base.update(over)
    return GenerateRequest(**base)


def test_happy_path_synthetic(tmp_path):
    out = generate_ring(synthetic_request(), tmp_path, "syn1")
    assert [c.name for c in out.checks] == ["SOLID", "DIMENSIONS", "PROFILE", "STEP_REIMPORT", "STL_MESH"]
    assert all(c.passed for c in out.checks), out.checks
    for p in (out.step_path, out.stl_path, out.missing_stl_path):
        assert p is not None and p.exists() and p.stat().st_size > 0
    assert out.step_path.name == "syn1.step"
    assert out.stl_path.name == "syn1.stl"
    assert out.missing_stl_path.name == "syn1-missing.stl"
    assert "Photo-derived dimensions are estimates; no physical fit verified." in out.limitations
    assert any("groove" in s.lower() for s in out.limitations)
    assert any("full circle" in s for s in out.limitations)


def test_missing_segment_angular_position(tmp_path):
    out = generate_ring(synthetic_request(groove=None), tmp_path, "syn2")
    mesh = trimesh.load(str(out.missing_stl_path), force="mesh")
    assert mesh.is_watertight
    # Mid-angle of (200, 340) is 270 deg = -Y direction.
    c = mesh.center_mass
    ang = math.degrees(math.atan2(c[1], c[0])) % 360
    assert abs(ang - 270.0) < 0.5
    # All vertices lie inside the arc (small tolerance for rounding).
    angs = [math.degrees(math.atan2(v[1], v[0])) % 360 for v in mesh.vertices]
    assert min(angs) > 199.9 and max(angs) < 340.1
    # Volume is span/360 of the full ring.
    full = math.pi * ((SYN_OUTER / 2) ** 2 - (SYN_INNER / 2) ** 2) * SYN_T
    assert abs(mesh.volume - full * 140 / 360) / (full * 140 / 360) < 0.01


def test_missing_segment_wraps_zero(tmp_path):
    out = generate_ring(synthetic_request(groove=None, missing_arc_deg=(330.0, 30.0)), tmp_path, "syn3")
    c = trimesh.load(str(out.missing_stl_path), force="mesh").center_mass
    ang = math.degrees(math.atan2(c[1], c[0]))
    assert abs(ang) < 0.5 and c[0] > 0


def test_unconfirmed_dimension_needs_input():
    with pytest.raises(NeedsInput, match="thickness"):
        validate_request(synthetic_request(thickness=_dim(SYN_T, confirmed=False)))


def test_none_value_needs_input():
    with pytest.raises(NeedsInput, match="outer_diameter"):
        validate_request(synthetic_request(outer_diameter=_dim(None, confirmed=True)))


def test_profile_not_confirmed_needs_input():
    with pytest.raises(NeedsInput, match="profile"):
        validate_request(synthetic_request(profile_confirmed=False))


def test_outer_not_greater_than_inner():
    with pytest.raises(CadError):
        validate_request(synthetic_request(outer_diameter=_dim(30.0)))


def test_groove_too_deep():
    with pytest.raises(CadError, match="too deep"):
        validate_request(synthetic_request(groove=Groove(depth_mm=4.5, width_mm=2.0)))


def test_custom_profile_rejected():
    with pytest.raises(CadError, match="not supported"):
        validate_request(synthetic_request(profile_rz_mm=[(15.0, 0.0), (20.0, 0.0), (20.0, 6.0)]))


def test_no_missing_arc(tmp_path):
    out = generate_ring(synthetic_request(missing_arc_deg=None, groove=None), tmp_path, "syn4")
    assert out.missing_stl_path is None
    assert not (tmp_path / "syn4-missing.stl").exists()
    assert all(c.passed for c in out.checks)
    assert not any("groove" in s.lower() for s in out.limitations)
