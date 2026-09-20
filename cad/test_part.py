"""A general part: the measured outline, pushed up by the measured thickness.

A ring is only one shape. This builder takes the outline the detector measured in
card-plane millimetres, cuts its holes, and extrudes it. Written before the code.

One thing is easy to get wrong and impossible to see on a ring: the card plane is
an image plane, so y grows downward, while CAD seen from +Z has y growing upward.
Without a flip the STEP is a mirror of the photo. test_an_l_shape_is_not_mirrored
is the test that catches it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cad.part import CadError, NeedsInput, generate_part

ROOT = Path(__file__).resolve().parents[1]
RECT = [(0.0, 0.0), (60.0, 0.0), (60.0, 40.0), (0.0, 40.0)]
SQUARE_HOLE = [(20.0, 10.0), (40.0, 10.0), (40.0, 30.0), (20.0, 30.0)]
# An L: a 60x40 body with the top-right 30x20 removed. In image mm, y grows down,
# so the missing corner is at large x and SMALL y.
L_SHAPE = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (60.0, 20.0), (60.0, 40.0), (0.0, 40.0)]


def _checks(out):
    return {c.name: c for c in out.checks}


def test_a_plain_rectangle_builds_and_passes_every_check(tmp_path):
    out = generate_part(RECT, [], 5.0, tmp_path, "rect")
    assert out.step_path.exists() and out.stl_path.exists()
    assert all(c.passed for c in out.checks), out.checks
    assert set(_checks(out)) == {"SOLID", "DIMENSIONS", "PROFILE", "STEP_REIMPORT", "STL_MESH"}
    assert "60.000 x 40.000 x 5.000" in _checks(out)["DIMENSIONS"].detail


def test_a_hole_is_cut_out_of_the_volume(tmp_path):
    solid = generate_part(RECT, [], 5.0, tmp_path, "solid")
    holed = generate_part(RECT, [SQUARE_HOLE], 5.0, tmp_path, "holed")
    assert all(c.passed for c in holed.checks), holed.checks
    # 60x40x5 = 12000 mm3, less 20x20x5 = 2000 mm3.
    assert _volume(solid) == pytest.approx(12000.0, rel=2e-3)
    assert _volume(holed) == pytest.approx(10000.0, rel=2e-3)


def _volume(out) -> float:
    import trimesh

    return float(trimesh.load(str(out.stl_path), force="mesh").volume)


def test_an_l_shape_is_not_mirrored(tmp_path):
    """The photo and the STEP must show the same part, not its mirror image.

    In the photo's millimetres the corner is missing at large x, small y. After the
    flip to CAD coordinates that corner is missing at large x, LARGE y. So the solid
    must contain (50, 5) and must not contain (50, 35).
    """
    import cadquery as cq

    out = generate_part(L_SHAPE, [], 5.0, tmp_path, "ell")
    shape = cq.importers.importStep(str(out.step_path)).solids().val()
    assert shape.isInside(cq.Vector(50.0, 5.0, 2.5)), "the arm of the L is on the wrong side"
    assert not shape.isInside(cq.Vector(50.0, 35.0, 2.5)), "the part is mirrored"


def test_an_outline_that_crosses_itself_is_refused(tmp_path):
    bowtie = [(0.0, 0.0), (60.0, 40.0), (60.0, 0.0), (0.0, 40.0)]
    with pytest.raises(CadError, match="crosses itself"):
        generate_part(bowtie, [], 5.0, tmp_path, "bowtie")


def test_a_hole_outside_the_outline_is_refused(tmp_path):
    outside = [(70.0, 10.0), (90.0, 10.0), (90.0, 30.0), (70.0, 30.0)]
    with pytest.raises(CadError, match="inside the part"):
        generate_part(RECT, [outside], 5.0, tmp_path, "outside")


def test_too_few_points_is_a_needs_input(tmp_path):
    with pytest.raises(NeedsInput, match="outline"):
        generate_part([(0.0, 0.0), (10.0, 0.0)], [], 5.0, tmp_path, "two")


def test_a_missing_thickness_is_a_needs_input(tmp_path):
    with pytest.raises(NeedsInput, match="thickness"):
        generate_part(RECT, [], None, tmp_path, "nothick")


@pytest.mark.parametrize("t", [0.0, -3.0, 500.0])
def test_an_impossible_thickness_is_refused(tmp_path, t):
    with pytest.raises(CadError, match="[Tt]hickness"):
        generate_part(RECT, [], t, tmp_path, "badthick")


def test_a_part_bigger_than_the_limit_is_refused(tmp_path):
    huge = [(0.0, 0.0), (400.0, 0.0), (400.0, 40.0), (0.0, 40.0)]
    with pytest.raises(CadError, match="mm or less"):
        generate_part(huge, [], 5.0, tmp_path, "huge")


def test_a_noisy_outline_still_passes_the_volume_check(tmp_path):
    """A real detector outline has hundreds of points with sub-millimetre wobble.

    The volume check must compare against the polygon that was really extruded, not
    against an ideal rectangle, or every real part fails PROFILE.
    """
    import numpy as np

    rng = np.random.default_rng(3)
    pts = []
    for x in np.linspace(0, 60, 60):
        pts.append((float(x), float(rng.normal(0, 0.05))))
    for y in np.linspace(0, 40, 40):
        pts.append((60.0 + float(rng.normal(0, 0.05)), float(y)))
    for x in np.linspace(60, 0, 60):
        pts.append((float(x), 40.0 + float(rng.normal(0, 0.05))))
    for y in np.linspace(40, 0, 40):
        pts.append((float(rng.normal(0, 0.05)), float(y)))
    out = generate_part(pts, [], 5.0, tmp_path, "noisy")
    assert all(c.passed for c in out.checks), out.checks


def test_the_summary_says_the_shape_came_from_one_photo(tmp_path):
    out = generate_part(RECT, [], 5.0, tmp_path, "limits")
    assert any("photo" in lim.lower() for lim in out.limitations)
    assert any("flat" in lim.lower() for lim in out.limitations)


def test_a_real_detected_outline_builds(tmp_path):
    """End to end: a sample photo, the general detector, then CAD."""
    import cv2

    p = ROOT / "sample-photos" / "IMG_9485.jpg"
    if not p.exists():
        pytest.skip("sample photo not present")
    from engine.detect_general import detect_part

    part = detect_part(cv2.imread(str(p)))
    if not part.outline_mm:
        pytest.skip("detector found nothing in this photo")
    out = generate_part(part.outline_mm, part.holes_mm, 6.0, tmp_path, "real")
    assert all(c.passed for c in out.checks), out.checks
