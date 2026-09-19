# GridMend build plan v3 (scope cut, Sat 19:40; updated 20:50)

Current state and next steps: [status.md](status.md).

**This file wins over `project-plan.md` for what we build tonight.** The project plan still holds the rules (no invented dimensions, no model-generated code, honest labels). This file says what to build, in which order and who owns it.

## Why we cut

At 19:30 the repo had no code. Integration freeze is **22:05**. That leaves about 2.5 hours tonight and 30 minutes tomorrow. We build the smallest version that works from start to end, then add extras only if time is left.

## Decisions

| Topic | Decision |
| --- | --- |
| Plan vs Valentin's diagram | **Fixed CadQuery template** for the ring (plan). No LangChain. **Devin: yes, after keys are live** (user decision 20:15): a separate "Devin mode" for parts without a template, see `docs/status.md`. |
| "Missing piece" idea (diagram) | Kept, done deterministically: after the circle fit we export the **missing arc as its own STL** and show it in a different color. Full ring = surviving arc + missing segment. |
| Edge detection | **Auto-detect first, operator drags points to correct** (user decision 20:15). Clicks remain the fallback. |
| Thickness and groove | **By voice** ("thickness is seven millimetres"), not from the side photo. Side photos are tilted and the card is held by hand. |
| Profile | Rectangle cross-section + **optional inner groove** (depth, width). The 4–16 point polygon editor is a Should. |
| Demo input | `sample-photos/20260919_180605.jpg`: top view, big surviving arc, full card. Hide the two small fragments in the demo photo if we re-shoot. |
| Card size | ID-1 (85.60 × 53.98 mm) **only after someone measures it**. Until then it is unconfirmed in the UI. |
| Galtea | One case only: **T4 spoken-number trap**. Text input, real before/fix/after. |
| Pitch | Substation context max **30 seconds**. Main line: "Only half the part survives. You cannot measure a diameter from half a ring with a ruler. The app rebuilds the missing half." |
| Hosting | Team laptop, one process. |

## Must (in this order)

| # | Task | Owner | Done when |
| --- | --- | --- | --- |
| 1 | FastAPI skeleton: `/api/health`, `/api/inspect`, `/api/voice`, `/api/profile-edit`, `/api/generate`, `/api/files/{name}`, serving `web/dist` | Mortaza | `uv run uvicorn api.main:app` starts; mock responses match `contracts/types.ts` and say `mode: "MOCK"` |
| 2 | CadQuery ring template + checks: revolve rectangle (+ groove), export STEP/STL, missing-segment STL, reimport check | Valentin | Synthetic ring (labeled synthetic) exports; 5 checks pass; STEP reopens |
| 3 | Geometry fit: homography from 4 card corners, circle fit (outer, inner) from clicked points, surviving arc angles, overlay PNG | Valentin | On `20260919_180605.jpg` with saved clicks, returns radii in mm and arc range; overlay shows fit + missing arc in red |
| 4 | Web UI: upload photo, click corners/edge points, show overlay and dimensions, push-to-talk, confirm buttons, Three.js viewer, downloads | Mortaza | Whole journey works in the browser without a terminal |
| 5 | SLNG STT behind `/api/voice` | Mortaza | Real audio → transcript; trace saved in `evidence/` |
| 6 | Nebius behind `/api/inspect` (observations + next question) and `/api/profile-edit` (transcript → proposed dimension/groove edit) | Valentin | Real calls; proposal is never auto-confirmed; trace saved |
| 7 | Galtea T4 run: baseline → real fix → rerun | Valentin runs, Andrii records | Evidence saved; survey done |
| 8 | Smoke script `scripts/smoke.sh`: start API, run fixture inspect + generate, check files | Mortaza | One command, exit 0 |

## Should (only after all Must pass)

SLNG TTS for questions · profile polygon editor with undo · held-out intact-photo comparison.

## Won't (tonight)

Side-photo calibration · energy explorer or any new catalog/explorer UI · LangChain · printing claims · database, auth, revisions.

## Timeline (CEST)

| Time | Goal |
| --- | --- |
| 19:45–20:15 | Tasks 1 + 2 started in parallel. API keys tested (Nebius, SLNG, Galtea). Card measured. |
| 20:15–21:15 | Tasks 3, 4, 5. Mock → real one piece at a time. |
| 21:15–22:05 | Task 6, 8, first full run. Galtea baseline. **22:05 integration freeze.** |
| 22:05–23:00 | Fix only. Record a full run as backup video. **Stop 23:00.** |
| Sun 09:00–09:30 | Galtea fix/rerun if not done, blockers only. **Code freeze 09:30.** |
| 09:30–10:30 | Rehearse twice, submit. Deadline 11:00. |

## Contract changes (v2 → v3)

See `contracts/types.ts`. Added: click points in `InspectContext`, `RingFit` in `InspectResult`, `groove` and `missing_arc_deg` in `GenerateRequest`, `missing_segment_stl_url` in `GenerateResult`, dimension features in `ProfileFeature` so `/api/profile-edit` also handles spoken thickness/diameters. Removed nothing that code depends on (there is no code yet).
