"""spoken_numbers.parse: spoken or typed numbers -> values with units. No guessing."""
from __future__ import annotations

import pytest

from engine.spoken_numbers import parse, unsupported_unit


def vals(text):
    return [(n.value, n.unit) for n in parse(text)]


@pytest.mark.parametrize(
    "text, want",
    [
        ("6 mm", [(6.0, "mm")]),
        ("6.5 mm", [(6.5, "mm")]),
        ("6,5 mm", [(6.5, "mm")]),
        ("six millimetres", [(6.0, "mm")]),
        ("six millimeters", [(6.0, "mm")]),
        ("six point five millimetres", [(6.5, "mm")]),
        ("point eight millimetres", [(0.8, "mm")]),
        ("zero point six centimetres", [(0.6, "cm")]),
        ("six and a half millimetres", [(6.5, "mm")]),
        ("half a centimetre", [(0.5, "cm")]),
        ("forty one point four millimetres", [(41.4, "mm")]),
        ("twenty five", [(25.0, None)]),
        ("sixty millimetres", [(60.0, "mm")]),
        ("sixteen millimetres", [(16.0, "mm")]),
        ("one hundred millimetres", [(100.0, "mm")]),
        ("a hundred and twenty mm", [(120.0, "mm")]),
        ("two point two five mm", [(2.25, "mm")]),
        ("41.4mm", [(41.4, "mm")]),
        ("6 cm", [(6.0, "cm")]),
        ("one millimetre deep and two millimetres wide", [(1.0, "mm"), (2.0, "mm")]),
        ("six, no sorry, seven millimetres", [(6.0, None), (7.0, "mm")]),
        ("maybe six or seven", [(6.0, None), (7.0, None)]),
        ("the same as the other one", []),
        ("one mm", [(1.0, "mm")]),
        ("", []),
        # Real SLNG nova-3 output style (numerals=true), 19 Sep:
        ("6 and a half millimeters", [(6.5, "mm")]),
        ("41 point 4 millimeters", [(41.4, "mm")]),
        ("the groove is 1 millimeter deep and 2 millimeters wide", [(1.0, "mm"), (2.0, "mm")]),
    ],
)
def test_parse(text, want):
    assert vals(text) == want


def test_positions_point_at_the_number():
    text = "the groove is two millimetres wide and one millimetre deep"
    nums = parse(text)
    assert [text[n.start:n.end].split()[0] for n in nums] == ["two", "one"]
    assert nums[0].end <= text.index("wide") and nums[1].end <= text.index("deep")


@pytest.mark.parametrize(
    "text",
    ["a quarter of an inch", "five eighths of an inch", "6 inches", "about 2 in thick", 'it is 3" wide', "three sixteenths"],
)
def test_unsupported_unit(text):
    assert unsupported_unit(text)


@pytest.mark.parametrize("text", ["six millimetres", "the inner diameter is 30 mm", "in the groove it is 1 mm deep"])
def test_supported(text):
    assert not unsupported_unit(text)
