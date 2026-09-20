export type ValState = "ok" | "draft" | "unknown";

export interface SectionVal {
  value: number | null;
  state: ValState;
}

export interface SectionGroove {
  depth: number | null;
  width: number | null;
  state: ValState;
}

interface Props {
  wall: SectionVal;
  thickness: SectionVal;
  /** null = no groove (plain rectangle). */
  groove: SectionGroove | null;
  grooveKnown: boolean;
  profileConfirmed: boolean;
}

const fmt = (v: number | null) => (v === null ? "?" : v.toFixed(v >= 10 ? 1 : 2).replace(/0$/, ""));

function HDim({ x1, x2, y, yFrom, label, state, labelAt }: { x1: number; x2: number; y: number; yFrom: number; label: string; state: ValState; labelAt?: "mid" | "end" }) {
  const a = 7;
  const mid = (x1 + x2) / 2;
  const lx = labelAt === "end" ? x2 + 8 : mid;
  return (
    <g className={`sdim ${state}`}>
      <line className="ext" x1={x1} y1={yFrom} x2={x1} y2={y + (y < yFrom ? -5 : 5)} />
      <line className="ext" x1={x2} y1={yFrom} x2={x2} y2={y + (y < yFrom ? -5 : 5)} />
      <line x1={x1} y1={y} x2={x2} y2={y} />
      <path className="arr" d={`M${x1} ${y} l${a} -3.5 v7z`} />
      <path className="arr" d={`M${x2} ${y} l${-a} -3.5 v7z`} />
      <text x={lx} y={y + 5.5} textAnchor={labelAt === "end" ? "start" : "middle"}>
        {label}
      </text>
    </g>
  );
}

function VDim({ y1, y2, x, xFrom, label, state }: { y1: number; y2: number; x: number; xFrom: number; label: string; state: ValState }) {
  const a = 7;
  const mid = (y1 + y2) / 2;
  const dir = x < xFrom ? -5 : 5;
  return (
    <g className={`sdim ${state}`}>
      <line className="ext" x1={xFrom} y1={y1} x2={x + dir} y2={y1} />
      <line className="ext" x1={xFrom} y1={y2} x2={x + dir} y2={y2} />
      <line x1={x} y1={y1} x2={x} y2={y2} />
      <path className="arr" d={`M${x} ${y1} l-3.5 ${a} h7z`} />
      <path className="arr" d={`M${x} ${y2} l-3.5 ${-a} h7z`} />
      <text x={x} y={mid + 5.5} textAnchor="middle">
        {label}
      </text>
    </g>
  );
}

/** Live cross-section of the ring wall. Solid = confirmed, dashed = draft or unconfirmed, "?" = unknown. */
export function SectionView({ wall, thickness, groove, grooveKnown, profileConfirmed }: Props) {
  // Proportions only; unknown values are drawn at a neutral size and labelled "?".
  const W = wall.value ?? 6;
  const T = thickness.value ?? 6;
  const s = Math.min(150 / W, 104 / T);
  const x0 = 104;
  const x1 = x0 + W * s;
  const yc = 104;
  const y0 = yc - (T * s) / 2;
  const y1 = yc + (T * s) / 2;

  let notch: { d: number; w: number } | null = null;
  if (groove) {
    const gd = Math.min((groove.depth ?? 1) * s, (x1 - x0) * 0.8);
    const gw = Math.min((groove.width ?? 2) * s, (y1 - y0) * 0.8);
    notch = { d: gd, w: gw };
  }
  const path = notch
    ? `M${x0} ${y0} H${x1} V${y1} H${x0} V${yc + notch.w / 2} H${x0 + notch.d} V${yc - notch.w / 2} H${x0} Z`
    : `M${x0} ${y0} H${x1} V${y1} H${x0} Z`;
  const outlineState: ValState = wall.state === "ok" && thickness.state === "ok" ? "ok" : wall.value === null || thickness.value === null ? "unknown" : "draft";

  const desc = [
    `Wall ${wall.value === null ? "unknown" : `${fmt(wall.value)} mm`}`,
    `thickness ${thickness.value === null ? "unknown" : `${fmt(thickness.value)} mm`}`,
    groove ? `inner groove ${fmt(groove.depth)} by ${fmt(groove.width)} mm` : grooveKnown ? "no groove" : "groove not known yet",
  ].join(", ");

  return (
    <figure className="section">
      <figcaption>
        <span>
          <b>Section A–A</b>, ring wall
        </span>
        <span className={`sec-state ${profileConfirmed ? "ok" : "draft"}`}>{profileConfirmed ? "Profile confirmed" : "Profile not confirmed"}</span>
      </figcaption>
      <svg viewBox="0 0 340 200" role="img" aria-label={`Cross-section of the ring wall. ${desc}.`}>
        <defs>
          <pattern id="sec-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="#FFF1B8" />
            <line x1="0" y1="0" x2="0" y2="8" stroke="#22252B" strokeWidth="1.1" />
          </pattern>
        </defs>
        <line className="axis" x1="16" y1="14" x2="16" y2="186" />
        <text className="axis-t" x="22" y="190">
          ring axis
        </text>
        <path d={path} fill="url(#sec-hatch)" className={`outline ${outlineState}`} />
        {notch && groove && groove.state !== "ok" && (
          <path
            className="notch-draft"
            d={`M${x0} ${yc + notch.w / 2} H${x0 + notch.d} V${yc - notch.w / 2} H${x0}`}
          />
        )}
        <HDim x1={x0} x2={x1} y={y0 - 22} yFrom={y0 - 4} label={fmt(wall.value)} state={wall.state} />
        <VDim y1={y0} y2={y1} x={x1 + 30} xFrom={x1 + 4} label={fmt(thickness.value)} state={thickness.state} />
        {notch && groove && (
          <>
            <VDim y1={yc - notch.w / 2} y2={yc + notch.w / 2} x={x0 - 34} xFrom={x0 - 4} label={fmt(groove.width)} state={groove.state} />
            <HDim x1={x0} x2={x0 + notch.d} y={y1 + 22} yFrom={yc + notch.w / 2 + 4} label={`${fmt(groove.depth)} deep`} state={groove.state} labelAt="end" />
          </>
        )}
        {!groove && (
          <text className="note" x={x0 + (x1 - x0) / 2} y={y1 + 30} textAnchor="middle">
            {grooveKnown ? "No groove, plain rectangle" : "Groove: not known yet"}
          </text>
        )}
      </svg>
    </figure>
  );
}
