"""Hard but general scenes for detect_part: texture, hard shadow, dark parts, low light.

Written before the code that passes them. None of these scenes is a copy of one
photo: they are the conditions that break a background model in general.

Each scene is drawn top-down in millimetres and then warped with a perspective
homography, so the true size of the part is known and the check is a real one.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from engine.detect_general import detect_part

CARD = (85.6, 53.98)
PX_PER_MM = 6
PLANE_MM = (220, 300)
QUAD = ((300, 200), (1700, 260), (1900, 2900), (100, 2800))
SIZE = (2000, 3000)


def _wood(shape) -> np.ndarray:
    """A warm table with strong grain, like oak. The grain is the trap: it is texture, not a part."""
    h, w = shape
    y, x = np.mgrid[:h, :w].astype(np.float32)
    grain = (
        22 * np.sin(x / 9.0 + 2.0 * np.sin(y / 260.0))
        + 14 * np.sin(x / 3.1 + 1.3)
        + 9 * np.sin(x / 41.0 + y / 700.0)
    )
    base = np.stack([58 + 0.35 * grain, 104 + 0.75 * grain, 156 + grain], -1)  # BGR, warm
    return np.clip(base, 0, 255).astype(np.uint8)


def _lamp(img: np.ndarray, centre, strength=0.55) -> np.ndarray:
    """One warm lamp: bright near the centre, much darker in the corners."""
    h, w = img.shape[:2]
    y, x = np.mgrid[:h, :w].astype(np.float32)
    d = np.hypot(x - centre[0] * PX_PER_MM, y - centre[1] * PX_PER_MM) / (0.7 * max(h, w))
    gain = (1.0 - strength * np.clip(d, 0, 1.4)).astype(np.float32)
    return np.clip(img.astype(np.float32) * gain[:, :, None], 0, 255).astype(np.uint8)


def _cast_shadow(img: np.ndarray, poly_mm, hard=True) -> np.ndarray:
    """A cast shadow: much darker, and bluer, because the light that fills it is cooler.

    This is what a real hard shadow does, and it is why "the table with less light"
    is the wrong model: the channels do NOT scale by the same factor.
    """
    mask = np.zeros(img.shape[:2], np.float32)
    cv2.fillPoly(mask, [np.round(np.array(poly_mm) * PX_PER_MM).astype(np.int32)], 1.0)
    mask = cv2.GaussianBlur(mask, (9, 9) if hard else (61, 61), 0)
    scale = np.array([0.62, 0.34, 0.24], np.float32)  # B, G, R: blue survives best
    out = img.astype(np.float32)
    return np.clip(out * (1 - mask[:, :, None]) + out * scale * mask[:, :, None], 0, 255).astype(np.uint8)


def _plane(card=True) -> np.ndarray:
    W, H = PLANE_MM
    plane = _wood((H * PX_PER_MM, W * PX_PER_MM))
    if card:
        c = np.array([[25, 25], [25 + CARD[0], 25], [25 + CARD[0], 25 + CARD[1]], [25, 25 + CARD[1]]])
        cv2.fillPoly(plane, [np.round(c * PX_PER_MM).astype(np.int32)], (200, 120, 90), cv2.LINE_AA)
    return plane


def _warp(plane) -> np.ndarray:
    W, H = PLANE_MM
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
    Hmm = cv2.getPerspectiveTransform(src, np.array(QUAD, np.float32))
    img = cv2.warpPerspective(plane, Hmm @ np.diag([1 / PX_PER_MM, 1 / PX_PER_MM, 1]), SIZE,
                              flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    rng = np.random.default_rng(1)
    return np.clip(img.astype(np.int16) + rng.normal(0, 3, img.shape).astype(np.int16), 0, 255).astype(np.uint8)


def _box(plane, centre, w_mm, h_mm, colour):
    p0 = (round((centre[0] - w_mm / 2) * PX_PER_MM), round((centre[1] - h_mm / 2) * PX_PER_MM))
    p1 = (round((centre[0] + w_mm / 2) * PX_PER_MM), round((centre[1] + h_mm / 2) * PX_PER_MM))
    cv2.rectangle(plane, p0, p1, colour, -1, cv2.LINE_AA)


PART = (110, 190)  # centre of the part, in mm on the table
CREAM = (205, 215, 220)
DARK = (45, 45, 50)


def test_part_on_a_wooden_table_is_measured():
    plane = _plane()
    _box(plane, PART, 60, 40, CREAM)
    out = detect_part(_warp(plane))
    assert out.length_mm is not None, out.warnings
    assert out.length_mm == pytest.approx(60, abs=3.0)
    assert out.width_mm == pytest.approx(40, abs=3.0)


def test_hard_cast_shadow_is_not_part_of_the_object():
    """The shadow is 45 mm long. If it is taken for the part, the length jumps to ~100 mm."""
    plane = _plane()
    x, y = PART
    _box(plane, PART, 60, 40, CREAM)
    plane = _cast_shadow(plane, [(x - 75, y - 20), (x - 30, y - 20), (x - 30, y + 20), (x - 75, y + 20)])
    out = detect_part(_warp(plane))
    assert out.length_mm is not None, out.warnings
    assert out.length_mm == pytest.approx(60, abs=4.0)


def test_soft_shadow_under_a_part_is_not_part_of_the_object():
    plane = _plane()
    x, y = PART
    _box(plane, PART, 60, 40, CREAM)
    plane = _cast_shadow(plane, [(x - 40, y + 12), (x + 40, y + 12), (x + 40, y + 34), (x - 40, y + 34)], hard=False)
    out = detect_part(_warp(plane))
    assert out.length_mm is not None, out.warnings
    assert out.width_mm == pytest.approx(40, abs=5.0)


def test_a_dark_part_is_not_thrown_away_as_a_shadow():
    plane = _plane()
    _box(plane, PART, 60, 40, DARK)
    out = detect_part(_warp(plane))
    assert out.length_mm is not None, out.warnings
    assert out.length_mm == pytest.approx(60, abs=3.0)


def test_low_warm_light_still_finds_the_part():
    plane = _plane()
    _box(plane, PART, 60, 40, CREAM)
    out = detect_part(_warp(_lamp(plane, (60, 60))))
    assert out.length_mm is not None, out.warnings
    assert out.length_mm == pytest.approx(60, abs=4.0)


def test_part_is_found_in_pixels_even_without_a_card():
    """No card means no millimetres. It must still show WHERE the part is."""
    plane = _plane(card=False)
    _box(plane, PART, 60, 40, CREAM)
    out = detect_part(_warp(plane))
    assert out.length_mm is None and out.outline_mm == []
    assert len(out.outline_px) >= 8
    assert any("card" in w.lower() for w in out.warnings)


def test_two_parts_are_both_reported():
    """The two pieces of a broken part lie near each other, next to the card."""
    plane = _plane()
    _box(plane, PART, 60, 40, CREAM)
    _box(plane, (PART[0] - 25, PART[1] + 45), 40, 25, CREAM)
    out = detect_part(_warp(plane))
    assert out.length_mm == pytest.approx(60, abs=3.0), out.warnings
    assert any("2 parts" in w for w in out.warnings)


def test_a_dark_area_far_from_the_card_is_not_the_part():
    """A photo often catches the floor past the table edge: big, dark, and far away.

    The engineer is told to put the card next to the part, so what is far from the
    card is not the part, however big it is.
    """
    plane = _plane()
    _box(plane, PART, 60, 40, CREAM)
    W, H = PLANE_MM
    # Inset on every side, so the "it touches the photo edge" rule does not save us.
    cv2.rectangle(plane, (round(0.10 * W * PX_PER_MM), round(0.72 * H * PX_PER_MM)),
                  (round(0.90 * W * PX_PER_MM), round(0.90 * H * PX_PER_MM)), (18, 16, 15), -1)
    out = detect_part(_warp(plane))
    assert out.length_mm == pytest.approx(60, abs=4.0), out.warnings


def test_a_bright_streak_along_a_table_edge_is_not_the_part():
    """A photo often catches the lit edge of the table: a long curved streak.

    It is bright, it is big, and it is close to the card. What it is not is a
    shape: it does not fill its own box, the way a real part does.
    """
    plane = _plane()
    _box(plane, PART, 60, 40, CREAM)
    pts = np.array([[(30 + 8 * np.sin(t / 30.0), t) for t in range(20, 290, 4)]], np.float32)
    cv2.polylines(plane, [np.round(pts * PX_PER_MM).astype(np.int32)], False, (225, 232, 238), 9, cv2.LINE_AA)
    out = detect_part(_warp(plane))
    assert out.length_mm == pytest.approx(60, abs=4.0), out.warnings


def test_every_candidate_is_returned_so_the_operator_can_choose():
    """When two things could be the part, the app must be able to offer both."""
    plane = _plane()
    _box(plane, PART, 60, 40, CREAM)
    _box(plane, (PART[0] - 25, PART[1] + 45), 40, 25, CREAM)
    out = detect_part(_warp(plane))
    assert len(out.candidates_px) == 2
    assert all(len(c) >= 8 for c in out.candidates_px)
    assert out.candidates_px[0] == out.outline_px  # the one it picked comes first
