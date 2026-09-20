"""detect_part: any shape, not only rings.

The synthetic scene is drawn top-down in mm and warped with a perspective
homography, so the true millimetre sizes are known. The real photos have no
measured truth except the yellow ring, whose outer diameter is 41.3 mm from
the ring fit, so that photo is the accuracy check.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from engine.detect_general import detect_part
from engine.fit import decode_image

ROOT = Path(__file__).resolve().parents[1]
CARD = (85.6, 53.98)
PX_PER_MM = 8
PLANE_MM = (200, 300)
TABLE = (190, 215, 225)
BLUE = (200, 120, 90)


def _scene(draw, quad=((300, 200), (1700, 260), (1900, 2900), (100, 2800)), size=(2000, 3000), card=True):
    W, H = PLANE_MM
    plane = np.full((H * PX_PER_MM, W * PX_PER_MM, 3), TABLE, np.uint8)
    if card:
        card_mm = np.array([[20, 20], [20 + CARD[0], 20], [20 + CARD[0], 20 + CARD[1]], [20, 20 + CARD[1]]])
        cv2.fillPoly(plane, [np.round(card_mm * PX_PER_MM).astype(np.int32)], BLUE, cv2.LINE_AA)
    draw(plane)
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
    Hmm = cv2.getPerspectiveTransform(src, np.array(quad, np.float32))
    img = cv2.warpPerspective(plane, Hmm @ np.diag([1 / PX_PER_MM, 1 / PX_PER_MM, 1]), size,
                              flags=cv2.INTER_AREA, borderValue=TABLE)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    rng = np.random.default_rng(0)
    return np.clip(img.astype(np.int16) + rng.normal(0, 3, img.shape).astype(np.int16), 0, 255).astype(np.uint8)


def _rect(c, w, h, colour=(70, 90, 110)):
    def draw(plane):
        p0 = (round((c[0] - w / 2) * PX_PER_MM), round((c[1] - h / 2) * PX_PER_MM))
        p1 = (round((c[0] + w / 2) * PX_PER_MM), round((c[1] + h / 2) * PX_PER_MM))
        cv2.rectangle(plane, p0, p1, colour, -1, cv2.LINE_AA)
    return draw


def test_rectangular_bracket_is_measured():
    img = _scene(_rect((70, 180), 60, 25))
    out = detect_part(img)
    assert out.confidence == "HIGH", out.warnings
    assert out.length_mm == pytest.approx(60, abs=1.5)
    assert out.width_mm == pytest.approx(25, abs=1.5)


def test_long_thin_stick_is_not_called_a_side_view():
    img = _scene(_rect((70, 180), 100, 8, colour=(150, 190, 215)))
    out = detect_part(img)
    assert out.length_mm == pytest.approx(100, abs=2.0), out.warnings
    assert out.width_mm == pytest.approx(8, abs=1.5)
    assert not any("side" in w for w in out.warnings)


def test_holes_are_found():
    def draw(plane):
        _rect((70, 180), 60, 25)(plane)
        for dx in (-18, 18):
            cv2.circle(plane, (round((70 + dx) * PX_PER_MM), round(180 * PX_PER_MM)), round(5 * PX_PER_MM), TABLE, -1, cv2.LINE_AA)
    out = detect_part(_scene(draw))
    assert len(out.holes_mm) == 2, out.warnings


def test_no_card_gives_shape_but_no_millimetres():
    out = detect_part(_scene(_rect((70, 180), 60, 25), card=False))
    assert out.length_mm is None and out.outline_mm == []
    assert any("card" in w.lower() for w in out.warnings)


def test_bad_image_does_not_raise():
    assert detect_part(np.zeros((0, 0, 3), np.uint8)).confidence == "NONE"


# ---- real photos (sample-photos/ is gitignored; skip when missing)


def _photo(name):
    p = ROOT / "sample-photos" / f"{name}.jpg"
    if not p.exists():
        pytest.skip(f"{p.name} not present")
    return decode_image(p.read_bytes())


def test_real_ring_photo_matches_the_ring_fit():
    """Accuracy check: the ring fit says outer diameter 41.3 mm on this photo."""
    out = detect_part(_photo("20260919_173227"))
    # LOW, not HIGH: shadows on this table make extra blobs, so the operator must check.
    # The measurement is still right, and that is what this test guards.
    assert out.confidence in ("HIGH", "LOW"), out.warnings
    assert out.length_mm == pytest.approx(41.3, abs=1.5)
    assert out.width_mm == pytest.approx(41.3, abs=1.5)
    assert len(out.holes_mm) == 1  # the bore


def test_real_wooden_stick_photo():
    """IMG_9485: a broken stirrer stick. No measured truth, so only the shape is checked."""
    out = detect_part(_photo("IMG_9485"))
    assert out.confidence == "HIGH", out.warnings
    assert 40 < out.length_mm < 130  # a stirrer stick, broken: plausible, not verified
    assert 3 < out.width_mm < 10
    assert not any("side" in w for w in out.warnings)
