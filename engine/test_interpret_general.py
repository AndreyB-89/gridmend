"""The questions must fit the part in front of the engineer, not always a ring.

A cup has no inner edge and no inner groove. Asking for them is noise, and it also
tells the engineer the app did not understand the photo. These tests cover the MOCK
path, which is what runs with no Nebius key, and the text sent to the model.
"""
from __future__ import annotations

from api.schemas import Calibration, InspectContext, PartShape, RingFit
from engine.interpret import _mock, _user_text

RING = RingFit(
    outer_diameter_mm=41.3, inner_diameter_mm=29.5, concentric_offset_mm=0.2, rms_residual_mm=0.3,
    surviving_arc_deg=(0.0, 200.0), missing_arc_deg=(200.0, 360.0), support_deg=200.0,
)
CUP = PartShape(
    outline_mm=[(0.0, 0.0), (60.0, 0.0), (60.0, 40.0), (0.0, 40.0)],
    holes_mm=[], length_mm=60.0, width_mm=40.0, confidence="HIGH",
)
WASHER = CUP.model_copy(update={"holes_mm": [[(20.0, 10.0), (40.0, 10.0), (40.0, 30.0), (20.0, 30.0)]]})


def _ctx(said: str = "") -> InspectContext:
    return InspectContext(
        top_calibration=Calibration(card_size_mm=(85.6, 53.98), size_confirmed=True,
                                    corners_px=((0, 0), (10, 0), (10, 10), (0, 10)), same_plane_confirmed=True),
        side_calibration=None, top_roi_px=None, outer_edge_points_px=[], inner_edge_points_px=[],
        reviewed_voice_text=said, operator_note="",
    )


def test_a_part_with_no_hole_is_never_asked_for_an_inner_edge():
    obs, question = _mock(_ctx(), None, shape=CUP)
    assert question is not None
    assert "inner edge" not in question.lower()
    assert "ring" not in question.lower()


def test_a_part_with_no_hole_is_measured_in_the_observations():
    obs, _ = _mock(_ctx(), None, shape=CUP)
    assert any("60" in o and "40" in o for o in obs), obs
    assert any(o.startswith("Measured:") for o in obs), obs


def test_the_next_question_for_any_part_is_its_thickness():
    _, question = _mock(_ctx(), None, shape=CUP)
    assert "thick" in question.lower()


def test_after_the_thickness_a_shape_part_needs_nothing_more():
    _, question = _mock(_ctx("the thickness is 6 mm"), None, shape=CUP)
    assert question is None


def test_a_part_with_a_hole_is_told_so():
    obs, _ = _mock(_ctx(), None, shape=WASHER)
    assert any("hole" in o.lower() for o in obs), obs


def test_a_ring_fit_still_asks_the_ring_questions():
    _, question = _mock(_ctx(), RING, shape=None)
    assert "thick" in question.lower()
    _, question = _mock(_ctx("thickness 6 mm"), RING, shape=None)
    assert "groove" in question.lower()


def test_with_no_fit_and_no_shape_it_asks_for_clicks():
    _, question = _mock(_ctx(), None, shape=None)
    assert "click" in question.lower()


def test_the_model_is_told_the_shape_numbers_and_who_measured_them():
    text = _user_text(_ctx(), None, shape=CUP)
    assert "60.0" in text and "40.0" in text
    assert "geometry code" in text.lower()


def test_the_model_is_told_when_a_part_has_no_hole():
    assert "no hole" in _user_text(_ctx(), None, shape=CUP).lower()
