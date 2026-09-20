// Run: node --experimental-strip-types --test web/tests/manualEntry.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { manualEdit, parseMm } from "../src/manualEntry.ts";

const D = (v: number | null, confirmed = false, source: any = v === null ? null : "PHOTO") => ({ value_mm: v, source, confirmed });
const base = (od: number | null, id: number | null, th: number | null = null, groove: any = null) => ({
  outer_diameter: D(od, od !== null),
  inner_diameter: D(id, id !== null),
  thickness: D(th, th !== null),
  groove,
  profile_rz_mm: null,
  profile_basis: "SIMPLIFIED_RECTANGLE" as const,
  profile_confirmed: false,
  missing_arc_deg: null,
  purpose: "DEMO_CAD_ONLY" as const,
});

test("parseMm accepts dot, comma, unit, spaces", () => {
  assert.equal(parseMm("6.5"), 6.5);
  assert.equal(parseMm(" 6,5 "), 6.5);
  assert.equal(parseMm("6.5 mm"), 6.5);
  assert.equal(parseMm("6.5mm"), 6.5);
  assert.equal(parseMm(".8"), 0.8);
  assert.equal(parseMm("41"), 41);
});

test("parseMm rejects junk", () => {
  for (const s of ["", "  ", "abc", "6.5 cm", "6..5", "1e3", "-3", "6 7", "six"]) assert.equal(parseMm(s), null, s);
});

test("empty box is no change", () => {
  const r = manualEdit(base(42, 30), "thickness", "   ", {});
  assert.equal(r.kind, "empty");
});

test("typed thickness makes an unconfirmed MANUAL candidate", () => {
  const acc = base(42, 30);
  const r = manualEdit(acc, "thickness", "6,5", {});
  assert.equal(r.kind, "ok");
  if (r.kind !== "ok") return;
  const c = r.res.candidate!;
  assert.deepEqual(c.thickness, { value_mm: 6.5, source: "MANUAL_MEASUREMENT", confirmed: false });
  assert.deepEqual(c.outer_diameter, acc.outer_diameter); // untouched
  assert.equal(r.res.feature, "THICKNESS");
  assert.equal(r.res.trace.provider, "LOCAL");
  assert.equal(r.res.readback, "Thickness: unknown → 6.5 mm (typed by you).");
  assert.equal(acc.thickness.value_mm, null); // input not mutated
});

test("range checks", () => {
  for (const s of ["0", "0.0", "1000", "2500"]) {
    const r = manualEdit(base(42, 30), "thickness", s, {});
    assert.equal(r.kind, "error", s);
  }
  assert.equal(manualEdit(base(42, 30), "thickness", "abc", {}).kind, "error");
});

test("inner must be smaller than outer, using shown values too", () => {
  assert.equal(manualEdit(base(42, 30), "inner_diameter", "45", {}).kind, "error");
  assert.equal(manualEdit(base(42, 30), "outer_diameter", "30", {}).kind, "error");
  // outer not accepted yet, but the photo shows 41.4
  assert.equal(manualEdit(base(null, null), "inner_diameter", "45", { outer_diameter: 41.4 }).kind, "error");
  assert.equal(manualEdit(base(null, null), "inner_diameter", "29.5", { outer_diameter: 41.4 }).kind, "ok");
});

test("groove must stay thinner than the wall", () => {
  const acc = base(42, 30, 6, { depth_mm: 3, width_mm: 2 });
  assert.equal(manualEdit(acc, "inner_diameter", "37", {}).kind, "error"); // wall 2.5 <= depth 3
  assert.equal(manualEdit(acc, "thickness", "1.5", {}).kind, "error"); // width 2 >= thickness
  assert.equal(manualEdit(acc, "thickness", "6.5", {}).kind, "ok");
});

test("same value already confirmed is no change", () => {
  const acc = base(42, 30, 6);
  acc.thickness = { value_mm: 6, source: "MANUAL_MEASUREMENT", confirmed: true };
  assert.equal(manualEdit(acc, "thickness", "6", {}).kind, "same");
});
