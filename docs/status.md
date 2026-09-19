# GridMend status (Sat 19 Sep, 20:50 CEST)

Short handoff. Plan: [build-plan.md](build-plan.md). Rules: [CLAUDE.md](../CLAUDE.md).

## Done (branch `feat/api-web`)

| Part | Where | Proof |
| --- | --- | --- |
| API: health, demo-clicks, demo-photo, auto-detect, inspect, voice, profile-edit, generate, files | `api/main.py`, `api/schemas.py` | `scripts/smoke.sh` 11/11 PASS |
| CAD ring template (rectangle + inner groove), full ring STEP/STL, **missing-segment STL**, 5 independent checks | `cad/ring.py` | 10 tests, ~0.1 s per build |
| Card homography + circle fit + missing arc + overlay; **auto-detect** of card and ring edges | `engine/fit.py` | 17 tests; demo photo: outer 41.35 mm, inner 29.55 mm, 168° missing |
| SLNG STT, Nebius vision/text adapters with LIVE/MOCK, spoken-edit parser (never auto-confirms) | `engine/providers/`, `engine/interpret.py`, `engine/profile_edit.py` | 27 tests (no real network yet) |
| Web UI, **design C "Field assistant"** + Section A–A from design A | `web/src/` | Headless click-through: photo → build, 5/5 checks |
| Layout mocks A–D (for reference) | `web/public/mocks/`, open `/mocks.html` | Needs `artifacts/mock-*.stl` locally |

Run: `uv sync && (cd web && npm install && npm run build) && uv run uvicorn api.main:app --port 8000`, open http://127.0.0.1:8000.

## Not done yet (in this order)

1. **API keys in `.env`** (empty now → everything is MOCK). Needed: `NEBIUS_API_KEY`, `NEBIUS_MODEL` (vision model; list with `GET /v1/models`), `SLNG_API_KEY`. Restart the server after editing. Check the header badges say LIVE.
2. **Live check:** one real Nebius call and one real SLNG call from the UI. Test the browser `audio/webm` upload against SLNG. Save traces with the `save-evidence` skill.
3. **Galtea (task 7):** T4 spoken-number trap on `engine.profile_edit.propose`. Baseline first, then the real fix, then rerun. Survey.
4. **Devin mode (user decision: after keys are live):** for parts with no template, our app starts a Devin session via API with photo observations + confirmed sizes; Devin writes CadQuery in its own sandbox; our validator (same 5 checks as `cad/ring.py`) decides pass/fail; failures go back to Devin; show one recorded failed-then-fixed run. Fits the Cognition challenge ("Devin for X", API-triggered, validator, auto-retry). Needs a Devin API key. Ring demo stays template-based.
5. **Card size:** measure the Calicéo card with a ruler, tick "I measured the card".
6. Pitch update (Andrii) and backup video before 23:00.

## Known limits

- Scale error of a few % (ring top face is above the card plane). No mm-accuracy claim.
- On the side where the ring wall is visible, auto-detect picks the wall foot, not the top edge. Operator checks points.
- No printer: no physical fit claim.

## Times

Integration freeze **22:05** · stop **23:00** · code freeze **Sun 09:30** · submit **10:30** (deadline 11:00).
