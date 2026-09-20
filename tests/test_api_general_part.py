"""The whole path for a part that is not a ring (MOCK mode, no network).

A cup, a stick or a bracket has no hole. Before this, /api/inspect answered
"Please click at least 3 points on the inner edge", and there was no way forward.
Now the photo is traced, the shape is returned, and /api/generate builds it.
"""
import json

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app

CARD_MM = [85.6, 53.98]
PX_PER_MM = 6


def _scene(hole: bool) -> bytes:
    """A yellow part on a plain table, with a blue card beside it. Drawn top-down.

    The part must differ from the table in colour (a, b in Lab), not only in
    lightness: that is exactly how the detector decides what is a part and what is
    a shadow. A cream part on a grey table is invisible to it, and so it is to a
    person too.
    """
    img = np.full((300 * PX_PER_MM, 220 * PX_PER_MM, 3), (190, 215, 225), np.uint8)
    card = np.array([[25, 25], [25 + CARD_MM[0], 25], [25 + CARD_MM[0], 25 + CARD_MM[1]], [25, 25 + CARD_MM[1]]])
    cv2.fillPoly(img, [np.round(card * PX_PER_MM).astype(np.int32)], (200, 120, 90), cv2.LINE_AA)
    cv2.rectangle(img, (80 * PX_PER_MM, 170 * PX_PER_MM), (140 * PX_PER_MM, 210 * PX_PER_MM), (40, 220, 245), -1)
    if hole:
        cv2.circle(img, (110 * PX_PER_MM, 190 * PX_PER_MM), 10 * PX_PER_MM, (190, 215, 225), -1)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def _corners():
    """The four card corners in pixels, in the order the contract asks for."""
    c = [(25, 25), (25 + CARD_MM[0], 25), (25 + CARD_MM[0], 25 + CARD_MM[1]), (25, 25 + CARD_MM[1])]
    return [[x * PX_PER_MM, y * PX_PER_MM] for x, y in c]


def _ctx(inner=None):
    return {
        "top_calibration": {"card_size_mm": CARD_MM, "size_confirmed": True,
                            "corners_px": _corners(), "same_plane_confirmed": True},
        "side_calibration": None, "top_roi_px": None,
        "outer_edge_points_px": [], "inner_edge_points_px": inner or [],
        "reviewed_voice_text": "", "operator_note": "",
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    return TestClient(app)


def _inspect(client, hole=False, inner=None):
    r = client.post("/api/inspect", files={"top_image": ("t.jpg", _scene(hole))},
                    data={"context": json.dumps(_ctx(inner))})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_part_with_no_hole_is_measured_and_not_blocked(client):
    body = _inspect(client)
    assert body["status"] == "REVIEW"
    shape = body["shape"]
    assert shape is not None, body["question"]
    assert shape["length_mm"] == pytest.approx(60, abs=4.0)
    assert shape["width_mm"] == pytest.approx(40, abs=4.0)
    assert shape["holes_mm"] == []
    assert len(shape["outline_mm"]) >= 8
    assert "inner edge" not in (body["question"] or "")


def test_a_hole_is_reported_in_the_shape(client):
    shape = _inspect(client, hole=True)["shape"]
    assert shape is not None
    assert len(shape["holes_mm"]) == 1


def test_half_an_inner_edge_is_still_a_mistake(client):
    """No inner points means "no hole". One or two means the operator stopped early."""
    body = _inspect(client, inner=[[600, 1100], [620, 1120]])
    assert "inner edge" in (body["question"] or "")


def test_the_shape_can_be_built_into_a_step_file(client):
    shape = _inspect(client)["shape"]
    req = {
        "shape": shape,
        "outer_diameter": {"value_mm": None, "source": None, "confirmed": False},
        "inner_diameter": {"value_mm": None, "source": None, "confirmed": False},
        "thickness": {"value_mm": 6.0, "source": "SPOKEN_MEASUREMENT", "confirmed": True},
        "groove": None, "profile_rz_mm": None, "profile_basis": "OBSERVED",
        "profile_confirmed": True, "missing_arc_deg": None, "purpose": "DEMO_CAD_ONLY",
    }
    r = client.post("/api/generate", json=req)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["design_id"].startswith("part-")
    assert body["step_url"] and body["stl_url"]
    assert body["missing_segment_stl_url"] is None  # only a ring knows what is missing
    assert all(c["passed"] for c in body["checks"])
    assert len(body["checks"]) == 5
    assert body["physical_fit_verified"] is False


def test_building_a_shape_without_a_thickness_asks_for_it(client):
    shape = _inspect(client)["shape"]
    req = {
        "shape": shape,
        "outer_diameter": {"value_mm": None, "source": None, "confirmed": False},
        "inner_diameter": {"value_mm": None, "source": None, "confirmed": False},
        "thickness": {"value_mm": 6.0, "source": "PHOTO", "confirmed": False},
        "groove": None, "profile_rz_mm": None, "profile_basis": "OBSERVED",
        "profile_confirmed": True, "missing_arc_deg": None, "purpose": "DEMO_CAD_ONLY",
    }
    r = client.post("/api/generate", json=req)
    assert r.status_code == 422
    assert r.json()["error"] == "NEEDS_INPUT"
    assert "thickness" in r.json()["message"].lower()


def test_an_unconfirmed_outline_is_not_built(client):
    """Nothing is built from a number the operator has not checked. Same rule as the ring."""
    shape = _inspect(client)["shape"]
    req = {
        "shape": shape,
        "outer_diameter": {"value_mm": None, "source": None, "confirmed": False},
        "inner_diameter": {"value_mm": None, "source": None, "confirmed": False},
        "thickness": {"value_mm": 6.0, "source": "SPOKEN_MEASUREMENT", "confirmed": True},
        "groove": None, "profile_rz_mm": None, "profile_basis": "OBSERVED",
        "profile_confirmed": False, "missing_arc_deg": None, "purpose": "DEMO_CAD_ONLY",
    }
    r = client.post("/api/generate", json=req)
    assert r.status_code == 422
    assert r.json()["error"] == "NEEDS_INPUT"


def test_the_ring_path_is_untouched_when_there_is_no_shape(client):
    """shape = null still means the ring template, with its groove and missing arc."""
    req = {
        "shape": None,
        "outer_diameter": {"value_mm": 40.0, "source": "PHOTO", "confirmed": True},
        "inner_diameter": {"value_mm": 30.0, "source": "PHOTO", "confirmed": True},
        "thickness": {"value_mm": 6.0, "source": "SPOKEN_MEASUREMENT", "confirmed": True},
        "groove": None, "profile_rz_mm": None, "profile_basis": "SIMPLIFIED_RECTANGLE",
        "profile_confirmed": True, "missing_arc_deg": [200.0, 340.0], "purpose": "DEMO_CAD_ONLY",
    }
    r = client.post("/api/generate", json=req)
    assert r.status_code == 200, r.text
    assert r.json()["design_id"].startswith("ring-")
    assert r.json()["missing_segment_stl_url"] is not None
