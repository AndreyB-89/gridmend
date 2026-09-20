"""Spoken or typed numbers -> values with units. Deterministic, no guessing.

Handles digits ("6.5", "6,5"), words ("forty one point four"), "and a half", "half a", "a hundred and twenty".
A lone "one" with no unit is treated as a pronoun ("the other one"), not a number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

Unit = Literal["mm", "cm"]

ONES = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
DIGIT_WORDS = {k: v for k, v in ONES.items() if v < 10}
UNITS: dict[str, Unit] = {
    "mm": "mm", "millimetre": "mm", "millimetres": "mm", "millimeter": "mm", "millimeters": "mm",
    "cm": "cm", "centimetre": "cm", "centimetres": "cm", "centimeter": "cm", "centimeters": "cm",
}

_TOKEN = re.compile(r'\d+(?:[.,]\d+)?|[a-z]+|"', re.I)
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?$")
_UNSUPPORTED = re.compile(
    r"\b(inch|inches|thou|thous|feet|foot)\b"
    r"|\b(thirds?|quarters?|fifths?|eighths?|sixteenths?|thirty[- ]?seconds?)\b"
    r'|\d\s*"'
    r"|\d\s*in\b(?=\s*(?:$|[.,;!?]|thick|wide|deep|long|high|tall|across))",
    re.I,
)


@dataclass(frozen=True)
class SpokenNumber:
    value: float
    unit: Optional[Unit]
    start: int  # character span in the text, including the unit
    end: int


def unsupported_unit(text: str) -> bool:
    """True if the text uses inches, feet or fractions like 'five eighths'. We only accept mm and cm."""
    return bool(_UNSUPPORTED.search(text))


def parse(text: str) -> list[SpokenNumber]:
    toks = [(m.group(0).lower(), m.start(), m.end()) for m in _TOKEN.finditer(text)]
    words = [t[0] for t in toks]
    out: list[SpokenNumber] = []
    i = 0
    while i < len(toks):
        got = _number_at(words, i)
        if got is None:
            i += 1
            continue
        value, j, lone_one = got
        unit = UNITS.get(words[j]) if j < len(words) else None
        if lone_one and unit is None:
            i = j
            continue
        end_idx = j if unit else j - 1
        out.append(SpokenNumber(value=value, unit=unit, start=toks[i][1], end=toks[end_idx][2]))
        i = end_idx + 1
    return out


def _number_at(w: list[str], i: int) -> Optional[tuple[float, int, bool]]:
    """Parse one number starting at token i. Returns (value, next index, is a lone 'one')."""
    n = len(w)
    # "half a centimetre"
    if w[i] == "half" and i + 1 < n and w[i + 1] in ("a", "an"):
        return 0.5, i + 2, False
    j = i
    whole: Optional[int] = None
    current = 0
    used_words = 0
    if _DIGITS.match(w[i]):
        if not w[i].isdigit():
            return float(w[i].replace(",", ".")), i + 1, False
        whole, j = int(w[i]), i + 1  # STT style: "6 and a half", "41 point 4"
    elif w[j] == "a" and j + 1 < n and w[j + 1] == "hundred":
        current, j, used_words = 1, j + 1, 1
    while whole is None and j < n:
        tok = w[j]
        if tok in TENS and current % 100 == 0:
            current += TENS[tok]
        elif tok in ONES and (used_words == 0 or current % 100 == 0 or (current % 10 == 0 and current % 100 >= 20 and ONES[tok] < 10)):
            current += ONES[tok]
        elif tok == "hundred" and used_words and current % 100 != 0 and current < 10:
            current *= 100
        elif tok == "and" and current and current % 100 == 0 and j + 1 < n and (w[j + 1] in ONES or w[j + 1] in TENS):
            pass  # "a hundred and twenty"
        else:
            break
        used_words += 1
        j += 1
    if used_words and whole is None:
        whole = current

    frac = ""
    if j < n and w[j] == "point":
        k = j + 1
        while k < n and w[k] in DIGIT_WORDS:
            frac += str(DIGIT_WORDS[w[k]])
            k += 1
        if not frac and k < n and w[k].isdigit():
            frac, k = w[k], k + 1
        if frac:
            j = k
            whole = whole or 0
    if whole is None:
        return None
    value = float(f"{whole}.{frac}") if frac else float(whole)
    if not frac and j + 2 < n and w[j] == "and" and w[j + 1] == "a" and w[j + 2] == "half":
        return value + 0.5, j + 3, False
    lone_one = used_words == 1 and not frac and w[i] == "one"
    return value, j, lone_one
