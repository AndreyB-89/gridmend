// A ring is one shape among many. When the photo gave a traced outline, the app
// builds that outline and asks only what a photo cannot show: the thickness.
// When there is no outline, the old ring path runs, with its three diameters,
// its groove and its missing arc.
import type { GenerateRequest, PartShape } from "./types.ts";

/** True when this part will be built from its traced outline, not from the ring template. */
export function isShapePart(a: GenerateRequest): boolean {
  return a.shape !== null;
}

/** What the operator still has to confirm before anything can be built. */
export function missingFor(a: GenerateRequest): string[] {
  const missing: string[] = [];
  if (isShapePart(a)) {
    if (!(a.thickness.confirmed && a.thickness.value_mm !== null)) missing.push("thickness");
    if (!a.profile_confirmed) missing.push("outline");
    return missing;
  }
  const labels = [
    ["outer diameter", a.outer_diameter],
    ["inner diameter", a.inner_diameter],
    ["thickness", a.thickness],
  ] as const;
  for (const [label, d] of labels) if (!(d.confirmed && d.value_mm !== null)) missing.push(label);
  if (!a.profile_confirmed) missing.push("profile");
  return missing;
}

/** One short line for the operator: the sizes the detector measured. */
export function shapeSummary(shape: PartShape | null): string | null {
  if (shape === null) return null;
  const n = shape.holes_mm.length;
  const holes = n === 0 ? "no hole" : n === 1 ? "1 hole" : `${n} holes`;
  return `${shape.length_mm.toFixed(1)} by ${shape.width_mm.toFixed(1)} mm, ${holes}`;
}
