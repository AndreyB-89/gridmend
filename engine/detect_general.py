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

from engine.fit import AutoDetect, FitError, _card_homography, _detect_card, _project

CARD_ID1_MM = (85.6, 53.98)  # ID-1 bank card
MAX_SIDE = 900  # working size in pixels; the card is still ~200 px wide at this size
BG_KERNEL = 51  # median window on the shrunk copy
BG_SHRINK = 8  # shrink before the median: the window then covers a part AND its shadow
MIN_DIFF = 8  # Lab units: below this the pixel is table
L_STRONG = 45  # a lightness jump this big is an edge, not a soft shadow
SHADOW_COLOUR_TOL = 1.25  # channels scaled this evenly means less light, not another colour
SHADOW_MAX_RATIO = 0.92  # and the pixel must be darker than the table
GRAIN_KERNEL = 9  # median window that removes wood grain but keeps the edge of a part
TEXTURE_WIN = 21  # window for "how rough is the surface here"
TEXTURE_KEEP = 0.55  # this much of the table's roughness still means table
PLAIN_TABLE_TEX = 0.010  # below this the table has no grain, so roughness proves nothing
MIN_AREA_FRAC = 0.0015  # smaller blobs are dirt, text or noise
NEAR_CARD = 2.2  # a part sits within this many card diagonals of the card; further away is the room
ROOM_REACH = 15  # pixels: how far the room reaches around what leaves the photo
ROOM_TOUCH = 0.25  # this much of a blob inside that reach means it is the room too
OUTER_POINTS = 16  # points offered on the outer edge
INNER_POINTS = 12  # points offered on the edge of the hole
MIN_HOLE_POINTS = 12  # a smaller hole outline is noise, not an inner edge
HULL_TOL_PX = 3.0  # an outline point this close to the convex hull is on the outer skin
GROW_WALL_FRAC = 0.55  # a hole edge may move out by this share of the way to the outer edge
GROW_PEAK_SHARE = 0.70  # an edge must be this share of the clearest edge inside the wall
GROW_MAX_PX = 40.0  # and never further than this, so a dark bore cannot run away
GROW_EDGE_KEEP = 0.6  # the edge found outside must be this clear next to the hole's own edge
GROW_MIN_STEPS = 6  # half-pixel steps to skip: the blur of the hole's own edge
SECOND_PART_FRAC = 0.30  # a second blob this big means more than one part in the photo


@dataclass
class PartOutline:
    corners_px: list[tuple[float, float]] | None
    outline_mm: list[tuple[float, float]]
    outline_px: list[tuple[float, float]] = field(default_factory=list)
    candidates_px: list[list[tuple[float, float]]] = field(default_factory=list)
    holes_mm: list[list[tuple[float, float]]] = field(default_factory=list)
    holes_px: list[list[tuple[float, float]]] = field(default_factory=list)
    length_mm: float | None = None
    width_mm: float | None = None
    # HIGH = one clear candidate and a card. It does NOT mean the number is right:
    # a part that is not flat on the table (a standing cup) still measures wrong.
    confidence: str = "NONE"
    warnings: list[str] = field(default_factory=list)
    overlay_png: bytes | None = None


def _big_blur(img: np.ndarray) -> np.ndarray:
    """The slow part of the picture: the table with its shading, without the part.

    A median on a quarter-size copy, so the window is wide enough to swallow a big
    part. With a 51 px window on the full-size image the middle of a large part
    becomes "background" and only its edges survive.
    """
    h, w = img.shape[:2]
    tiny = cv2.resize(img, (max(8, w // BG_SHRINK), max(8, h // BG_SHRINK)), interpolation=cv2.INTER_AREA)
    k = BG_KERNEL if BG_KERNEL % 2 else BG_KERNEL + 1
    return cv2.resize(cv2.medianBlur(tiny, k), (w, h), interpolation=cv2.INTER_LINEAR)


def _texture(lab: np.ndarray) -> np.ndarray:
    """How rough the surface looks, next to how bright it is.

    Wood grain keeps the same roughness in the light and in a shadow, because
    less light scales the pattern and its average together. A smooth part has
    almost none. This is the cue that a colour test cannot give us.
    """
    light = lab[:, :, 0].astype(np.float32)
    fine = cv2.absdiff(light, cv2.medianBlur(lab, GRAIN_KERNEL)[:, :, 0].astype(np.float32))
    return cv2.blur(fine, (TEXTURE_WIN, TEXTURE_WIN)) / (cv2.blur(light, (TEXTURE_WIN, TEXTURE_WIN)) + 1.0)


def _foreground(small_bgr: np.ndarray) -> np.ndarray:
    """Pixels that are a part, not the table, its grain or its shadow."""
    lab = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2Lab)
    # Median first: it removes the grain of the table but keeps the edge of a part.
    flat = cv2.medianBlur(lab, GRAIN_KERNEL)
    bg = _big_blur(flat)
    diff = cv2.absdiff(flat, bg)
    # A shadow changes L a lot but a and b much less. A part changes colour.
    # So colour (a, b) decides, and lightness alone only counts when it is very strong.
    chroma = np.maximum(diff[:, :, 1], diff[:, :, 2]).astype(np.float32)
    thr_c = max(MIN_DIFF, float(np.median(chroma) + 5.0 * np.median(np.abs(chroma - np.median(chroma)))))
    light = diff[:, :, 0].astype(np.float32)
    mask = ((chroma > thr_c) | ((light > L_STRONG) & (chroma > 0.5 * thr_c))).astype(np.uint8) * 255
    mask[_shadow(small_bgr, lab)] = 0
    k3 = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k3, iterations=2)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, k3, iterations=1)


def _shadow(small_bgr: np.ndarray, lab: np.ndarray) -> np.ndarray:
    """True where the pixel is still the table, only with less light on it.

    Two signs, because one is not enough:
    1. Every channel scaled by about the same factor. That is a soft shadow on a
       plain table, where the only change is "less of the same light".
    2. The table's own roughness is still there, and the pixel is darker. A hard
       shadow on wood is filled by a cooler light, so its colour DOES change, but
       the grain under it does not go away. A smooth part has no grain.
    """
    img = small_bgr.astype(np.float32) + 1.0
    bg = _big_blur(small_bgr).astype(np.float32) + 1.0
    ratio = img / bg
    lo, hi = ratio.min(axis=2), ratio.max(axis=2)
    even = (hi / np.maximum(lo, 1e-6) < SHADOW_COLOUR_TOL) & (hi < SHADOW_MAX_RATIO)

    tex = _texture(lab)
    # Most of a photo is table, so the middle value of the roughness IS the table's
    # roughness. (A frame of border pixels is not safe: a phone photo is often
    # smeared or dark at the edge.)
    table_tex = float(np.median(tex))
    if table_tex < PLAIN_TABLE_TEX:  # a plain table: roughness says nothing, colour must decide
        return even
    darker = hi < SHADOW_MAX_RATIO
    rough = (darker & (tex > TEXTURE_KEEP * table_tex)).astype(np.uint8)
    # Shrink it a little: near the edge of a part the roughness reading is the edge
    # itself, and without this the rule eats a few millimetres of the part.
    rough = cv2.erode(rough, np.ones((3, 3), np.uint8))
    return even | (rough > 0)


def _edge_strength(small_bgr: np.ndarray) -> np.ndarray:
    """How strong an edge is at each pixel, on lightness and on colour."""
    lab = cv2.cvtColor(cv2.GaussianBlur(small_bgr, (3, 3), 0), cv2.COLOR_BGR2Lab).astype(np.float32)
    g = np.zeros(lab.shape[:2], np.float32)
    for ch in (0, 2):
        gx = cv2.Scharr(lab[:, :, ch], cv2.CV_32F, 1, 0)
        gy = cv2.Scharr(lab[:, :, ch], cv2.CV_32F, 0, 1)
        g = np.maximum(g, cv2.magnitude(gx, gy))
    return g


def _grow_hole(grad: np.ndarray, hole: np.ndarray, outer: np.ndarray) -> np.ndarray:
    """Push the edge of a hole out to the top edge of the wall.

    Looking into a through hole from the side, the far wall hides part of the
    opening: what the camera sees is the floor through the hole, smaller than the
    opening and pushed to one side. So from each point of the visible hole we walk
    outwards and stop at the FIRST clear edge we meet, which is the top edge of the
    wall. A photo taken straight down has flat top face out there, no edge, and
    nothing moves.
    """
    h, w = grad.shape
    centre = hole.mean(0)
    radius = float(np.mean(np.hypot(*(hole - centre).T)))
    hull = outer.reshape(-1, 1, 2).astype(np.float32)
    here = np.median(grad[np.clip(np.round(hole[:, 1]), 0, h - 1).astype(int),
                          np.clip(np.round(hole[:, 0]), 0, w - 1).astype(int)])
    floor_level = max(GROW_EDGE_KEEP * float(here), 1e-6)
    out = []
    for p in hole:
        u = p - centre
        n = float(np.hypot(*u))
        if n < 1e-6:
            out.append(p)
            continue
        u = u / n
        # Never walk more than part of the way to the outer edge: whatever the
        # opening is, it lies inside the wall of the part.
        wall = abs(cv2.pointPolygonTest(hull, (float(p[0]), float(p[1])), True))
        reach = max(2.0, min(GROW_MAX_PX, GROW_WALL_FRAC * wall))
        steps = np.arange(0.0, reach + 0.5, 0.5, dtype=np.float32)
        xs = np.clip(p[0] + steps * u[0], 0, w - 1)
        ys = np.clip(p[1] + steps * u[1], 0, h - 1)
        line = grad[np.round(ys).astype(int), np.round(xs).astype(int)]
        # The clearest edge inside the wall, not the first one: the wall itself can
        # carry grooves and shading, and those edges are weaker than its top edge.
        tail = line[GROW_MIN_STEPS:]
        moved = p
        if len(tail):
            # The first edge that is really an edge: as clear as the hole's own rim,
            # and at least half as clear as the best edge inside the wall. A groove
            # or the shading of the wall does not pass both.
            level = max(floor_level, GROW_PEAK_SHARE * float(tail.max()))
            hits = np.nonzero(tail >= level)[0]
            if len(hits):
                moved = p + steps[GROW_MIN_STEPS + int(hits[0])] * u
        out.append(moved)
    return np.asarray(out, np.float64)


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
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    # Everything that runs out of the photo is the room, not the part: a table edge,
    # a dark floor, a sleeve. What touches such an area belongs to it as well.
    room = np.zeros((h, w), np.uint8)
    for i in range(1, n):
        x, y, bw, bh, _ = stats[i]
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            room[labels == i] = 255
    room = cv2.dilate(room, np.ones((ROOM_REACH, ROOM_REACH), np.uint8))
    min_area = MIN_AREA_FRAC * h * w
    # The engineer is told to put the card next to the part. So a blob far from the
    # card is the room, not the part: a table edge, a dark floor, a sleeve.
    card_centre = np.mean(quad, axis=0) if quad is not None else None
    card_span = float(np.linalg.norm(quad.max(0) - quad.min(0))) if quad is not None else 0.0
    parts, cut, far = [], False, 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            cut = True
            continue
        if card_centre is not None and np.linalg.norm(centroids[i] - card_centre) > NEAR_CARD * card_span:
            far += 1
            continue
        if np.count_nonzero(room[labels == i]) > ROOM_TOUCH * area:
            cut = True
            continue
        parts.append((area, i))
    if not parts:
        if cut:
            warnings.append("The part touches the edge of the photo. Step back so the whole part is in view.")
        elif far:
            warnings.append("I see something, but not next to the card. Put the card beside the part.")
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

    def outline_of(index):
        one = (labels == index).astype(np.uint8)
        cs, hier = cv2.findContours(one, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        return cs, hier

    # Every candidate, biggest first, so the operator can say "no, that one".
    candidates_px = [
        [(round(float(x) / s, 1), round(float(y) / s, 1))
         for x, y in max(outline_of(i)[0], key=cv2.contourArea).reshape(-1, 2)]
        for _, i in parts
    ]

    blob = (labels == parts[0][1]).astype(np.uint8)
    cs, hier = cv2.findContours(blob, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outer = max(cs, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    outer_area = cv2.contourArea(outer.astype(np.float32))
    holes = [
        c.reshape(-1, 2).astype(np.float64)
        for j, c in enumerate(cs)
        if hier[0][j][3] != -1 and cv2.contourArea(c) > 0.01 * outer_area
    ]
    if holes:  # a hole seen at an angle looks smaller than it is
        grad = _edge_strength(small)
        holes = [_grow_hole(grad, hole, outer) for hole in holes]

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
        outline_px=candidates_px[0],
        candidates_px=candidates_px,
        holes_mm=holes_mm,
        holes_px=[[(round(float(x) / s, 1), round(float(y) / s, 1)) for x, y in hole] for hole in holes],
        length_mm=length_mm,
        width_mm=width_mm,
        confidence=confidence,
        warnings=warnings,
        overlay_png=_overlay(small, quad, outer, holes),
    )


def _sample(points: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    """n points spread evenly along a closed outline."""
    if len(points) <= n:
        return points
    step = len(points) / n
    return [points[int(round(i * step)) % len(points)] for i in range(n)]


def _outer_boundary(outline: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The points of the outline that lie on its outer skin.

    A broken ring is a "C": its outline runs around the outside AND back along the
    inside. Feeding all of it to a circle fit gives a diameter about 10% too small.
    The outer skin is the part of the outline that touches its own convex hull, and
    that is true for any shape, round or not.
    """
    if len(outline) < 8:
        return outline
    q = np.asarray(outline, np.float32)
    hull = cv2.convexHull(q.reshape(-1, 1, 2)).reshape(-1, 2)
    keep = [p for p in q if abs(cv2.pointPolygonTest(hull.reshape(-1, 1, 2), (float(p[0]), float(p[1])), True)) <= HULL_TOL_PX]
    return [tuple(map(float, p)) for p in keep] if len(keep) >= 8 else outline


def auto_detect(image_bgr: np.ndarray) -> AutoDetect:
    """The app's first guess: card corners, plus points on the outer and inner edge.

    This replaces the old ring-only detector. The points come from the outline of
    whatever part is next to the card, and from its largest hole, so a ring, a cup
    and a stick all go through the same road. The operator still checks the points.
    """
    part = detect_part(image_bgr)
    outer = _sample(_outer_boundary(part.outline_px), OUTER_POINTS)
    inner: list[tuple[float, float]] = []
    if part.holes_px:
        biggest = max(part.holes_px, key=len)
        if len(biggest) >= MIN_HOLE_POINTS:
            inner = _sample(biggest, INNER_POINTS)
    warnings = list(part.warnings)
    if outer and not inner:
        warnings.append("I found no hole in this part. If it has one, click 3 points on the inner edge.")
    confidence = part.confidence if outer else "NONE"
    return AutoDetect(
        corners_px=part.corners_px,
        outer_edge_points_px=outer,
        inner_edge_points_px=inner,
        confidence=confidence,
        warnings=warnings,
    )
