"""Run the T4 spoken-number cases against engine.profile_edit.propose.

Run: uv run python evals/run_t4.py [--out evals/results/<name>.json]
Uses LIVE Nebius if NEBIUS_API_KEY is set, else the MOCK parser. The mode is printed and saved.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.schemas import Dimension, GenerateRequest, Groove, ProfileEditRequest  # noqa: E402
from engine.profile_edit import propose  # noqa: E402

CASES = Path(__file__).with_name("t4_cases.json")


def accepted_request(a: dict) -> GenerateRequest:
    def d(v):
        return Dimension(value_mm=v, source="PHOTO", confirmed=True) if v is not None else Dimension.unknown()

    g = a.get("groove")
    return GenerateRequest(
        shape=None, outer_diameter=d(a["outer_diameter_mm"]), inner_diameter=d(a["inner_diameter_mm"]),
        thickness=d(a["thickness_mm"]), groove=Groove(depth_mm=g[0], width_mm=g[1]) if g else None,
        profile_rz_mm=None, profile_basis="SIMPLIFIED_RECTANGLE", profile_confirmed=True,
        missing_arc_deg=None, purpose="DEMO_CAD_ONLY",
    )


def judge(case: dict, accepted: GenerateRequest, result) -> tuple[bool, str]:
    """Returns (passed, what we got)."""
    c = result.candidate
    if c is None:
        got = f"ask: {result.question}"
        return case["expect"] == "ask", got
    if c.profile_confirmed or any(
        getattr(c, f).confirmed and getattr(c, f) != getattr(accepted, f)
        for f in ("outer_diameter", "inner_diameter", "thickness")
    ):
        return False, "proposal came back CONFIRMED"
    changed = {}
    for f in ("outer_diameter", "inner_diameter", "thickness"):
        if getattr(c, f) != getattr(accepted, f):
            changed[f] = getattr(c, f).value_mm
    if c.groove != accepted.groove and c.groove is not None:
        changed["groove"] = [c.groove.depth_mm, c.groove.width_mm]
    got = json.dumps(changed)
    exp = case["expect"]
    if exp == "ask":
        return False, got
    want = {k: v for k, v in exp.items() if k != "measured"}
    ok = set(changed) == set(want) and all(
        (abs(changed[k] - v) < 1e-6) if not isinstance(v, list) else all(abs(x - y) < 1e-6 for x, y in zip(changed[k], v))
        for k, v in want.items()
    )
    if ok and exp.get("measured"):
        field = next(iter(want))
        ok = getattr(c, field).source == "SPOKEN_MEASUREMENT"
        got += " (measurement)" if ok else " (not marked as measurement)"
    return ok, got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="save results JSON here")
    args = ap.parse_args()
    spec = json.loads(CASES.read_text())
    accepted = accepted_request(spec["accepted"])
    rows, mode, model = [], None, None
    for case in spec["cases"]:
        try:
            result = propose(ProfileEditRequest(accepted=accepted, reviewed_voice_text=case["text"]))
            mode, model = result.trace.mode, result.trace.model
            passed, got = judge(case, accepted, result)
        except Exception as exc:  # a crash is a failure, not a skip
            passed, got = False, f"error: {type(exc).__name__}: {exc}"
        rows.append({"id": case["id"], "text": case["text"], "expect": case["expect"], "got": got, "passed": passed})
        print(f"{'PASS' if passed else 'FAIL'}  {case['id']:<20} {got}")
    n = sum(r["passed"] for r in rows)
    print(f"\n{n}/{len(rows)} passed. mode={mode} model={model}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "suite": spec["name"], "run_at": datetime.now(timezone.utc).isoformat(), "mode": mode, "model": model,
            "passed": n, "total": len(rows), "results": rows,
        }, indent=2))
        print(f"saved {out}")
    return 0 if n == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
