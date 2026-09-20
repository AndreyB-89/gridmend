// Run: node --experimental-strip-types --test web/tests/partMode.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { isShapePart, missingFor, shapeSummary } from "../src/partMode.ts";
import type { GenerateRequest, PartShape } from "../src/types.ts";

const D = (v: number | null, confirmed = false) => ({ value_mm: v, source: v === null ? null : ("PHOTO" as const), confirmed });
const SHAPE: PartShape = {
  outline_mm: [[0, 0], [60, 0], [60, 40], [0, 40]],
  holes_mm: [],
  length_mm: 60,
  width_mm: 40,
  confidence: "HIGH",
};
const req = (over: Partial<GenerateRequest> = {}): GenerateRequest => ({
  shape: null,
  outer_diameter: D(null),
  inner_diameter: D(null),
  thickness: D(null),
  groove: null,
  profile_rz_mm: null,
  profile_basis: "SIMPLIFIED_RECTANGLE",
  profile_confirmed: false,
  missing_arc_deg: null,
  purpose: "DEMO_CAD_ONLY",
  ...over,
});

test("a ring (no shape) still needs three diameters and the profile", () => {
  assert.equal(isShapePart(req()), false);
  assert.deepEqual(missingFor(req()), ["outer diameter", "inner diameter", "thickness", "profile"]);
});

test("a shape part needs only the thickness and the outline", () => {
  const a = req({ shape: SHAPE });
  assert.equal(isShapePart(a), true);
  assert.deepEqual(missingFor(a), ["thickness", "outline"]);
});

test("a shape part with both answers is ready to build", () => {
  const a = req({ shape: SHAPE, thickness: D(6, true), profile_confirmed: true });
  assert.deepEqual(missingFor(a), []);
});

test("a diameter the operator never gave is not asked for on a shape part", () => {
  const a = req({ shape: SHAPE, thickness: D(6, true) });
  assert.ok(!missingFor(a).some((m) => m.includes("diameter")));
});

test("an unconfirmed thickness still counts as missing", () => {
  const a = req({ shape: SHAPE, thickness: D(6, false), profile_confirmed: true });
  assert.deepEqual(missingFor(a), ["thickness"]);
});

test("the summary reads the sizes the detector measured", () => {
  assert.equal(shapeSummary(SHAPE), "60.0 by 40.0 mm, no hole");
});

test("the summary counts the holes", () => {
  const two = { ...SHAPE, holes_mm: [SHAPE.outline_mm, SHAPE.outline_mm] };
  assert.equal(shapeSummary(two), "60.0 by 40.0 mm, 2 holes");
  const one = { ...SHAPE, holes_mm: [SHAPE.outline_mm] };
  assert.equal(shapeSummary(one), "60.0 by 40.0 mm, 1 hole");
});

test("no shape means no summary", () => {
  assert.equal(shapeSummary(null), null);
});
