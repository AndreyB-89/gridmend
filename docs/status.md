# GridMend status (Sat 19 Sep, 22:00 CEST)

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

| **LIVE providers work** (Nebius + SLNG keys set). Defaults: vision `google/gemma-3-27b-it`, text `Qwen/Qwen3-235B-A22B-Instruct-2507` | `engine/providers/` | `scripts/check_providers.py` all PASS; LIVE smoke 11/11; inspect ~2.5 s; SLNG ~0.7 s on browser webm/opus |
| SLNG fix: no `smart_format` (SLNG answers 400 "model latest not found" with it) | `engine/providers/slng.py` | test + live call |
| Spoken-number parser + LIVE grounding guard (a model number must be in what the engineer said) | `engine/spoken_numbers.py`, `engine/profile_edit.py` | T4 (27 cases). MOCK: old `ce33773` 14/25 with 6 silent wrong values (e.g. "six and a half" → 6 mm) → new 27/27 (2 STT-style cases added). LIVE (Qwen3-235B): old code **24/27** (3 × "invalid JSON" error = error screen for the engineer) → new **27/27**. Files in `evals/results/` |
| Model replies in odd shapes (`[6, 7]`, `{"value": null}`) → a question, not a 502 | `engine/profile_edit.py` | tests |
| Two sizes in one sentence: saves one, says the other must be said again | `engine/profile_edit.py` | test |
| Vision model can no longer label geometry numbers as "Engineer reports" | `engine/interpret.py` | test; seen live |
| Auto-detect finds complete rings too | `engine/fit.py` | Held-out intact photo: OD **41.4 mm** vs rebuild **41.3 mm**. ID does not match (24.8 vs 29.5: wall foot) → no ID-accuracy claim |
| Auto-detect v2 (after 22:05, user's OK) | `engine/fit.py`, `engine/test_detect.py` | Finds the top face, not the wall foot: edge search for two circles with one centre, in a frame corrected for the camera angle. Top views: 2/16 → **9/17 HIGH** (all top views, incl. IMG_9475); intact photo ID now **29.9** (was 24.8). Several rings: splits touching rings, picks one, says so. Side / hand / cut photos: plain message, no wrong points. Yellow rings only (brown excluded) |
| Number boxes + typing hint | `web/src/manualEntry.ts`, `App.tsx` | Typed mm → Draft (MANUAL_MEASUREMENT) → Confirm. 8 unit tests |
| Optional side photo → vision model (shape observations only, sizes from photos dropped). HEIC → plain "use JPEG" message | `engine/interpret.py`, `api/main.py`, `web/src/App.tsx` | tests; LIVE headless run 3.0 s, "Visible (side photo): … roughly rectangular" |
| **Waiting for Valentin:** rough thickness from the side photo (card upright, touching the ring) | contract change (`side_calibration`) | not built |
| Plain error banners (no "PROVIDER_FAILED" codes) | `web/src/api.ts` | web build |

## Not done yet (in this order)

1. ~~API keys~~ Done for Nebius + SLNG. Needed: `NEBIUS_API_KEY`, `NEBIUS_MODEL` (vision model; list with `GET /v1/models`), `SLNG_API_KEY`. Both models have working defaults (vision `google/gemma-3-27b-it`, text `Qwen/Qwen3-235B-A22B-Instruct-2507`); set `NEBIUS_MODEL` / `NEBIUS_TEXT_MODEL` only to override. Then run `uv run python scripts/check_providers.py`. Restart the server after editing. Check the header badges say LIVE.
2. **Live check in a real browser with a real microphone** (headless Chrome only has a fake beep). Then save traces with the `save-evidence` skill.
3. ~~T4 eval with LIVE Nebius~~ Done 22:00: 27/27 LIVE (old code 24/27 LIVE). Pitch line in `docs/pitch.md` still says "25" and "MOCK parser": Andrii to update (now 27 cases, LIVE + MOCK both 27/27).
4. **Devin mode (user decision: after keys are live):** for parts with no template, our app starts a Devin session via API with photo observations + confirmed sizes; Devin writes CadQuery in its own sandbox; our validator (same 5 checks as `cad/ring.py`) decides pass/fail; failures go back to Devin; show one recorded failed-then-fixed run. Fits the Cognition challenge ("Devin for X", API-triggered, validator, auto-retry). Needs a Devin API key. Ring demo stays template-based.
5. **Card size:** measure the Calicéo card with a ruler, tick "I measured the card".
6. Pitch update (Andrii) and backup video before 23:00.

## Known limits

- Scale error of a few % (ring top face is above the card plane). No mm-accuracy claim.
- Auto-detect v2 looks for the top-face edges (not the wall foot). It needs a top view, a yellow ring and the card flat on the table. Yellow vs brown is a thin hue cut (17). Any yellow round object with a hole passes. The operator still checks the points.
- No printer: no physical fit claim.

## Times

Integration freeze **22:05** · stop **23:00** · code freeze **Sun 09:30** · submit **10:30** (deadline 11:00).
