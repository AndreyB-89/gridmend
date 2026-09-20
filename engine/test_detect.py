"""auto_detect on photos taken at an angle, several rings, and bad photos.

The synthetic scenes are drawn top-down in mm, with the parallax a real camera
sees (the bottom of the ring is shifted from the top face), and then warped
with a perspective homography. The true top-face circles are known, so we can
check that the automatic points sit on the top face and not on the wall foot.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from engine.fit import auto_detect, decode_image, fit_ring

ROOT = Path(__file__).resolve().parents[1]
CARD = (85.6, 53.98)
PX_PER_MM = 8
PLANE_MM = (200, 300)
TABLE = (190, 215, 225)
BLUE = (200, 120, 90)
TOP = (40, 220, 245)
WALL = (20, 160, 195)


def _disk(shape, c, r):
    m = np.zeros(shape, np.uint8)
    cv2.circle(m, (round(c[0] * PX_PER_MM), round(c[1] * PX_PER_MM)), round(r * PX_PER_MM), 255, -1, cv2.LINE_AA)
    return m > 127


def _draw_ring(plane, c, od, idm, shift=(0.0, 3.0), missing=None, wall=WALL):
    """Top face at centre c; the bottom (wall foot) is shifted by `shift` mm (parallax)."""
    shape = plane.shape[:2]
    b = (c[0] + shift[0], c[1] + shift[1])
    top_o, top_i = _disk(shape, c, od / 2), _disk(shape, c, idm / 2)
    bot_o, bot_i = _disk(shape, b, od / 2), _disk(shape, b, idm / 2)
    region = top_o | bot_o
    if missing is not None:  # remove a sector (degrees, CCW, 0 = +x, y down)
        yy, xx = np.mgrid[: shape[0], : shape[1]] / PX_PER_MM
        ang = np.mod(np.degrees(np.arctan2(-(yy - c[1]), xx - c[0])), 360)
        a0, a1 = missing
        gone = np.mod(ang - a0, 360) < np.mod(a1 - a0, 360)
    else:
        gone = np.zeros(shape, bool)
    keep = ~gone
    plane[region & keep] = wall  # outer wall (seen on the near side)
    plane[top_o & ~top_i & keep] = TOP  # top face
    plane[top_i & keep] = wall  # inner wall seen through the bore
    plane[top_i & bot_i & keep] = TABLE  # the floor seen through the bore


def _scene(rings, quad=((300, 200), (1700, 260), (1900, 2900), (100, 2800)), size=(2000, 3000), seed=0):
    """rings: list of dicts for _draw_ring. Returns (image, card corners px, H mm->px)."""
    W, H = PLANE_MM
    plane = np.full((H * PX_PER_MM, W * PX_PER_MM, 3), TABLE, np.uint8)
    card_mm = np.array([[20, 20], [20 + CARD[0], 20], [20 + CARD[0], 20 + CARD[1]], [20, 20 + CARD[1]]], np.float64)
    cv2.fillPoly(plane, [np.round(card_mm * PX_PER_MM).astype(np.int32)], BLUE, cv2.LINE_AA)
    for r in rings:
        _draw_ring(plane, **r)
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
    Hmm = cv2.getPerspectiveTransform(src, np.array(quad, np.float32))
    Hpx = Hmm @ np.diag([1 / PX_PER_MM, 1 / PX_PER_MM, 1])
    img = cv2.warpPerspective(plane, Hpx, size, flags=cv2.INTER_AREA, borderValue=TABLE)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    rng = np.random.default_rng(seed)
    img = np.clip(img.astype(np.int16) + rng.normal(0, 3, img.shape).astype(np.int16), 0, 255).astype(np.uint8)
    corners = cv2.perspectiveTransform(card_mm.reshape(-1, 1, 2).astype(np.float32), Hmm).reshape(-1, 2)
    return img, corners, Hmm


def _fit(img, out):
    return fit_ring(img, out.corners_px, CARD, out.outer_edge_points_px, out.inner_edge_points_px).fit


@pytest.mark.parametrize("missing", [None, (200.0, 330.0)])
def test_tilted_ring_points_on_top_face(missing):
    img, corners, _ = _scene([dict(c=(70, 180), od=42, idm=30, missing=missing)])
    out = auto_detect(img)
    assert out.confidence == "HIGH", out.warnings
    assert np.allclose(out.corners_px, corners, atol=6)
    f = _fit(img, out)
    # The colour outline alone gives the wall foot: ID about 27 mm here. The top face is 42 / 30.
    assert f.outer_diameter_mm == pytest.approx(42, abs=0.6)
    assert f.inner_diameter_mm == pytest.approx(30, abs=0.6)


def test_stepped_top_face_picks_the_bore():
    # A ring with a raised inner step: the step line is concentric too, but the bore is the inner edge.
    img2, _, Hmm = _scene([dict(c=(70, 180), od=42, idm=24)])
    # Draw the step line (a thin darker circle at d=34 mm) on the top face.
    t = np.radians(np.arange(0, 360, 0.5))
    ring = np.column_stack([70 + 17 * np.cos(t), 180 + 17 * np.sin(t)]).astype(np.float32).reshape(-1, 1, 2)
    px = cv2.perspectiveTransform(ring, Hmm).reshape(-1, 2)
    cv2.polylines(img2, [np.round(px).astype(np.int32)], True, (30, 190, 215), 3, cv2.LINE_AA)
    out = auto_detect(img2)
    f = _fit(img2, out)
    assert f.inner_diameter_mm == pytest.approx(24, abs=0.8)


def test_several_rings_picks_the_broken_one():
    rings = [
        dict(c=(60, 150), od=42, idm=30),
        dict(c=(101, 152), od=40, idm=28),  # touches the first one
        dict(c=(80, 240), od=42, idm=30, missing=(200.0, 330.0)),
    ]
    img, _, Hmm = _scene(rings)
    out = auto_detect(img)
    assert out.confidence == "HIGH", out.warnings
    f = _fit(img, out)
    assert f.outer_diameter_mm == pytest.approx(42, abs=0.8)
    assert f.support_deg < 300  # it picked the broken ring
    assert any("3 rings" in w for w in out.warnings)


def test_touching_complete_rings_are_split():
    rings = [dict(c=(60, 150), od=42, idm=30), dict(c=(101, 152), od=40, idm=28)]
    img, _, _ = _scene(rings)
    out = auto_detect(img)
    assert out.confidence == "HIGH", out.warnings
    f = _fit(img, out)
    assert f.outer_diameter_mm == pytest.approx(42, abs=0.8) or f.outer_diameter_mm == pytest.approx(40, abs=0.8)
    assert any("2 rings" in w for w in out.warnings)


def test_no_inner_edge_gives_outer_only():
    # A disc-like part: the hole is too small to be an inner edge.
    img, _, _ = _scene([dict(c=(70, 180), od=42, idm=6)])
    out = auto_detect(img)
    assert len(out.outer_edge_points_px) >= 8
    assert out.inner_edge_points_px == []
    assert out.confidence == "LOW"
    assert any("inner edge" in w for w in out.warnings)


def test_side_view_says_take_it_from_above():
    # Very flat view: the ring looks 3-4 times wider than tall.
    quad = ((0, 1500), (2000, 1500), (2600, 2200), (-600, 2200))
    img, _, _ = _scene([dict(c=(70, 180), od=42, idm=30)], quad=quad)
    out = auto_detect(img)
    assert out.outer_edge_points_px == [] and out.confidence != "HIGH"
    assert any("from above" in w for w in out.warnings)


def test_ring_cut_by_photo_edge_says_so():
    img, _, _ = _scene([dict(c=(70, 180), od=42, idm=30)])
    x = int(np.nonzero((img[:, :, 0] < 100).any(0))[0].min())  # left end of the ring
    out = auto_detect(np.ascontiguousarray(img[:, x + 60 :]))
    assert out.outer_edge_points_px == []
    assert any("whole ring" in w for w in out.warnings)


def test_no_card_says_how_to_fix():
    img = np.full((2000, 1500, 3), TABLE, np.uint8)
    cv2.circle(img, (700, 1000), 200, TOP, -1)
    cv2.circle(img, (700, 1000), 140, TABLE, -1)
    out = auto_detect(img)
    assert out.corners_px is None and len(out.inner_edge_points_px) >= 8
    assert any("card" in w.lower() and "flat" in w for w in out.warnings)


# ---- real photos (sample-photos/ is gitignored; skip when missing)

TOP_VIEW = ["20260919_170239", "20260919_171608", "20260919_171736", "20260919_173227", "20260919_180605", "IMG_9475"]
SIDE_OR_HAND = ["20260919_173239", "20260919_173254", "20260919_180631", "20260919_181651"]


def _photo(name):
    p = ROOT / "sample-photos" / f"{name}.jpg"
    if not p.exists():
        pytest.skip(f"{p.name} not present")
    return decode_image(p.read_bytes())


@pytest.mark.parametrize("name", TOP_VIEW)
def test_real_top_view_photos_find_the_ring(name):
    img = _photo(name)
    out = auto_detect(img)
    assert out.corners_px is not None
    assert len(out.outer_edge_points_px) >= 8 and len(out.inner_edge_points_px) >= 8, out.warnings
    f = _fit(img, out)
    assert 30 <= f.outer_diameter_mm <= 60 and f.rms_residual_mm < 0.5
    assert 0.35 < f.inner_diameter_mm / f.outer_diameter_mm < 0.9


@pytest.mark.parametrize("name", SIDE_OR_HAND)
def test_real_side_or_hand_photos_are_not_high(name):
    out = auto_detect(_photo(name))
    assert out.confidence != "HIGH"
    assert out.warnings


def test_real_photos_speed():
    import time

    img = _photo("20260919_171736")
    t0 = time.perf_counter()
    auto_detect(img)
    assert time.perf_counter() - t0 < 2.0


def test_heic_photo_says_use_jpeg():
    from engine.fit import FitError

    with pytest.raises(FitError, match="HEIC"):
        decode_image(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 100)
