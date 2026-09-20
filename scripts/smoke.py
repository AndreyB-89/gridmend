"""Called by scripts/smoke.sh. Prints one PASS/FAIL/SKIP line per step."""
import json
import os
import sys
from pathlib import Path

import httpx

BASE = os.environ["SMOKE_BASE"]
ROOT = Path(__file__).resolve().parent.parent
c = httpx.Client(base_url=BASE, timeout=90)
failed = False


def step(name, ok, detail=""):
    global failed
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}".rstrip())
    failed |= not ok


def unknown():
    return {"value_mm": None, "source": None, "confirmed": False}


h = c.get("/api/health").json()
step("health", h.get("status") == "OK", json.dumps(h["modes"]))

missing_arc = None
clicks_path = ROOT / "fixtures" / "demo-clicks.json"
if clicks_path.exists() and (ROOT / json.loads(clicks_path.read_text())["image"]).exists():
    clicks = json.loads(clicks_path.read_text())
    ctx = {
        "top_calibration": {
            "card_size_mm": clicks["card_size_mm"],
            "size_confirmed": clicks.get("card_size_confirmed", False),
            "corners_px": clicks["corners_px"],
            "same_plane_confirmed": False,
        },
        "side_calibration": None,
        "top_roi_px": None,
        "outer_edge_points_px": clicks["outer_edge_points_px"],
        "inner_edge_points_px": clicks["inner_edge_points_px"],
        "reviewed_voice_text": "",
        "operator_note": "",
    }
    img = (ROOT / clicks["image"]).read_bytes()
    r = c.post("/api/inspect", files={"top_image": ("demo.jpg", img, "image/jpeg")}, data={"context": json.dumps(ctx)})
    if r.status_code == 200 and r.json()["fit"]:
        res = r.json()
        fit = res["fit"]
        missing_arc = fit["missing_arc_deg"]
        step("inspect", True, f"outer={fit['outer_diameter_mm']:.2f} inner={fit['inner_diameter_mm']:.2f} "
             f"rms={fit['rms_residual_mm']:.2f} missing={missing_arc} nebius={res['trace']['mode']}")
        ov = c.get(res["top_overlay_url"])
        step("overlay", ov.status_code == 200 and len(ov.content) > 1000)
    else:
        step("inspect", False, f"{r.status_code} {r.text[:300]}")
else:
    print("SKIP inspect (demo photo or fixtures/demo-clicks.json not on this machine)")

# SYNTHETIC dimensions (not measured): only to exercise the CAD path.
synthetic = {
    "outer_diameter": {"value_mm": 40.0, "source": "MANUAL_MEASUREMENT", "confirmed": True},
    "inner_diameter": {"value_mm": 30.0, "source": "MANUAL_MEASUREMENT", "confirmed": True},
    "thickness": {"value_mm": 6.0, "source": "MANUAL_MEASUREMENT", "confirmed": True},
    "groove": {"depth_mm": 1.0, "width_mm": 2.0},
    "shape": None,
    "profile_rz_mm": None,
    "profile_basis": "OBSERVED",
    "profile_confirmed": True,
    "missing_arc_deg": missing_arc or [200.0, 340.0],
    "purpose": "DEMO_CAD_ONLY",
}

pe = c.post("/api/profile-edit", json={"accepted": {**synthetic, "thickness": unknown(), "profile_confirmed": False},
                                       "reviewed_voice_text": "thickness is 6 millimetres"})
ok = pe.status_code == 200 and (pe.json()["candidate"] is None or not pe.json()["candidate"]["thickness"]["confirmed"])
step("profile-edit", ok, f"{pe.status_code} mode={pe.json().get('trace', {}).get('mode')}" if pe.status_code == 200 else pe.text[:200])

bad = c.post("/api/generate", json={**synthetic, "thickness": unknown()})
step("generate rejects unknown thickness", bad.status_code == 422 and bad.json()["error"] == "NEEDS_INPUT")

g = c.post("/api/generate", json=synthetic)
if g.status_code == 200:
    res = g.json()
    step("generate", all(ch["passed"] for ch in res["checks"]), " ".join(f"{ch['name']}={ch['passed']}" for ch in res["checks"]))
    for key in ("step_url", "stl_url", "missing_segment_stl_url", "summary_url"):
        f = c.get(res[key]) if res[key] else None
        step(f"download {key}", f is not None and f.status_code == 200 and len(f.content) > 100)
else:
    step("generate", False, f"{g.status_code} {g.text[:300]}")

trav = c.get("/api/files/..%2F.env")
step("files rejects traversal", trav.status_code == 404)
sys.exit(1 if failed else 0)
