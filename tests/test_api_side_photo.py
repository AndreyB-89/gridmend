"""/api/inspect with an optional side photo (MOCK mode, no network)."""
import json

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app

CTX = {
    "top_calibration": {"card_size_mm": None, "size_confirmed": False, "corners_px": None, "same_plane_confirmed": False},
    "side_calibration": None, "top_roi_px": None, "outer_edge_points_px": [], "inner_edge_points_px": [],
    "reviewed_voice_text": "", "operator_note": "",
}


def _jpeg(color=200):
    ok, buf = cv2.imencode(".jpg", np.full((300, 400, 3), color, np.uint8))
    return buf.tobytes()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    return TestClient(app)


def test_inspect_without_side_photo(client):
    r = client.post("/api/inspect", files={"top_image": ("t.jpg", _jpeg())}, data={"context": json.dumps(CTX)})
    assert r.status_code == 200
    assert not any("side photo" in o for o in r.json()["observations"])


def test_inspect_with_side_photo_reaches_the_vision_step(client):
    files = {"top_image": ("t.jpg", _jpeg()), "side_image": ("s.jpg", _jpeg(120))}
    r = client.post("/api/inspect", files=files, data={"context": json.dumps(CTX)})
    assert r.status_code == 200
    assert any(o.startswith("Visible (side photo):") for o in r.json()["observations"])


def test_inspect_bad_side_photo_is_a_plain_error(client):
    files = {"top_image": ("t.jpg", _jpeg()), "side_image": ("s.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)}
    r = client.post("/api/inspect", files=files, data={"context": json.dumps(CTX)})
    assert r.status_code == 422
    assert "side photo" in r.json()["message"].lower() and "HEIC" in r.json()["message"]
