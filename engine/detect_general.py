"""General part outline: any shape, any colour, measured in the card plane.

`engine/fit.py` finds rings only: a yellow colour mask seeds a search for two
concentric circles. This module makes no shape assumption and no colour
assumption. It separates the part from the table with a background model, and
returns the outline in millimetres through the card homography.

Same hard rules as the rest of the engine:
- The card gives the scale. No card means no millimetres, never a guess.
- This code measures pixels. No language model is involved.
- Every number is a proposal until the operator confirms it.

Status: new, not wired to the UI. `fit_ring` and `cad/ring.py` still handle
rings only, so an outline from here has no CAD path yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from engine.fit import FitError, _card_homography, _detect_card, _project

CARD_ID1_MM = (85.6, 53.98)  # ID-1 bank card
MAX_SIDE = 900  # working size in pixels; the card is still ~200 px wide at this size
BG_KERNEL = 51  # median blur that removes the part but keeps the table shading
MIN_DIFF = 8  # Lab units: below this the pixel is table
L_STRONG = 45  # a lightness jump this big is an edge, not a soft shadow
MIN_AREA_FRAC = 0.0015  # smaller blobs are dirt, text or noise
SECOND_PART_FRAC = 0.30  # a second blob this big means more than one part in the photo


@dataclass
class PartOutline:
    corners_px: list[tuple[float, float]] | None
    outline_mm: list[tuple[float, float]]
    holes_mm: list[list[tuple[float, float]]] = field(default_factory=list)
    length_mm: float | None = None
    width_mm: float | None = None
    confidence: str = "NONE"  # HIGH / LOW / NONE
    warnings: list[str] = field(default_factory=list)
    overlay_png: bytes | None = None


def _foreground(small_bgr: np.ndarray) -> np.ndarray:
    """Pixels that differ from the local table colour, on L (light) and b (blue-yellow)."""
    lab = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2Lab)
    # Background = a median on a quarter-size copy, so the window is wide enough to
    # swallow a big part. On the full-size image a 51 px window fits inside a large
    # part, the middle of the part becomes "background" and only its edges survive.
    h, w = lab.shape[:2]
    tiny = cv2.resize(lab, (max(8, w // 4), max(8, h // 4)), interpolation=cv2.INTER_AREA)
    k = BG_KERNEL if BG_KERNEL % 2 else BG_KERNEL + 1
    bg = cv2.resize(cv2.medianBlur(tiny, k), (w, h), interpolation=cv2.INTER_LINEAR)
    diff = cv2.absdiff(lab, bg)
    # A shadow changes L a lot but a and b almost not at all. A part changes colour.
    # So colour (a, b) decides, and lightness alone only counts when it is very strong.
    chroma = np.maximum(diff[:, :, 1], diff[:, :, 2]).astype(np.float32)
    thr_c = max(MIN_DIFF, float(np.median(chroma) + 5.0 * np.median(np.abs(chroma - np.median(chroma)))))
    light = diff[:, :, 0].astype(np.float32)
    mask = ((chroma > thr_c) | ((light > L_STRONG) & (chroma > 0.5 * thr_c))).astype(np.uint8) * 255
    k3 = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k3, iterations=2)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, k3, iterations=1)


def _drop_card(mask: np.ndarray, quad: np.ndarray | None) -> np.ndarray:
    if quad is None:
        return mask
    pad = cv2.convexHull(np.round(quad).astype(np.int32))
    out = mask.copy()
    cv2.fillConvexPoly(out, pad, 0)
    cv2.polylines(out, [pad], True, 0, 9)  # the card edge and its shadow
    return out


def _overlay(small_bgr, quad, outer_px, holes_px) -> bytes:
    img = small_bgr.copy()
    if quad is not None:
        cv2.polylines(img, [np.round(quad).astype(np.int32)], True, (255, 160, 0), 2)
    cv2.polylines(img, [np.round(outer_px).astype(np.int32)], True, (0, 220, 60), 2)
    for h in holes_px:
        cv2.polylines(img, [np.round(h).astype(np.int32)], True, (0, 120, 255), 2)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""


def detect_part(image_bgr: np.ndarray, card_size_mm: tuple[float, float] = CARD_ID1_MM) -> PartOutline:
    """Find one part lying flat next to the card. Never raises for a normal photo."""
    if image_bgr is None or image_bgr.ndim != 3 or image_bgr.size == 0:
        return PartOutline(None, [], warnings=["Could not read the photo."])

    s = min(1.0, MAX_SIDE / max(image_bgr.shape[:2]))
    small = cv2.resize(image_bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else image_bgr
    h, w = small.shape[:2]
    warnings: list[str] = []

    quad = _detect_card(cv2.cvtColor(small, cv2.COLOR_BGR2HSV))
    H = None
    if quad is None:
        warnings.append("Card not found. Put the card flat on the table next to the part.")
    else:
        try:
            H, _ = _card_homography([tuple(p) for p in quad], card_size_mm)
        except FitError:
            H = None
            warnings.append("The card looks too tilted. Take the photo more from above.")

    mask = _drop_card(_foreground(small), quad)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    min_area = MIN_AREA_FRAC * h * w
    parts, cut = [], False
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            cut = True
            continue
        parts.append((area, i))
    if not parts:
        if cut:
            warnings.append("The part touches the edge of the photo. Step back so the whole part is in view.")
        else:
            warnings.append("I could not find a part next to the card. Put it on a plain table, away from the card.")
        return PartOutline(
            [(p[0] / s, p[1] / s) for p in quad] if quad is not None else None, [], warnings=warnings
        )

    parts.sort(reverse=True)
    if len(parts) > 1 and parts[1][0] > SECOND_PART_FRAC * parts[0][0]:
        warnings.append(f"I see {len(parts)} parts and picked the biggest one.")
    if cut:
        warnings.append("Something else touches the edge of the photo.")

    blob = (labels == parts[0][1]).astype(np.uint8)
    cs, hier = cv2.findContours(blob, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outer = max(cs, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    outer_area = cv2.contourArea(outer.astype(np.float32))
    holes = [
        c.reshape(-1, 2).astype(np.float64)
        for j, c in enumerate(cs)
        if hier[0][j][3] != -1 and cv2.contourArea(c) > 0.01 * outer_area
    ]

    outline_mm: list[tuple[float, float]] = []
    holes_mm: list[list[tuple[float, float]]] = []
    length_mm = width_mm = None
    if H is not None:
        q = _project(H, outer)
        outline_mm = [(round(float(x), 2), round(float(y), 2)) for x, y in q]
        holes_mm = [
            [(round(float(x), 2), round(float(y), 2)) for x, y in _project(H, hole)] for hole in holes
        ]
        (_, _), (a, b), _ = cv2.minAreaRect(q.astype(np.float32))
        length_mm, width_mm = round(max(a, b), 1), round(min(a, b), 1)
    else:
        warnings.append("Without the card I can show the shape but no millimetres.")

    confidence = "HIGH" if (H is not None and not cut and len(parts) == 1) else ("LOW" if outline_mm else "NONE")
    return PartOutline(
        corners_px=[(float(p[0]) / s, float(p[1]) / s) for p in quad] if quad is not None else None,
        outline_mm=outline_mm,
        holes_mm=holes_mm,
        length_mm=length_mm,
        width_mm=width_mm,
        confidence=confidence,
        warnings=warnings,
        overlay_png=_overlay(small, quad, outer, holes),
    )
