import { useEffect, useMemo, useRef, useState } from "react";
import type { Point } from "../types.ts";

export type ClickSet = "corners" | "outer" | "inner";

export interface Clicks {
  corners: Point[];
  outer: Point[];
  inner: Point[];
}

export const SET_COLORS: Record<ClickSet, string> = {
  corners: "#2F7DF6",
  outer: "#FFD21F",
  inner: "#E63B2E",
};

export const SET_LABEL: Record<ClickSet, string> = {
  corners: "Card",
  outer: "Outer",
  inner: "Inner",
};

const CORNER_LABELS = ["1", "2", "3", "4"];

interface Props {
  photoUrl: string;
  overlayUrl: string | null;
  showOverlay: boolean;
  clicks: Clicks;
  activeSet: ClickSet;
  wholePhoto: boolean;
  onAddPoint: (p: Point) => void;
  onMovePoint: (set: ClickSet, index: number, p: Point) => void;
  onRemovePoint: (set: ClickSet, index: number) => void;
  onDragStart: () => void;
}

/** Algebraic circle fit in pixels, only to frame the view. The real fit runs on the server. */
function circleFit(pts: Point[]): { x: number; y: number; r: number } | null {
  if (pts.length < 3) return null;
  let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0, sz = 0, sxz = 0, syz = 0;
  for (const [x, y] of pts) {
    const z = x * x + y * y;
    sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; sz += z; sxz += x * z; syz += y * z;
  }
  const n = pts.length;
  // Solve [sxx sxy sx; sxy syy sy; sx sy n] [a b c] = [sxz syz sz]
  const m = [
    [sxx, sxy, sx, sxz],
    [sxy, syy, sy, syz],
    [sx, sy, n, sz],
  ];
  for (let i = 0; i < 3; i++) {
    let p = i;
    for (let k = i + 1; k < 3; k++) if (Math.abs(m[k][i]) > Math.abs(m[p][i])) p = k;
    [m[i], m[p]] = [m[p], m[i]];
    if (Math.abs(m[i][i]) < 1e-9) return null;
    for (let k = 0; k < 3; k++) {
      if (k === i) continue;
      const f = m[k][i] / m[i][i];
      for (let j = i; j < 4; j++) m[k][j] -= f * m[i][j];
    }
  }
  const A = m[0][3] / m[0][0], B = m[1][3] / m[1][1], C = m[2][3] / m[2][2];
  const x = A / 2, y = B / 2;
  const r2 = C + x * x + y * y;
  return r2 > 0 ? { x, y, r: Math.sqrt(r2) } : null;
}

/** Photo with the detected points in natural image pixels. Points can be dragged and nudged with arrow keys. */
export function PhotoCanvas({
  photoUrl,
  overlayUrl,
  showOverlay,
  clicks,
  activeSet,
  wholePhoto,
  onAddPoint,
  onMovePoint,
  onRemovePoint,
  onDragStart,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const dragRef = useRef<{ set: ClickSet; i: number; moved: boolean } | null>(null);

  useEffect(() => {
    setNatural(null);
    const img = new Image();
    img.onload = () => setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    img.src = photoUrl;
  }, [photoUrl]);

  // Zoom to the points (card + ring) so the ring is large enough to edit.
  const viewBox = useMemo(() => {
    if (!natural) return "0 0 1 1";
    // Card corners: show card and ring. Edge points: zoom to the ring so each point is easy to grab.
    const ring = [...clicks.outer, ...clicks.inner];
    const all = activeSet === "corners" || ring.length < 3 ? [...clicks.corners, ...ring] : ring;
    if (wholePhoto || all.length < 3) return `0 0 ${natural.w} ${natural.h}`;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of all) {
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    }
    // For the ring, frame the whole fitted circle (display only), so the missing arc is visible too.
    const c = all === ring ? circleFit(clicks.outer) : null;
    if (c && c.r > 0 && c.r < Math.max(natural.w, natural.h)) {
      x0 = Math.min(x0, c.x - c.r); x1 = Math.max(x1, c.x + c.r);
      y0 = Math.min(y0, c.y - c.r); y1 = Math.max(y1, c.y + c.r);
    }
    const pad = Math.max(x1 - x0, y1 - y0) * 0.18 + natural.w * 0.015;
    x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
    x1 = Math.min(natural.w, x1 + pad); y1 = Math.min(natural.h, y1 + pad);
    return `${x0} ${y0} ${x1 - x0} ${y1 - y0}`;
    // Recompute only when points are added or removed, not on every drag step.
  }, [natural, wholePhoto, activeSet, clicks.corners.length, clicks.outer.length, clicks.inner.length, photoUrl]);

  const vbSize = useMemo(() => {
    const p = viewBox.split(" ").map(Number);
    return Math.max(p[2], p[3]);
  }, [viewBox]);

  const toNatural = (clientX: number, clientY: number): Point | null => {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm || !natural) return null;
    const pt = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    const x = Math.min(natural.w, Math.max(0, pt.x));
    const y = Math.min(natural.h, Math.max(0, pt.y));
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
  };

  if (!natural) {
    return <div className="photo-canvas loading">Loading photo…</div>;
  }

  const r = vbSize / 70;
  const sw = r / 3.2;
  const editable = !(showOverlay && overlayUrl);

  const renderSet = (set: ClickSet, pts: Point[]) =>
    pts.map((p, i) => (
      <g
        key={`${set}-${i}`}
        className="pt"
        tabIndex={editable ? 0 : -1}
        role="button"
        aria-label={`${SET_LABEL[set]} ${set === "corners" ? "corner" : "edge"} point ${i + 1} at ${Math.round(p[0])}, ${Math.round(p[1])}. Drag or use the arrow keys to move. Delete removes it.`}
        onPointerDown={(e) => {
          if (!editable) return;
          e.stopPropagation();
          (e.currentTarget as Element).setPointerCapture(e.pointerId);
          dragRef.current = { set, i, moved: false };
          onDragStart();
        }}
        onPointerMove={(e) => {
          const d = dragRef.current;
          if (!d || d.set !== set || d.i !== i) return;
          const q = toNatural(e.clientX, e.clientY);
          if (q) {
            d.moved = true;
            onMovePoint(set, i, q);
          }
        }}
        onPointerUp={() => {
          dragRef.current = null;
        }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          const step = e.shiftKey ? 12 : 3;
          const k = e.key;
          const dx = k === "ArrowLeft" ? -step : k === "ArrowRight" ? step : 0;
          const dy = k === "ArrowUp" ? -step : k === "ArrowDown" ? step : 0;
          if (dx || dy) {
            e.preventDefault();
            onMovePoint(set, i, [Math.round((p[0] + dx) * 10) / 10, Math.round((p[1] + dy) * 10) / 10]);
          } else if (k === "Delete" || k === "Backspace") {
            e.preventDefault();
            onRemovePoint(set, i);
          }
        }}
      >
        <circle className="hit" cx={p[0]} cy={p[1]} r={r * 1.9} fill="transparent" />
        <circle cx={p[0]} cy={p[1]} r={r} fill={SET_COLORS[set]} fillOpacity={0.35} stroke="#22252B" strokeWidth={sw * 1.8} />
        <circle cx={p[0]} cy={p[1]} r={r} fill="none" stroke="#fff" strokeWidth={sw} />
        <circle cx={p[0]} cy={p[1]} r={r / 4} fill={SET_COLORS[set]} stroke="#22252B" strokeWidth={sw / 2} />
        {set === "corners" && (
          <text x={p[0] + r * 1.3} y={p[1] - r * 1.2} fontSize={r * 1.9} fontWeight={800} fill="#fff" stroke="#22252B" strokeWidth={sw * 1.6} paintOrder="stroke">
            {CORNER_LABELS[i]}
          </text>
        )}
      </g>
    ));

  return (
    <div className={`photo-canvas ${editable ? "editable" : ""} set-${activeSet}`}>
      <svg
        ref={svgRef}
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={editable ? "Photo with detected points. Click the photo to add a point." : "Photo with the fitted circles. The missing arc is red."}
        onClick={(e) => {
          if (!editable) return;
          const q = toNatural(e.clientX, e.clientY);
          if (q) onAddPoint(q);
        }}
      >
        <image href={photoUrl} x={0} y={0} width={natural.w} height={natural.h} preserveAspectRatio="none" />
        {showOverlay && overlayUrl && (
          <image href={overlayUrl} x={0} y={0} width={natural.w} height={natural.h} preserveAspectRatio="none" />
        )}
        {editable && (
          <>
            {clicks.corners.length >= 2 && (
              <polygon
                points={clicks.corners.map((p) => p.join(",")).join(" ")}
                fill={clicks.corners.length === 4 ? "rgba(47,125,246,0.14)" : "none"}
                stroke={SET_COLORS.corners}
                strokeWidth={sw * 1.4}
                strokeDasharray={clicks.corners.length === 4 ? undefined : `${r} ${r}`}
              />
            )}
            {renderSet("corners", clicks.corners)}
            {renderSet("outer", clicks.outer)}
            {renderSet("inner", clicks.inner)}
          </>
        )}
      </svg>
    </div>
  );
}
