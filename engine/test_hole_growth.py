"""A hole seen at an angle looks smaller than it is. The detector must correct that.

Why: looking into a through hole from the side, the far wall hides part of the
opening. What the camera sees is the floor through the hole, which is smaller
than the opening and pushed to one side. The real edge is the top edge of the
wall, a little further out. This is true for any part with a through hole, not
only for a ring.

The scenes below are drawn top-down in millimetres, with the wall drawn where a
real camera would see it, and then warped. The true opening is known.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from engine.detect_general import detect_part
from engine.fit import decode_image

ROOT = Path(__file__).resolve().parents[1]
PX_PER_MM = 8
PLANE_MM = (200, 300)
TABLE = (190, 215, 225)
BLUE = (200, 120, 90)
TOP = (40, 220, 245)
WALL = (20, 160, 195)
CARD = (85.6, 53.98)
QUAD = ((300, 200), (1700, 260), (1900, 2900), (100, 2800))


def _disk(shape, c, r):
    m = np.zeros(shape, np.uint8)
    cv2.circle(m, (round(c[0] * PX_PER_MM), round(c[1] * PX_PER_MM)), round(r * PX_PER_MM), 255, -1, cv2.LINE_AA)
    return m > 127


def _scene(centre=(70, 180), od=42.0, idm=30.0, shift=(0.0, 4.0), wall=WALL, floor=TABLE):
    """A part with a through hole. `shift` is how far the bottom sits from the top face."""
    W, H = PLANE_MM
    plane = np.full((H * PX_PER_MM, W * PX_PER_MM, 3), TABLE, np.uint8)
    card = np.array([[20, 20], [20 + CARD[0], 20], [20 + CARD[0], 20 + CARD[1]], [20, 20 + CARD[1]]])
    cv2.fillPoly(plane, [np.round(card * PX_PER_MM).astype(np.int32)], BLUE, cv2.LINE_AA)
    shape = plane.shape[:2]
    b = (centre[0] + shift[0], centre[1] + shift[1])
    top_o, top_i = _disk(shape, centre, od / 2), _disk(shape, centre, idm / 2)
    bot_o, bot_i = _disk(shape, b, od / 2), _disk(shape, b, idm / 2)
    plane[top_o | bot_o] = wall
    plane[top_o & ~top_i] = TOP
    plane[top_i] = wall  # the inner wall, seen through the opening
    plane[top_i & bot_i] = floor  # and the floor, seen through both circles
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
    Hmm = cv2.getPerspectiveTransform(src, np.array(QUAD, np.float32))
    img = cv2.warpPerspective(plane, Hmm @ np.diag([1 / PX_PER_MM, 1 / PX_PER_MM, 1]), (2000, 3000),
                              flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    rng = np.random.default_rng(0)
    return np.clip(img.astype(np.int16) + rng.normal(0, 3, img.shape).astype(np.int16), 0, 255).astype(np.uint8)


def _hole_size(out):
    assert out.holes_mm, out.warnings
    biggest = max(out.holes_mm, key=len)
    (_, _), (a, b), _ = cv2.minAreaRect(np.array(biggest, np.float32))
    return max(a, b), min(a, b)


def test_the_opening_is_measured_not_the_floor_patch():
    """Without the correction the visible floor patch reads about 26 mm, not 30."""
    out = detect_part(_scene(idm=30.0, shift=(0.0, 4.0)))
    long_mm, short_mm = _hole_size(out)
    assert long_mm == pytest.approx(30.0, abs=2.0), out.warnings
    assert short_mm == pytest.approx(30.0, abs=2.0)


def test_a_straight_down_photo_is_left_alone():
    """No angle, no parallax: the hole is already right and must not grow."""
    out = detect_part(_scene(idm=30.0, shift=(0.0, 0.0)))
    long_mm, _ = _hole_size(out)
    assert long_mm == pytest.approx(30.0, abs=1.5), out.warnings


def test_a_small_hole_stays_small():
    out = detect_part(_scene(od=42.0, idm=14.0, shift=(0.0, 2.0)))
    long_mm, _ = _hole_size(out)
    assert long_mm == pytest.approx(14.0, abs=2.0), out.warnings


def test_a_dark_bore_does_not_run_away():
    """A deep hole with no floor in sight: the correction must stay bounded."""
    out = detect_part(_scene(idm=30.0, shift=(0.0, 4.0), floor=(30, 30, 30)))
    if out.holes_mm:
        long_mm, _ = _hole_size(out)
        assert long_mm < 36.0, out.warnings


def test_the_outer_edge_is_not_changed():
    """The outer side has its own parallax: the silhouette of a part with height
    includes the outer wall, so 42 mm of top face reads about 47 mm here. This test
    only guards that the hole correction does not touch the outer edge."""
    before = detect_part(_scene(idm=30.0, shift=(0.0, 4.0)))
    assert 42.0 <= before.length_mm <= 48.0, (before.length_mm, before.warnings)


def test_real_ring_photo_inner_diameter():
    """20260919_173227: the ring fit from clicked points says about 29.5 mm."""
    p = ROOT / "sample-photos" / "20260919_173227.jpg"
    if not p.exists():
        pytest.skip("sample photo not present")
    out = detect_part(decode_image(p.read_bytes()))
    long_mm, short_mm = _hole_size(out)
    assert long_mm == pytest.approx(29.5, abs=3.0)  # was 19.4 mm before this step
    # Not a perfect circle: the top face of the ring sits above the card plane, so
    # projecting it into that plane squashes it a little. That error is not this
    # step's to fix; it is the known scale limit of a one-photo method.
    assert short_mm / long_mm > 0.82
