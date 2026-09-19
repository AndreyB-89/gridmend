"""Ring fit from operator clicks on a top-view photo.

Input: one photo, the 4 card corners and points on the outer and inner edge
of the surviving arc. All pixel coordinates are in the image *as the browser
shows it*, i.e. after the EXIF orientation is applied. `decode_image` applies
the EXIF orientation itself, so its pixel grid matches the browser.

Steps:
1. Homography from the 4 card corners (TL, TR, BR, BL as seen) to the card
   plane in mm: (0,0), (w,0), (w,h), (0,h). If the card lies in portrait in the
   photo, w and h are swapped so the longer side maps to the longer card size.
2. Edge points go to mm. Each edge gets a circle fit: algebraic (Kasa) least
   squares, then a few Gauss-Newton steps on the geometric distance.
3. Diameters, centre offset and RMS residual (geometric, in mm) are reported.
4. Surviving arc: angles of all clicked points around the mean centre. The
   largest gap between sorted angles is the missing part.

Angle convention: the mm frame has y pointing down (like the image). Angles
use atan2(-(y - cy), x - cx), in degrees, 0 = +x (right in the card frame),
counter-clockwise *as seen on screen*. Arcs are (start, end), going CCW from
start to end, values in [0, 360).

Accuracy note: the ring's top face sits a few mm above the card plane, so the
scale has a small error (a few percent at most at normal phone distance). The
arc support is also measured only between the clicked points, so the operator
should click close to the fracture ends. We do not claim mm accuracy.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from api.schemas import RingFit

MAX_PIXELS = 20_000_000
OVERLAY_MAX_SIDE = 1600

Pt = tuple[float, float]


class FitError(Exception):
    """Input problem. The message is simple English for the operator."""


@dataclass
class FitOutput:
    fit: RingFit
    warnings: list[str]
    overlay_png: bytes


# --------------------------------------------------------------------------
# Image decode with EXIF orientation
# --------------------------------------------------------------------------

def _jpeg_exif_orientation(data: bytes) -> int:
    """Return the EXIF Orientation tag (1..8) of a JPEG, or 1 if absent."""
    try:
        if data[:2] != b"\xff\xd8":
            return 1
        i = 2
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                return 1
            marker = data[i + 1]
            if marker in (0xD9, 0xDA):  # end of image / start of scan
                return 1
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            seg = data[i + 4:i + 2 + seg_len]
            if marker == 0xE1 and seg[:6] == b"Exif\x00\x00":
                tiff = seg[6:]
                e = "<" if tiff[:2] == b"II" else ">"
                ifd = struct.unpack(e + "I", tiff[4:8])[0]
                n = struct.unpack(e + "H", tiff[ifd:ifd + 2])[0]
                for k in range(n):
                    p = ifd + 2 + 12 * k
                    tag, typ = struct.unpack(e + "HH", tiff[p:p + 4])
                    if tag == 0x0112 and typ == 3:
                        v = struct.unpack(e + "H", tiff[p + 8:p + 10])[0]
                        return v if 1 <= v <= 8 else 1
                return 1
            i += 2 + seg_len
    except (struct.error, IndexError):
        return 1
    return 1


def _apply_orientation(img: np.ndarray, orientation: int) -> np.ndarray:
    if orientation == 2:
        return cv2.flip(img, 1)
    if orientation == 3:
        return cv2.rotate(img, cv2.ROTATE_180)
    if orientation == 4:
        return cv2.flip(img, 0)
    if orientation == 5:
        return cv2.transpose(img)
    if orientation == 6:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if orientation == 7:
        return cv2.rotate(cv2.transpose(img), cv2.ROTATE_180)
    if orientation == 8:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def decode_image(data: bytes) -> np.ndarray:
    """Decode to BGR with EXIF orientation applied (same pixel grid as a browser).

    We decode with IMREAD_IGNORE_ORIENTATION and rotate ourselves, so the result
    does not depend on how a given OpenCV build handles EXIF.
    """
    if not data:
        raise FitError("The photo is empty. Please upload the photo again.")
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if img is None or img.size == 0:
        raise FitError("Could not read the photo. Please upload a JPEG or PNG file.")
    if img.shape[0] * img.shape[1] > MAX_PIXELS:
        raise FitError("The photo is too large (over 20 megapixels). Please use a smaller photo.")
    return _apply_orientation(img, _jpeg_exif_orientation(data))


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def _card_homography(corners_px, card_size_mm) -> tuple[np.ndarray, tuple[float, float]]:
    if corners_px is None or len(corners_px) != 4:
        raise FitError("Please click exactly 4 card corners.")
    c = np.asarray(corners_px, dtype=np.float64).reshape(4, 2)
    if not np.all(np.isfinite(c)):
        raise FitError("A card corner is not a valid point. Please click the corners again.")
    w, h = float(card_size_mm[0]), float(card_size_mm[1])
    if not (w > 0 and h > 0):
        raise FitError("The card size must be two positive numbers in mm.")

    if not cv2.isContourConvex(c.astype(np.float32).reshape(-1, 1, 2)):
        raise FitError("The 4 card corners do not form a clean box. Click them in order: top-left, top-right, bottom-right, bottom-left.")
    area = abs(cv2.contourArea(c.astype(np.float32)))
    if area < 400:  # smaller than 20x20 px
        raise FitError("The card corners are too close together. Please click the 4 corners of the card.")
    # Signed area in image coords (y down): TL,TR,BR,BL gives positive (clockwise on screen).
    x, y = c[:, 0], c[:, 1]
    signed = 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
    if signed <= 0:
        raise FitError("The card corners are in the wrong order. Click: top-left, top-right, bottom-right, bottom-left.")

    sides = [np.linalg.norm(c[(i + 1) % 4] - c[i]) for i in range(4)]
    horiz = (sides[0] + sides[2]) / 2  # TL->TR, BR->BL
    vert = (sides[1] + sides[3]) / 2   # TR->BR, BL->TL
    long_mm, short_mm = max(w, h), min(w, h)
    if horiz >= vert:
        w, h = long_mm, short_mm
    else:
        w, h = short_mm, long_mm
    measured = max(horiz, vert) / max(min(horiz, vert), 1e-9)
    expected = long_mm / short_mm
    ratio = measured / expected
    if not (0.6 <= ratio <= 1.6):
        raise FitError(
            "The card shape in the photo does not match the card size. "
            "Check the 4 corners, or take the photo more from above."
        )
    for i in range(4):  # opposite sides should be of similar length
        a, b = sides[i], sides[(i + 2) % 4]
        if min(a, b) / max(a, b) < 0.5:
            raise FitError("The card looks too tilted. Take the photo more from above, or click the corners again.")

    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    H = cv2.getPerspectiveTransform(c.astype(np.float32), dst)
    return H.astype(np.float64), (w, h)


def _project(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, H).reshape(-1, 2)


def _fit_circle(pts: np.ndarray, name: str) -> tuple[float, float, float, float]:
    """Kasa fit + Gauss-Newton refinement. Returns cx, cy, r, rms (geometric)."""
    if len(pts) < 3:
        raise FitError(f"Please click at least 3 points on the {name} edge.")
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    b = x * x + y * y
    sol, _, rank, sv = np.linalg.lstsq(A, b, rcond=None)
    if rank < 3 or sv[-1] / sv[0] < 1e-9:
        raise FitError(f"The {name} edge points are on a straight line. Please click points spread along the curve.")
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if r2 <= 0:
        raise FitError(f"Could not fit a circle to the {name} edge. Please click the points again.")
    r = math.sqrt(r2)

    for _ in range(10):
        dx, dy = x - cx, y - cy
        d = np.hypot(dx, dy)
        d[d < 1e-12] = 1e-12
        res = d - r
        J = np.column_stack([-dx / d, -dy / d, -np.ones_like(d)])
        step, *_ = np.linalg.lstsq(J, -res, rcond=None)
        cx, cy, r = cx + step[0], cy + step[1], r + step[2]
        if np.linalg.norm(step) < 1e-9:
            break
    r = abs(r)
    rms = float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - r) ** 2)))
    if not all(math.isfinite(v) for v in (cx, cy, r, rms)):
        raise FitError(f"Could not fit a circle to the {name} edge. Please click the points again.")
    return float(cx), float(cy), float(r), rms


def _angles_deg(pts: np.ndarray, cx: float, cy: float) -> np.ndarray:
    """CCW-on-screen angles in [0, 360). See module docstring."""
    a = np.degrees(np.arctan2(-(pts[:, 1] - cy), pts[:, 0] - cx))
    return np.mod(a, 360.0)


def _covered_arc(angles: np.ndarray) -> tuple[float, float, float]:
    """Smallest CCW arc covering all angles. Returns (start, end, span)."""
    a = np.sort(np.mod(angles, 360.0))
    gaps = np.diff(np.concatenate([a, [a[0] + 360.0]]))
    k = int(np.argmax(gaps))  # gap from a[k] to a[k+1] is the missing part
    start = float(a[(k + 1) % len(a)])
    end = float(a[k])
    span = 360.0 - float(gaps[k])
    return round(start, 2) % 360.0, round(end, 2) % 360.0, span


def _circle_mm(cx, cy, r, a0, a1, n=180) -> np.ndarray:
    """Points on a circle from angle a0 to a1 (CCW, degrees, screen convention)."""
    span = (a1 - a0) % 360.0
    if span == 0:
        span = 360.0
    t = np.radians(a0 + np.linspace(0, span, max(2, int(n * span / 360) + 2)))
    return np.column_stack([cx + r * np.cos(t), cy - r * np.sin(t)])


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------

def fit_ring(
    image_bgr: np.ndarray,
    corners_px: list[Pt],
    card_size_mm: tuple[float, float],
    outer_pts_px: list[Pt],
    inner_pts_px: list[Pt],
) -> FitOutput:
    H, (w, h) = _card_homography(corners_px, card_size_mm)

    outer_px = np.asarray(outer_pts_px, dtype=np.float64).reshape(-1, 2)
    inner_px = np.asarray(inner_pts_px, dtype=np.float64).reshape(-1, 2)
    if len(outer_px) < 3:
        raise FitError("Please click at least 3 points on the outer edge.")
    if len(inner_px) < 3:
        raise FitError("Please click at least 3 points on the inner edge.")
    if not (np.all(np.isfinite(outer_px)) and np.all(np.isfinite(inner_px))):
        raise FitError("An edge point is not a valid point. Please click the edge points again.")

    outer_mm = _project(H, outer_px)
    inner_mm = _project(H, inner_px)
    ocx, ocy, orr, orms = _fit_circle(outer_mm, "outer")
    icx, icy, irr, irms = _fit_circle(inner_mm, "inner")

    if irr >= orr:
        raise FitError(
            "The inner circle is not smaller than the outer circle. "
            "Check that outer points are on the outside edge and inner points on the inside edge."
        )

    offset = math.hypot(ocx - icx, ocy - icy)
    rms = max(orms, irms)
    cx, cy = (ocx + icx) / 2, (ocy + icy) / 2
    angles = _angles_deg(np.vstack([outer_mm, inner_mm]), cx, cy)
    start, end, support = _covered_arc(angles)

    warnings: list[str] = []
    if support < 120:
        warnings.append("Surviving arc is short; diameter may be less accurate.")
    if offset > 1.0:
        warnings.append(
            f"Outer and inner circles are {offset:.1f} mm apart (not concentric). Check the edge points."
        )
    if rms > 0.5:
        warnings.append(
            f"Edge points are {rms:.2f} mm away from the fitted circle on average. Some points may be off the edge."
        )

    fit = RingFit(
        outer_diameter_mm=round(2 * orr, 3),
        inner_diameter_mm=round(2 * irr, 3),
        concentric_offset_mm=round(offset, 3),
        rms_residual_mm=round(rms, 4),
        surviving_arc_deg=(start, end),
        missing_arc_deg=(end, start),
        support_deg=round(support, 2),
    )

    overlay = _draw_overlay(
        image_bgr, H, corners_px, outer_px, inner_px,
        (ocx, ocy, orr), (icx, icy, irr), start, end,
    )
    return FitOutput(fit=fit, warnings=warnings, overlay_png=overlay)


def _draw_overlay(img, H, corners_px, outer_px, inner_px, oc, ic, start, end) -> bytes:
    long_side = max(img.shape[:2])
    s = min(1.0, OVERLAY_MAX_SIDE / long_side)
    out = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img.copy()
    Hinv = np.linalg.inv(H)
    lw = max(2, int(round(3 * max(out.shape[:2]) / 1600)))

    def poly(pts_px, color, thick):
        p = np.round(np.asarray(pts_px) * s).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [p], False, color, thick, cv2.LINE_AA)

    quad = np.asarray(corners_px, dtype=np.float64)
    q = np.round(quad * s).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(out, [q], True, (255, 0, 0), lw, cv2.LINE_AA)  # blue

    for cx, cy, r in (oc, ic):
        poly(_project(Hinv, _circle_mm(cx, cy, r, start, end)), (0, 200, 0), lw)          # green
        poly(_project(Hinv, _circle_mm(cx, cy, r, end, start)), (0, 0, 255), lw * 3)      # red

    for pts, color in ((outer_px, (255, 0, 255)), (inner_px, (255, 255, 0))):
        for x, y in pts:
            cv2.circle(out, (int(round(x * s)), int(round(y * s))), lw * 2, color, -1, cv2.LINE_AA)
            cv2.circle(out, (int(round(x * s)), int(round(y * s))), lw * 2, (0, 0, 0), 1, cv2.LINE_AA)

    ok, buf = cv2.imencode(".png", out)
    if not ok:
        raise FitError("Could not draw the result image.")
    return buf.tobytes()


# --------------------------------------------------------------------------
# Automatic first guess (operator corrects it by clicking)
# --------------------------------------------------------------------------

DETECT_MAX_SIDE = 2000  # detection works on a downscaled copy
# HSV ranges (OpenCV: H 0..180). Add a new ring colour here.
CARD_HSV_RANGES = [((95, 20, 60), (135, 255, 255))]  # blue card
RING_HSV_RANGES = {"yellow": ((15, 80, 120), (40, 255, 255))}
RING_COLOR = "yellow"
AUTO_POINTS = 12
END_TRIM_DEG = 8.0


@dataclass
class AutoDetect:
    corners_px: list[Pt] | None
    outer_edge_points_px: list[Pt]
    inner_edge_points_px: list[Pt]
    confidence: Literal["HIGH", "LOW", "NONE"]
    warnings: list[str]


def _kasa(q: np.ndarray) -> tuple[float, float, float]:
    A = np.column_stack([q[:, 0], q[:, 1], np.ones(len(q))])
    b = (q ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = s[0] / 2, s[1] / 2
    return float(cx), float(cy), float(math.sqrt(max(s[2] + cx * cx + cy * cy, 0.0)))


def _hsv_mask(hsv: np.ndarray, ranges) -> np.ndarray:
    m = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in ranges:
        m |= cv2.inRange(hsv, lo, hi)
    return m


def _order_corners(q: np.ndarray) -> np.ndarray:
    """Order 4 points clockwise on screen, starting at top-left (min x+y)."""
    c = q.mean(0)
    ang = np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0])  # y down: increasing = clockwise on screen
    q = q[np.argsort(ang)]
    k = int(np.argmin(q.sum(1)))
    return np.roll(q, -k, axis=0)


def _detect_card(hsv: np.ndarray) -> np.ndarray | None:
    """Card corners (small-image pixels) as the intersections of 4 fitted sides."""
    mask = _hsv_mask(hsv, CARD_HSV_RANGES)
    k = max(3, int(round(max(hsv.shape[:2]) / 160)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    img_area = hsv.shape[0] * hsv.shape[1]
    if cv2.contourArea(c) < 0.01 * img_area:
        return None
    hull = cv2.convexHull(c)
    quad = None
    for eps in (0.02, 0.03, 0.05, 0.08):
        ap = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
        if len(ap) == 4:
            quad = ap.reshape(4, 2).astype(np.float64)
            break
    if quad is None:
        return None
    if cv2.contourArea(c) < 0.85 * cv2.contourArea(quad.astype(np.float32)):
        return None  # not a filled rectangle
    quad = _order_corners(quad)
    pts = c.reshape(-1, 2).astype(np.float64)
    for thr_frac in (0.05, 0.02, 0.012):
        thr = thr_frac * math.sqrt(cv2.contourArea(c))
        lines = []
        for i in range(4):
            a, b = quad[i], quad[(i + 1) % 4]
            d = b - a
            L = np.linalg.norm(d)
            u = d / L
            n = np.array([-u[1], u[0]])
            t = (pts - a) @ u
            sel = (np.abs((pts - a) @ n) < thr) & (t > 0.15 * L) & (t < 0.85 * L)
            if sel.sum() < 5:
                return None
            vx, vy, x0, y0 = cv2.fitLine(pts[sel].astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
            lines.append((np.array([x0, y0]), np.array([vx, vy])))
        new = []
        for i in range(4):
            (p, u), (q, v) = lines[(i - 1) % 4], lines[i]
            A = np.column_stack([u, -v])
            if abs(np.linalg.det(A)) < 1e-6:
                return None
            new.append(p + np.linalg.solve(A, q - p)[0] * u)
        quad = np.array(new)
    sides = [np.linalg.norm(quad[(i + 1) % 4] - quad[i]) for i in range(4)]
    aspect = max(sides) / max(min(sides), 1e-9)
    if not (1.2 < aspect < 2.2):  # ID-1 is 1.586
        return None
    return quad


def _ring_candidate(contour: np.ndarray, shape) -> dict | None:
    """Check if a contour looks like an annulus arc. Returns edge points or None."""
    p = contour.reshape(-1, 2).astype(np.float64)
    h, w = shape
    if p[:, 0].min() <= 1 or p[:, 1].min() <= 1 or p[:, 0].max() >= w - 2 or p[:, 1].max() >= h - 2:
        return None  # cut by the photo border
    hull = cv2.convexHull(p.astype(np.float32)).reshape(-1, 2).astype(np.float64)
    if len(hull) < 5:
        return None
    cx, cy, R = _kasa(hull)
    for _ in range(3):
        r = np.hypot(p[:, 0] - cx, p[:, 1] - cy)
        outer = p[np.abs(r - R) < 0.03 * R]
        if len(outer) < 20:
            return None
        cx, cy, R = _kasa(outer)
    r = np.hypot(outer[:, 0] - cx, outer[:, 1] - cy)
    if np.sqrt(np.mean((r - R) ** 2)) / R > 0.01:
        return None
    # Inner edge: the most common radius well inside the outer edge.
    rr = np.hypot(p[:, 0] - cx, p[:, 1] - cy) / R
    hist, edges = np.histogram(rr, bins=32, range=(0.3, 0.94))
    kb = int(np.argmax(hist))
    peak = (edges[kb] + edges[kb + 1]) / 2
    inner = p[np.abs(rr - peak) < 0.04]
    if len(inner) < 20:
        return None
    icx, icy, iR = _kasa(inner)
    ir = np.hypot(p[:, 0] - icx, p[:, 1] - icy)
    inner = p[np.abs(ir - iR) < 0.025 * iR]
    if len(inner) < 20 or not (0.3 * R < iR < 0.95 * R):
        return None
    ir = np.hypot(inner[:, 0] - icx, inner[:, 1] - icy)
    if np.sqrt(np.mean((ir - iR) ** 2)) / iR > 0.025 or math.hypot(icx - cx, icy - cy) > 0.1 * R:
        return None
    ang_o = np.mod(np.degrees(np.arctan2(-(outer[:, 1] - cy), outer[:, 0] - cx)), 360)
    ang_i = np.mod(np.degrees(np.arctan2(-(inner[:, 1] - cy), inner[:, 0] - cx)), 360)
    s_o, _, span_o = _covered_arc(ang_o)
    s_i, _, span_i = _covered_arc(ang_i)
    if min(span_o, span_i) < 60:
        return None  # a small fragment, not the main arc
    return {"outer": (outer, ang_o, s_o, span_o), "inner": (inner, ang_i, s_i, span_i), "R": R}


def _spread_points(pts, ang, start, span, n) -> np.ndarray:
    rel = np.mod(ang - start, 360)
    lo, hi = END_TRIM_DEG, span - END_TRIM_DEG
    if hi <= lo:
        lo, hi = 0.0, span
    out = []
    for t in np.linspace(lo, hi, n):
        i = int(np.argmin(np.abs(rel - t)))
        if not out or np.min(np.hypot(*(np.array(out) - pts[i]).T)) > 1.0:
            out.append(pts[i])
    return np.array(out)


def auto_detect(image_bgr: np.ndarray) -> AutoDetect:
    """First guess of card corners and ring edge points. Never raises for a normal image.

    Works on a downscaled copy; returned points are in full-size oriented pixels.
    The operator must check and correct the points before the fit is trusted.
    """
    warnings: list[str] = []
    if image_bgr is None or image_bgr.ndim != 3 or image_bgr.size == 0:
        return AutoDetect(None, [], [], "NONE", ["Could not read the photo."])
    s = min(1.0, DETECT_MAX_SIDE / max(image_bgr.shape[:2]))
    small = cv2.resize(image_bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else image_bgr
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

    def full(q):
        return [(round(float(x) / s, 1), round(float(y) / s, 1)) for x, y in q]

    quad = _detect_card(hsv)
    corners = full(quad) if quad is not None else None
    if corners is None:
        warnings.append("Card not found: click its 4 corners.")

    mask = _hsv_mask(hsv, [RING_HSV_RANGES[RING_COLOR]])
    k = max(3, int(round(max(hsv.shape[:2]) / 400)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    min_area = 0.001 * hsv.shape[0] * hsv.shape[1]
    best, best_area = None, 0.0
    for c in cs:
        a = cv2.contourArea(c)
        if a < min_area or a <= best_area:
            continue
        cand = _ring_candidate(c, hsv.shape[:2])
        if cand is not None:
            best, best_area = cand, a

    outer_pts: list[Pt] = []
    inner_pts: list[Pt] = []
    if best is None:
        warnings.append("Ring edge not found: click at least 3 points on the outer edge and 3 on the inner edge.")
    else:
        outer_pts = full(_spread_points(*best["outer"], AUTO_POINTS))
        inner_pts = full(_spread_points(*best["inner"], AUTO_POINTS))
        warnings.append("Edge points are automatic. Check them and move any point that is not on the top edge of the ring.")

    if corners is not None and best is not None and len(outer_pts) >= 8 and len(inner_pts) >= 8:
        conf = "HIGH"
    elif corners is None and best is None:
        conf = "NONE"
    else:
        conf = "LOW"
    return AutoDetect(corners, outer_pts, inner_pts, conf, warnings)
