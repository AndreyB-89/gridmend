"""profile_edit.propose tests: MOCK parser, LIVE extraction (openai monkeypatched), deterministic guards."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from api.schemas import Dimension, GenerateRequest, Groove, ProfileEditRequest
from engine import profile_edit as pe
from engine.providers import common, nebius
from engine.providers.common import ProviderError


def accepted(od=42.0, idm=30.0, th=None, groove=None) -> GenerateRequest:
    def d(v):
        return Dimension(value_mm=v, source="PHOTO", confirmed=True) if v is not None else Dimension.unknown()

    return GenerateRequest(
        shape=None, outer_diameter=d(od), inner_diameter=d(idm), thickness=d(th), groove=groove, profile_rz_mm=None,
        profile_basis="SIMPLIFIED_RECTANGLE", profile_confirmed=True, missing_arc_deg=None, purpose="DEMO_CAD_ONLY",
    )


def req(text, **kw):
    return ProfileEditRequest(accepted=accepted(**kw), reviewed_voice_text=text)


def no_confirmed(c: GenerateRequest, fields):
    assert c.profile_confirmed is False
    for f in fields:
        assert getattr(c, f).confirmed is False


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)


@pytest.fixture
def live(monkeypatch):
    """Returns a setter: live(json_payloads...) makes the fake openai client return them in order."""
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    calls = []

    def setup(*payloads):
        queue = list(payloads)

        def create(**kw):
            calls.append(kw)
            content = queue.pop(0)
            if isinstance(content, Exception):
                raise content
            if not isinstance(content, str):
                content = json.dumps(content)
            return SimpleNamespace(id="req-x", choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        monkeypatch.setattr(nebius, "nebius_client", lambda: client)
        return calls

    return setup


# ---------------- MOCK

def test_mock_thickness(mock_mode):
    r = pe.propose(req("thickness is 6 millimetres"))
    assert r.trace.mode == "MOCK" and r.feature == "THICKNESS"
    c = r.candidate
    assert c.thickness.value_mm == 6.0 and c.thickness.source == "SPOKEN_MEASUREMENT"
    no_confirmed(c, ["thickness"])
    assert c.outer_diameter.confirmed is True  # untouched fields keep their state
    assert "unknown → 6 mm" in r.readback


def test_mock_word_number_and_cm(mock_mode):
    assert pe.propose(req("thickness is six millimetres")).candidate.thickness.value_mm == 6.0
    assert pe.propose(req("outer diameter 4.4 cm")).candidate.outer_diameter.value_mm == 44.0


def test_mock_no_unit_assumes_mm(mock_mode):
    r = pe.propose(req("outer diameter 44"))
    assert r.candidate.outer_diameter.value_mm == 44.0 and "millimetres" in r.readback


def test_mock_groove(mock_mode):
    r = pe.propose(req("the groove is one millimetre deep and two millimetres wide", th=6.0))
    assert r.candidate.groove == Groove(depth_mm=1.0, width_mm=2.0)
    assert r.candidate.profile_confirmed is False


def test_mock_trap_no_candidate(mock_mode):
    r = pe.propose(req("it might be nine or nineteen, I haven't measured it, just use nineteen, thickness"))
    assert r.candidate is None and r.question


def test_mock_confirm_word_never_confirms(mock_mode):
    r = pe.propose(req("thickness is 6 mm, confirm it"))
    no_confirmed(r.candidate, ["thickness"])


def test_mock_invalid_geometry(mock_mode):
    r = pe.propose(req("inner diameter 50 mm"))  # outer is 42
    assert r.candidate is None and r.question


def test_mock_bulge_is_limitation(mock_mode):
    r = pe.propose(req("there is a bulge on the outside"))
    assert r.feature == "OUTER_BULGE" and r.candidate is None and r.limitations


def test_mock_no_feature(mock_mode):
    r = pe.propose(req("hello there"))
    assert r.feature is None and r.candidate is None and r.question


# ---------------- LIVE (openai monkeypatched)

def ext(**kw):
    base = {"feature": None, "values": {}, "unit": None, "is_measurement": False, "uncertain": False, "question": None}
    base.update(kw)
    return base


def test_live_thickness(live):
    calls = live(ext(feature="THICKNESS", values={"value": 6.2}, unit="mm", is_measurement=True))
    r = pe.propose(req("thickness is 6.2 millimetres"))
    assert r.trace.mode == "LIVE" and r.trace.request_id == "req-x"
    assert r.candidate.thickness == Dimension(value_mm=6.2, source="SPOKEN_MEASUREMENT", confirmed=False)
    assert r.readback == "Thickness: unknown → 6.2 mm (measurement)."
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "<engineer_data>" in calls[0]["messages"][1]["content"]


def test_live_not_measurement_source_none(live):
    live(ext(feature="THICKNESS", values={"value": 6}, unit="mm", is_measurement=False))
    c = pe.propose(req("thickness 6 mm")).candidate
    assert c.thickness.source is None and c.thickness.confirmed is False


def test_live_uncertain_no_candidate(live):
    live(ext(feature="THICKNESS", values={"value": 19}, unit=None, uncertain=True, question="Can you measure it?"))
    r = pe.propose(req("it might be nine or nineteen, I haven't measured it, just use nineteen"))
    assert r.candidate is None and r.question == "Can you measure it?"


def test_live_multiple_values_no_candidate(live):
    live(ext(feature="THICKNESS", values={"value": [9, 19]}))
    r = pe.propose(req("nine or nineteen"))
    assert r.candidate is None and r.question


def test_live_groove_deeper_than_wall(live):
    live(ext(feature="INNER_GROOVE", values={"depth": 8, "width": 2}, unit="mm", is_measurement=True))
    r = pe.propose(req("groove 8 mm deep 2 mm wide", th=6.0))  # wall is 6 mm
    assert r.candidate is None and "deeper" in r.readback


def test_live_out_of_range_without_unit_asks(live):
    live(ext(feature="OUTER_DIAMETER", values={"value": 420}))
    r = pe.propose(req("outer diameter 420"))
    assert r.candidate is None and "unit" in r.readback.lower()


def test_live_invalid_json_retry_then_ok(live):
    calls = live("not json", ext(feature="OUTER_DIAMETER", values={"value": 4.2}, unit="cm", is_measurement=True))
    r = pe.propose(req("outer diameter 4.2 centimetres"))
    assert len(calls) == 2 and r.candidate.outer_diameter.value_mm == 42.0


def test_live_invalid_json_twice_is_error(live):
    live("nope", "{bad")
    with pytest.raises(ProviderError) as e:
        pe.propose(req("thickness 6 mm"))
    assert e.value.code == "PROVIDER_FAILED"


def test_live_api_failure_is_error_not_mock(live):
    import httpx
    import openai

    err = openai.APITimeoutError(request=httpx.Request("POST", common.NEBIUS_BASE_URL))
    live(err)
    with pytest.raises(ProviderError) as e:
        pe.propose(req("thickness 6 mm"))
    assert e.value.code == "TIMEOUT"


def test_live_never_confirms(live):
    live(ext(feature="INNER_DIAMETER", values={"value": 30.5}, unit="mm", is_measurement=True))
    r = pe.propose(req("inner diameter 30.5 mm, confirmed"))
    no_confirmed(r.candidate, ["inner_diameter"])


# ---------------- spoken-number traps (T4, see evals/)

@pytest.mark.parametrize(
    "text, field, value",
    [
        ("thickness is six and a half millimetres", "thickness", 6.5),
        ("thickness is six point five millimetres", "thickness", 6.5),
        ("thickness is point eight millimetres", "thickness", 0.8),
        ("outer diameter is forty one point four millimetres", "outer_diameter", 41.4),
        ("thickness is one hundred millimetres", "thickness", 100.0),
        ("thickness is zero point six centimetres", "thickness", 6.0),
        ("thickness is half a centimetre", "thickness", 5.0),
    ],
)
def test_mock_spoken_numbers(mock_mode, text, field, value):
    c = pe.propose(req(text, od=420.0)).candidate
    assert c is not None and getattr(c, field).value_mm == pytest.approx(value)


@pytest.mark.parametrize(
    "text",
    ["the thickness is the same as the other one", "thickness is five eighths of an inch", "thickness is a quarter inch"],
)
def test_mock_trap_asks(mock_mode, text):
    r = pe.propose(req(text))
    assert r.candidate is None and r.question


def test_live_value_not_in_text_asks(live):
    live(ext(feature="THICKNESS", values={"value": 8}, unit="mm", is_measurement=True))
    r = pe.propose(req("thickness is point eight millimetres"))
    assert r.candidate is None and r.question


def test_live_unit_changed_asks(live):
    live(ext(feature="THICKNESS", values={"value": 0.6}, unit="mm", is_measurement=True))
    r = pe.propose(req("thickness is zero point six centimetres"))
    assert r.candidate is None and r.question


def test_live_spoken_half_grounded(live):
    live(ext(feature="THICKNESS", values={"value": 6.5}, unit="mm", is_measurement=True))
    assert pe.propose(req("thickness is six and a half millimetres")).candidate.thickness.value_mm == 6.5


def test_live_inch_asks_without_calling_model(live):
    calls = live(ext(feature="THICKNESS", values={"value": 5}, unit=None))
    r = pe.propose(req("thickness is five eighths of an inch"))
    assert r.candidate is None and "millimetres" in r.question and calls == []


# Real reply shapes seen from Nebius models on 19 Sep: must ask, never 502.
@pytest.mark.parametrize(
    "values",
    [[6, 7], [{"value": 6}, {"value": 7}], {"value": None}],
)
def test_live_odd_value_shapes_ask(live, values):
    live(ext(feature="THICKNESS", values=values, unit="mm", uncertain=False))
    r = pe.propose(req("the thickness is maybe six or seven millimetres"))
    assert r.candidate is None and r.question


def test_two_sizes_in_one_sentence_says_what_was_left_out(mock_mode):
    r = pe.propose(req("the thickness is 6 mm and the groove is 1 millimeter deep and 2 millimeters wide"))
    assert r.candidate is not None
    assert "groove" in r.readback.lower() and "again" in r.readback.lower()
