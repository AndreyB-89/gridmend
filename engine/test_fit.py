import json
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from engine.fit import FitError, _covered_arc, auto_detect, decode_image, fit_ring

ROOT = Path(__file__).resolve().parents[1]
DEMO_PHOTO = ROOT / "sample-photos" / "20260919_180605.jpg"
DEMO_CLICKS = ROOT / "fixtures" / "demo-clicks.json"

CARD = (85.6, 53.98)
# Known card corners in a (slightly perspective) image, TL, TR, BR, BL.
CORNERS_PX = [(400.0, 300.0), (1250.0, 340.0), (1230.0, 880.0), (380.0, 850.0)]


def _synthetic(outer_d=40.0, inner_d=30.0, centre=(40.0, 80.0), arc=(300.0, 140.0), n=12):
    """Points on known circles (card mm frame) projected to pixels via a known homography."""
    w, h = CARD
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
    H_mm_to_px = cv2.getPerspectiveTransform(src, np.array(CORNERS_PX, np.float32))
    span = (arc[1] - arc[0]) % 360
    t = np.radians(arc[0] + np.linspace(0, span, n))

    def pts(r):
        mm = np.column_stack([centre[0] + r * np.cos(t), centre[1] - r * np.sin(t)])
        px = cv2.perspectiveTransform(mm.reshape(-1, 1, 2), H_mm_to_px).reshape(-1, 2)
        return [tuple(p) for p in px]

    return pts(outer_d / 2), pts(inner_d / 2)


def _blank():
    return np.full((1200, 1600, 3), 200, np.uint8)


def test_synthetic_recovers_diameters_and_missing_arc():
    outer, inner = _synthetic()
    out = fit_ring(_blank(), CORNERS_PX, CARD, outer, inner)
    f = out.fit
    assert abs(f.outer_diameter_mm - 40.0) < 0.05
    assert abs(f.inner_diameter_mm - 30.0) < 0.05
    assert f.concentric_offset_mm < 0.05
    assert f.rms_residual_mm < 0.01
    assert f.surviving_arc_deg == pytest.approx((300.0, 140.0), abs=0.1)
    assert f.missing_arc_deg == pytest.approx((140.0, 300.0), abs=0.1)
    assert f.support_deg == pytest.approx(200.0, abs=0.1)
    assert out.warnings == []
    assert out.overlay_png[:8] == b"\x89PNG\r\n\x1a\n"


def test_card_size_given_portrait_is_same_result():
    outer, inner = _synthetic()
    f = fit_ring(_blank(), CORNERS_PX, (CARD[1], CARD[0]), outer, inner).fit
    assert abs(f.outer_diameter_mm - 40.0) < 0.05


def test_portrait_card_in_image_swaps_sides():
    # Rotate the whole synthetic scene 90 deg: card now appears portrait.
    outer, inner = _synthetic()
    rot = lambda p: (1300.0 - p[1], p[0])  # 90 deg clockwise-on-screen map
    corners = [rot(p) for p in CORNERS_PX]
    corners = [corners[3], corners[0], corners[1], corners[2]]  # new TL, TR, BR, BL
    out = fit_ring(_blank(), corners, CARD, [rot(p) for p in outer], [rot(p) for p in inner])
    assert abs(out.fit.outer_diameter_mm - 40.0) < 0.05
    assert abs(out.fit.inner_diameter_mm - 30.0) < 0.05


def test_short_arc_warns():
    outer, inner = _synthetic(arc=(0.0, 90.0))
    out = fit_ring(_blank(), CORNERS_PX, CARD, outer, inner)
    assert any("short" in w for w in out.warnings)


def test_covered_arc_wraps_zero():
    s, e, span = _covered_arc(np.array([350.0, 10.0, 40.0]))
    assert (s, e) == (350.0, 40.0)
    assert span == pytest.approx(50.0)


def test_too_few_points():
    outer, inner = _synthetic()
    with pytest.raises(FitError, match="at least 3"):
        fit_ring(_blank(), CORNERS_PX, CARD, outer[:2], inner)
    with pytest.raises(FitError, match="inner"):
        fit_ring(_blank(), CORNERS_PX, CARD, outer, inner[:2])


def test_inner_bigger_than_outer():
    outer, inner = _synthetic()
    with pytest.raises(FitError):
        fit_ring(_blank(), CORNERS_PX, CARD, inner, outer)


@pytest.mark.parametrize(
    "corners",
    [
        [(400, 300), (1230, 880), (1250, 340), (380, 850)],  # crossed, not convex
        [(400, 300), (380, 850), (1230, 880), (1250, 340)],  # wrong order (counter-clockwise)
        [(0, 0), (100, 0), (100, 10), (0, 10)],  # aspect 10:1, not a card
        [(400, 300), (1250, 340), (1230, 880)],  # only 3
    ],
)
def test_bad_corners(corners):
    outer, inner = _synthetic()
    with pytest.raises(FitError):
        fit_ring(_blank(), corners, CARD, outer, inner)


def test_decode_rejects_garbage():
    with pytest.raises(FitError):
        decode_image(b"not an image")
    with pytest.raises(FitError):
        decode_image(b"")


def _demo_bytes():
    if not DEMO_PHOTO.exists():
        pytest.skip("demo photo not present (sample-photos/ is gitignored)")
    return DEMO_PHOTO.read_bytes()


def test_demo_photo_decodes_portrait():
    img = decode_image(_demo_bytes())
    h, w = img.shape[:2]
    assert (w, h) == (2252, 4000)
    # Same pixels as OpenCV's own EXIF handling (and so as the browser).
    ref = cv2.imdecode(np.frombuffer(_demo_bytes(), np.uint8), cv2.IMREAD_COLOR)
    assert ref.shape == img.shape and np.array_equal(ref, img)


def test_demo_photo_fit():
    img = decode_image(_demo_bytes())
    clicks = json.loads(DEMO_CLICKS.read_text())
    out = fit_ring(
        img,
        clicks["corners_px"],
        tuple(clicks["card_size_mm"]),
        clicks["outer_edge_points_px"],
        clicks["inner_edge_points_px"],
    )
    f = out.fit
    assert 25 <= f.outer_diameter_mm <= 60
    assert 0 < f.inner_diameter_mm < f.outer_diameter_mm
    assert f.support_deg > 120
    assert f.rms_residual_mm < 1.0
    assert math.isclose((f.support_deg + (f.missing_arc_deg[1] - f.missing_arc_deg[0]) % 360), 360, abs_tol=0.1)


def test_auto_detect_blank_image():
    out = auto_detect(np.full((1500, 1000, 3), 220, np.uint8))
    assert out.confidence == "NONE"
    assert out.corners_px is None
    assert out.outer_edge_points_px == [] and out.inner_edge_points_px == []
    assert out.warnings


def test_auto_detect_drawn_scene():
    # Beige table, blue card (portrait), yellow C-shaped arc (outer r=150, inner r=110 px).
    img = np.full((3000, 2000, 3), (190, 215, 225), np.uint8)
    card = np.array([[500, 300], [1040, 300], [1040, 1156], [500, 1156]], np.int32)
    cv2.fillPoly(img, [card], (200, 120, 90))
    cv2.ellipse(img, (1000, 2000), (150, 150), 0, 60, 300, (40, 220, 245), -1)
    cv2.ellipse(img, (1000, 2000), (110, 110), 0, 0, 360, (190, 215, 225), -1)
    out = auto_detect(img)
    assert out.confidence == "HIGH"
    assert np.allclose(out.corners_px, card, atol=4)
    assert len(out.outer_edge_points_px) >= 8 and len(out.inner_edge_points_px) >= 8
    for pts, r in ((out.outer_edge_points_px, 150), (out.inner_edge_points_px, 110)):
        d = np.hypot(*(np.array(pts) - (1000, 2000)).T)
        assert np.all(np.abs(d - r) < 4)


def test_auto_detect_demo_photo():
    import time

    img = decode_image(_demo_bytes())
    t0 = time.perf_counter()
    auto = auto_detect(img)
    assert time.perf_counter() - t0 < 1.5
    assert auto.corners_px is not None
    assert len(auto.outer_edge_points_px) >= 8 and len(auto.inner_edge_points_px) >= 8
    f = fit_ring(img, auto.corners_px, CARD, auto.outer_edge_points_px, auto.inner_edge_points_px).fit
    assert 38 <= f.outer_diameter_mm <= 45
    assert 27 <= f.inner_diameter_mm <= 33
