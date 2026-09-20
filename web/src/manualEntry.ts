// A number typed into the size table becomes a draft, like a spoken edit.
// It is never confirmed here: the operator still presses Confirm (hard rule 1).
import type { GenerateRequest, ProfileEditResult, ProfileFeature } from "./types.ts";

export type DimKey = "outer_diameter" | "inner_diameter" | "thickness";

const LABEL: Record<DimKey, string> = {
  outer_diameter: "Outer diameter",
  inner_diameter: "Inner diameter",
  thickness: "Thickness",
};
const FEATURE: Record<DimKey, ProfileFeature> = {
  outer_diameter: "OUTER_DIAMETER",
  inner_diameter: "INNER_DIAMETER",
  thickness: "THICKNESS",
};
const MAX_MM = 1000;

/** "6.5", "6,5", ".8", "6.5 mm" → number; anything else → null. */
export function parseMm(text: string): number | null {
  const m = /^\s*(\d+(?:[.,]\d+)?|[.,]\d+)\s*(?:mm)?\s*$/i.exec(text);
  if (!m) return null;
  return Number(m[1].replace(",", "."));
}

export type ManualResult =
  | { kind: "empty" }
  | { kind: "same" }
  | { kind: "error"; message: string }
  | { kind: "ok"; res: ProfileEditResult };

function fmt(v: number) {
  return `${Number(v.toFixed(2))} mm`;
}

/** `shown` = values the table shows now (e.g. an unconfirmed photo value), used for the checks. */
export function manualEdit(
  accepted: GenerateRequest,
  key: DimKey,
  text: string,
  shown: Partial<Record<DimKey, number | null>>,
): ManualResult {
  if (!text.trim()) return { kind: "empty" };
  const v = parseMm(text);
  if (v === null) return { kind: "error", message: "Type a number in millimetres, for example 6.5." };
  if (v <= 0) return { kind: "error", message: "The size must be more than 0 mm." };
  if (v >= MAX_MM) return { kind: "error", message: `The size must be less than ${MAX_MM} mm.` };

  const now = accepted[key];
  if (now.confirmed && now.value_mm === v && now.source === "MANUAL_MEASUREMENT") return { kind: "same" };

  const val = (k: DimKey) => (k === key ? v : (accepted[k].value_mm ?? shown[k] ?? null));
  const od = val("outer_diameter");
  const id = val("inner_diameter");
  const th = val("thickness");
  if (od !== null && id !== null && id >= od) {
    return { kind: "error", message: `The inner diameter (${fmt(id)}) must be smaller than the outer diameter (${fmt(od)}).` };
  }
  const g = accepted.groove;
  if (g && od !== null && id !== null && g.depth_mm >= (od - id) / 2) {
    return { kind: "error", message: `The groove (${fmt(g.depth_mm)} deep) would be deeper than the wall (${fmt((od - id) / 2)}).` };
  }
  if (g && th !== null && g.width_mm >= th) {
    return { kind: "error", message: `The groove (${fmt(g.width_mm)} wide) would be wider than the thickness (${fmt(th)}).` };
  }

  const candidate: GenerateRequest = {
    ...accepted,
    [key]: { value_mm: v, source: "MANUAL_MEASUREMENT", confirmed: false },
  };
  const was = now.value_mm === null ? "unknown" : fmt(now.value_mm);
  return {
    kind: "ok",
    res: {
      feature: FEATURE[key],
      candidate,
      readback: `${LABEL[key]}: ${was} → ${fmt(v)} (typed by you).`,
      question: null,
      limitations: [],
      trace: { provider: "LOCAL", model: "manual-entry", mode: "LIVE", latency_ms: 0, request_id: null },
    },
  };
}
