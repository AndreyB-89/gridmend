"""POST /api/devin/session (STUB). No key on CI, so every test runs in MOCK."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.providers import devin


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEVIN_API_KEY", "")
    return TestClient(app)


def _body(**over):
    body = {
        "part_name": "aluminium spacer bracket",
        "observations": ["Visible: a flat plate with two holes.", "Visible (side photo): the plate is one thickness."],
        "dimensions": {
            "length": {"value_mm": 60.0, "source": "MANUAL_MEASUREMENT", "confirmed": True},
            "thickness": {"value_mm": 4.0, "source": "SPOKEN_MEASUREMENT", "confirmed": True},
        },
        "operator_note": "",
    }
    body.update(over)
    return body


def test_mock_returns_the_prompt_and_sends_nothing(client):
    r = client.post("/api/devin/session", json=_body())
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["mode"] == "MOCK"
    assert out["session_id"] == devin.MOCK_SESSION_ID
    assert "DEVIN_API_KEY" in out["note"]
    assert "aluminium spacer bracket" in out["prompt"]
    assert "60.0" in out["prompt"] and "4.0" in out["prompt"]


def test_unconfirmed_size_is_refused(client):
    dims = {
        "length": {"value_mm": 60.0, "source": "PHOTO", "confirmed": False},
        "thickness": {"value_mm": None, "source": None, "confirmed": False},
    }
    r = client.post("/api/devin/session", json=_body(dimensions=dims))
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "NEEDS_INPUT"
    assert "length" in body["message"] and "thickness" in body["message"]


def test_prompt_forbids_invented_sizes_and_lists_the_checks():
    prompt = devin.build_prompt("spacer", ["Visible: a ring."], {"outer_diameter": 41.3})
    assert "Never invent a size" in prompt
    assert "<observations>" in prompt and "<confirmed_dimensions>" in prompt
    for check in ("SOLID", "DIMENSIONS", "PROFILE", "STEP_REIMPORT", "STL_MESH"):
        assert check in prompt
