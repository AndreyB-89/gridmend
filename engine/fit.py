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
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1", b"ftypmsf1"):
        raise FitError("This is an iPhone HEIC photo. Please use JPEG: on the iPhone choose "
                       "Settings > Camera > Formats > Most Compatible, or export the photo as JPEG.")
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
RING_HSV_RANGES = {"yellow": ((17, 80, 120), (40, 255, 255))}  # H 15-16 is the brown PLA rings
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


# Ring detection. The colour mask only gives *seeds*: in a photo taken at an
# angle the ring is an ellipse, the near outer wall is part of the yellow
# outline, and the inner wall hides the real inner edge (the hole in the mask
# is the wall *foot*). The top face is bounded by two circles in one plane with
# one centre, so we search, in a locally rectified frame, for the centre where
# an outer and an inner circle both have edge support all around.

MIN_TILT_RATIO = 0.45  # ring outline minor/major axis below this = side view
EDGE_GRAD_TOL_DEG = 25.0  # edge gradient must point along the radius
COVER_BINS = 72  # 5 degree bins
MAX_EDGE_POINTS = 5000


def _edge_points(small_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Colour-aware edges: yellow on beige has almost no contrast in grey, so use L and b of Lab.

    Returns (points xy, unit gradient xy) for every edge pixel.
    """
    lab = cv2.cvtColor(cv2.GaussianBlur(small_bgr, (5, 5), 0), cv2.COLOR_BGR2LAB)
    L, b = lab[:, :, 0], lab[:, :, 2]
    edges = cv2.Canny(L, 30, 70, L2gradient=True) | cv2.Canny(b, 12, 30, L2gradient=True)
    gx = np.zeros(L.shape, np.float32)
    gy = np.zeros(L.shape, np.float32)
    best = np.zeros(L.shape, np.float32)
    for ch, w in ((L, 1.0), (b, 2.0)):
        sx = cv2.Sobel(ch, cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(ch, cv2.CV_32F, 0, 1, ksize=3)
        mag = w * np.hypot(sx, sy)
        sel = mag > best
        gx[sel], gy[sel], best[sel] = sx[sel], sy[sel], mag[sel]
    ys, xs = np.nonzero(edges)
    g = np.column_stack([gx[ys, xs], gy[ys, xs]]).astype(np.float64)
    g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
    return np.column_stack([xs, ys]).astype(np.float64), g


def _rectifier(H: np.ndarray | None, at: np.ndarray, ellipse) -> np.ndarray:
    """2x2 matrix (det 1) that makes a circle on the table round again near `at`.

    With a card: the local Jacobian of the card homography (shape only, the
    card size does not matter here). Without a card: from the outline ellipse.
    """
    if H is not None:
        x, y = at
        w = H[2, 0] * x + H[2, 1] * y + H[2, 2]
        u = (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / w
        v = (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / w
        J = np.array([[H[0, 0] - u * H[2, 0], H[0, 1] - u * H[2, 1]],
                      [H[1, 0] - v * H[2, 0], H[1, 1] - v * H[2, 1]]]) / w
    elif ellipse is not None:
        (_, _), (ew, eh), ang = ellipse
        t = math.radians(ang)
        R = np.array([[math.cos(t), math.sin(t)], [-math.sin(t), math.cos(t)]])  # image -> ellipse axes
        J = np.diag([1 / max(ew, 1e-9), 1 / max(eh, 1e-9)]) @ R
    else:
        return np.eye(2)
    d = abs(np.linalg.det(J))
    return J / math.sqrt(d) if d > 1e-12 else np.eye(2)


def _coverage(q: np.ndarray, g: np.ndarray, c: np.ndarray, width: float, nbins: int) -> tuple[np.ndarray, np.ndarray]:
    """Per radius bin: (sectors with a radial edge point, sharpness).

    Sharpness counts edge points per sector (capped, so one long straight edge
    cannot win). A true circle around `c` puts its points in one or two bins;
    a circle around the wrong centre, or the mixed outline of top and foot, is
    smeared over many bins and scores lower.
    """
    d = q - c
    r = np.hypot(d[:, 0], d[:, 1])
    radial = np.abs((d * g).sum(1)) > math.cos(math.radians(EDGE_GRAD_TOL_DEG)) * np.maximum(r, 1e-9)
    k = (r / width).astype(np.int64)
    ok = radial & (k < nbins)
    a = ((np.arctan2(d[ok, 1], d[ok, 0]) + math.pi) / (2 * math.pi) * COVER_BINS).astype(np.int64) % COVER_BINS
    cnt = np.zeros((nbins + 1, COVER_BINS), np.int32)
    np.add.at(cnt, (k[ok], a), 1)
    pair = cnt[:-1] + cnt[1:]  # an edge may fall in either of two neighbour bins
    return (pair > 0).sum(1), np.minimum(pair, 6).sum(1)


def _pick_circles(cov: np.ndarray, width: float, rmax: float) -> tuple[int, int] | None:
    """Outer = the largest well-covered radius. Inner = the smallest well-covered radius inside it.

    The bore is the innermost circle seen all around; a step on the top face is
    also a full circle but larger; the wall foot is only seen on one side.
    """
    lo = int(0.2 * rmax / width)
    if lo >= len(cov) or cov[lo:].max() < COVER_BINS // 4:
        return None
    top = cov[lo:].max()
    good_o = np.nonzero(cov >= 0.75 * top)[0]
    good_o = good_o[good_o >= lo]
    ko = int(good_o.max())
    band = np.arange(int(0.3 * ko), int(0.93 * ko))
    if len(band) == 0:
        return ko, -1
    need = max(COVER_BINS // 4, 0.7 * cov[ko])
    good_i = band[cov[band] >= need]
    return ko, (int(good_i.min()) if len(good_i) else -1)


def _search_ring(pts, grads, seed: np.ndarray, A: np.ndarray, rmax: float) -> dict | None:
    """Grid search of the top-face centre around `seed`. Works in the rectified frame q = A (p - seed)."""
    q = (pts - seed) @ A.T
    gq = grads @ np.linalg.inv(A)  # gradients are covectors
    gq /= np.maximum(np.linalg.norm(gq, axis=1, keepdims=True), 1e-9)
    near = np.hypot(q[:, 0], q[:, 1]) < 1.35 * rmax
    q, gq = q[near], gq[near]
    if len(q) < 40:
        return None
    if len(q) > MAX_EDGE_POINTS:
        idx = np.random.default_rng(0).choice(len(q), MAX_EDGE_POINTS, replace=False)
        q, gq = q[idx], gq[idx]
    width = max(1.0, 0.007 * rmax)
    nbins = int(1.3 * rmax / width) + 2

    def score_at(c):
        cov, sharp = _coverage(q, gq, c, width, nbins)
        pick = _pick_circles(cov, width, rmax)
        if pick is None:
            return -1, None
        ko, ki = pick
        return sharp[ko] + (sharp[ki] if ki >= 0 else 0), (ko, ki, cov)

    best = (-1, None, None)
    step = rmax / 16
    for dx in np.arange(-0.35, 0.3501, 1 / 16) * rmax:
        for dy in np.arange(-0.35, 0.3501, 1 / 16) * rmax:
            c = np.array([dx, dy])
            s, info = score_at(c)
            if s > best[0]:
                best = (s, info, c)
    if best[1] is None:
        return None
    for _ in range(2):  # refine
        step /= 4
        c0 = best[2]
        for dx in np.arange(-2, 2.01) * step:
            for dy in np.arange(-2, 2.01) * step:
                c = c0 + (dx, dy)
                s, info = score_at(c)
                if s > best[0]:
                    best = (s, info, c)
    _, (ko, ki, cov), c = best

    def inliers(k):
        d = q - c
        r = np.hypot(d[:, 0], d[:, 1])
        radial = np.abs((d * gq).sum(1)) > math.cos(math.radians(EDGE_GRAD_TOL_DEG)) * np.maximum(r, 1e-9)
        return q[radial & (np.abs(r - (k + 0.5) * width) <= 1.5 * width)]

    out_q = inliers(ko)
    if len(out_q) < 20:
        return None
    ocx, ocy, oR = _kasa(out_q)
    res = {"centre_q": np.array([ocx, ocy]), "R": oR, "cov_o": int(cov[ko]), "cov_i": 0, "outer_q": out_q, "inner_q": None}
    if ki >= 0:
        in_q = inliers(ki)
        if len(in_q) >= 20:
            icx, icy, iR = _kasa(in_q)
            if math.hypot(icx - ocx, icy - ocy) < 0.1 * oR and 0.25 * oR < iR < 0.95 * oR:
                res.update(inner_q=in_q, cov_i=int(cov[ki]))
    Ainv = np.linalg.inv(A)
    res["to_px"] = lambda qq: qq @ Ainv.T + seed
    return res


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


def _edge_sample(q: np.ndarray, centre_q: np.ndarray, to_px) -> np.ndarray:
    ang = np.mod(np.degrees(np.arctan2(-(q[:, 1] - centre_q[1]), q[:, 0] - centre_q[0])), 360)
    start, _, span = _covered_arc(ang)
    return to_px(_spread_points(q, ang, start, span, AUTO_POINTS))


def _seeds(mask: np.ndarray, H: np.ndarray | None) -> tuple[list, bool, bool]:
    """Seeds (centre px, rectifier, search radius) from the colour mask.

    Every hole is a seed (so touching rings split), and every blob is a seed
    (a broken 'C' has no hole). Returns (seeds, cut_by_border, side_view).
    """
    h, w = mask.shape
    cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    min_area = 0.001 * h * w
    seeds, cut, side = [], False, False
    for idx, c in enumerate(cs):
        if hier[0][idx][3] != -1:
            continue
        area = cv2.contourArea(c)
        if area < min_area or len(c) < 5:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
            cut = True
            continue
        hull = cv2.convexHull(c)
        ell = cv2.fitEllipse(hull) if len(hull) >= 5 else cv2.fitEllipse(c)
        ratio = min(ell[1]) / max(max(ell[1]), 1e-9)
        holes = [cs[j] for j in range(len(cs)) if hier[0][j][3] == idx and cv2.contourArea(cs[j]) > 0.01 * area]
        if ratio < MIN_TILT_RATIO and len(holes) <= 1:
            side = True
            continue
        centre = np.array(ell[0], np.float64)
        A = _rectifier(H, centre, ell)
        # Search radius in the rectified frame: the rectified outline size.
        hq = (hull.reshape(-1, 2) - centre) @ A.T
        rmax = 1.1 * float(np.max(np.hypot(hq[:, 0], hq[:, 1])))
        seeds.append((centre, A, rmax))
        for hole in holes:
            if len(hole) < 5:
                continue
            he = cv2.fitEllipse(hole)
            hc = np.array(he[0], np.float64)
            Ah = _rectifier(H, hc, he if H is None else None)
            qq = (hole.reshape(-1, 2) - hc) @ Ah.T
            r_hole = float(np.max(np.hypot(qq[:, 0], qq[:, 1])))
            if len(holes) > 1 or hier[0][idx][2] != -1:
                seeds.append((hc, Ah, min(3.2 * r_hole, rmax)))
    return seeds, cut, side


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
    H = None
    if quad is not None:
        try:  # ID-1 proportions: used for the shape of circles only, never for sizes
            H, _ = _card_homography([tuple(p) for p in quad], (85.6, 53.98))
        except FitError:
            H = None

    mask = _hsv_mask(hsv, [RING_HSV_RANGES[RING_COLOR]])
    k = max(3, int(round(max(hsv.shape[:2]) / 400)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    seeds, cut, side = _seeds(mask, H)

    rings: list[dict] = []
    if seeds:
        pts, grads = _edge_points(small)
        near = cv2.dilate(mask, np.ones((2 * k + 1, 2 * k + 1), np.uint8))[pts[:, 1].astype(int), pts[:, 0].astype(int)] > 0
        pts, grads = pts[near], grads[near]
        for centre, A, rmax in seeds:
            r = _search_ring(pts, grads, centre, A, rmax)
            if r is None:
                continue
            # Too little of a circle is not a ring: side views and pieces in the hand give short arcs.
            if r["inner_q"] is None and r["cov_o"] < 0.75 * COVER_BINS:
                continue
            if r["cov_o"] < 110 / 360 * COVER_BINS or (r["inner_q"] is not None and r["cov_i"] < 100 / 360 * COVER_BINS):
                continue
            r["centre_px"] = r["to_px"](r["centre_q"][None])[0]
            r["score"] = r["cov_o"] + r["cov_i"]
            rings.append(r)
    # One ring per place: keep the best-scoring candidate within a ring radius.
    uniq: list[dict] = []
    for r in sorted(rings, key=lambda r: -r["score"]):
        if all(np.hypot(*(r["centre_px"] - u["centre_px"])) > 0.5 * r["R"] for u in uniq):
            uniq.append(r)
    both = [r for r in uniq if r["inner_q"] is not None]

    outer_pts: list[Pt] = []
    inner_pts: list[Pt] = []
    chosen = None
    if uniq:
        pool = both or uniq
        broken = [r for r in pool if r["cov_o"] < 0.85 * COVER_BINS]
        chosen = max(broken or pool, key=lambda r: r["score"])
        outer_pts = full(_edge_sample(chosen["outer_q"], chosen["centre_q"], chosen["to_px"]))
        if chosen["inner_q"] is not None:
            inner_pts = full(_edge_sample(chosen["inner_q"], chosen["centre_q"], chosen["to_px"]))
        if len(uniq) > 1:
            which = "the one that looks broken" if broken else "the clearest one"
            warnings.append(f"I found {len(uniq)} rings and picked {which}. If it is the wrong ring, move the points.")

    if corners is None:
        warnings.append("Card not found. Put the card flat on the table next to the ring, or click its 4 corners.")
    if chosen is None:
        if side:
            warnings.append("The photo looks like it is taken from the side. Take it from above, with the card flat next to the ring.")
        elif cut:
            warnings.append("The ring touches the edge of the photo. Take the photo with the whole ring in view.")
        else:
            warnings.append(
                "Ring not found. Take the photo from above, with the whole ring in view. "
                "Or click 3 points on the outer edge and 3 on the inner edge."
            )
    elif not inner_pts:
        warnings.append("I found the outer edge only. Click 3 points on the inner edge: the top edge of the hole.")
    else:
        warnings.append("Edge points are automatic. Check them and move any point that is not on the top edge of the ring.")

    if corners is not None and len(outer_pts) >= 8 and len(inner_pts) >= 8:
        conf = "HIGH"
    elif corners is None and chosen is None:
        conf = "NONE"
    else:
        conf = "LOW"
    return AutoDetect(corners, outer_pts, inner_pts, conf, warnings)
