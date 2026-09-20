"""auto_detect is now the general detector: it must still serve the ring flow.

The app asks for card corners plus points on an outer and an inner edge. The
general detector gives an outline and its holes, so the points come from there.
A ring is only one case of that, and a cup or a stick must work as well.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from engine.detect_general import auto_detect
from engine.fit import decode_image, fit_ring

ROOT = Path(__file__).resolve().parents[1]
CARD = (85.6, 53.98)


def _photo(name):
    p = ROOT / "sample-photos" / f"{name}.jpg"
    if not p.exists():
        pytest.skip(f"{p.name} not present")
    return decode_image(p.read_bytes())


def test_ring_photo_still_gives_both_edges_and_a_sane_fit():
    img = _photo("20260919_173227")
    out = auto_detect(img)
    assert out.corners_px is not None
    assert len(out.outer_edge_points_px) >= 8
    assert len(out.inner_edge_points_px) >= 8, out.warnings
    f = fit_ring(img, out.corners_px, CARD, out.outer_edge_points_px, out.inner_edge_points_px).fit
    # The old ring-only detector measured 41.3 mm on this photo. The outline of the
    # general detector sits on the outer wall, so a bigger error is expected here.
    assert f.outer_diameter_mm == pytest.approx(41.3, abs=2.0)
    assert 0.3 < f.inner_diameter_mm / f.outer_diameter_mm < 0.95


def test_broken_ring_photo_gives_points():
    img = _photo("IMG_9475")
    out = auto_detect(img)
    assert out.corners_px is not None
    assert len(out.outer_edge_points_px) >= 8


def test_a_cup_gives_an_outer_edge_and_no_inner_edge():
    out = auto_detect(_photo("IMG_9486"))
    assert out.corners_px is not None
    assert len(out.outer_edge_points_px) >= 8
    assert out.inner_edge_points_px == []
    assert out.confidence in ("HIGH", "LOW")


def test_a_wooden_stick_gives_points_too():
    out = auto_detect(_photo("IMG_9485"))
    assert len(out.outer_edge_points_px) >= 8
    assert out.inner_edge_points_px == []


def test_points_are_inside_the_photo():
    img = _photo("20260919_173227")
    out = auto_detect(img)
    h, w = img.shape[:2]
    for x, y in out.outer_edge_points_px + out.inner_edge_points_px:
        assert 0 <= x <= w and 0 <= y <= h


def test_blank_image_finds_nothing_and_says_so():
    out = auto_detect(np.full((1500, 1000, 3), 220, np.uint8))
    assert out.corners_px is None
    assert out.outer_edge_points_px == [] and out.inner_edge_points_px == []
    assert out.confidence == "NONE" and out.warnings


def test_broken_bytes_do_not_raise():
    out = auto_detect(np.zeros((0, 0, 3), np.uint8))
    assert out.confidence == "NONE"


def test_a_broken_ring_has_no_hole_so_the_operator_clicks_the_inner_edge():
    """A broken ring's inner edge is part of the same outline, not a hole.

    We do not guess which half of the outline is "inner": that would be a rule
    about rings, and this detector is not about rings. It says so instead.
    """
    import cv2

    img = np.full((3000, 2000, 3), (190, 215, 225), np.uint8)
    cv2.fillPoly(img, [np.array([[500, 300], [1040, 300], [1040, 1156], [500, 1156]], np.int32)], (200, 120, 90))
    cv2.ellipse(img, (1000, 2000), (150, 150), 0, 60, 300, (40, 220, 245), -1)
    cv2.ellipse(img, (1000, 2000), (110, 110), 0, 0, 360, (190, 215, 225), -1)
    out = auto_detect(img)
    assert len(out.outer_edge_points_px) >= 8
    assert out.inner_edge_points_px == []
    assert any("inner edge" in w for w in out.warnings)


def test_a_complete_ring_uses_its_hole_as_the_inner_edge():
    import cv2

    img = np.full((3000, 2000, 3), (190, 215, 225), np.uint8)
    cv2.fillPoly(img, [np.array([[500, 300], [1040, 300], [1040, 1156], [500, 1156]], np.int32)], (200, 120, 90))
    cv2.circle(img, (1000, 2000), 150, (40, 220, 245), -1)
    cv2.circle(img, (1000, 2000), 110, (190, 215, 225), -1)
    out = auto_detect(img)
    for pts, r in ((out.outer_edge_points_px, 150), (out.inner_edge_points_px, 110)):
        assert len(pts) >= 8
        d = np.hypot(*(np.array(pts) - (1000, 2000)).T)
        assert np.all(np.abs(d - r) < 5), (r, d)
