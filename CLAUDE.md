# GridMend: notes for Claude Code (and Codex via AGENTS.md)

HackBarna hackathon project. **Photo of a broken ring + card for scale + engineer's voice → rebuilt ring as STEP/STL, with the missing segment as its own STL.** No printer: CAD files and checks are the deliverable.

**Current state and next steps: [docs/status.md](docs/status.md).** What to build tonight: [docs/build-plan.md](docs/build-plan.md). Rules and background: [docs/project-plan.md](docs/project-plan.md). Contract: [contracts/types.ts](contracts/types.ts) (v3).

## Deadlines (Barcelona, CEST)

Integration freeze **Sat 22:05** · stop **23:00** · code freeze **Sun 09:30** · submit **10:30** (hard deadline 11:00).
After 22:05: only fixes to existing paths. No new endpoints, dependencies, providers or UI flows. If asked for a feature after the freeze, say so and ask first.

## Owners (don't edit another owner's files without asking)

| Owner | Files |
| --- | --- |
| Valentin | `engine/`, `cad/`, `evals/`, `api/routes/inspect.py`, `api/routes/generate.py` |
| Mortaza | `web/`, `api/main.py`, `api/schemas.py`, `api/routes/voice.py`, `api/routes/profile_edit.py`, `api/routes/files.py`, `scripts/` |
| Andrii | `fixtures/`, `evidence/`, `docs/` |

Contract changes (`contracts/types.ts` + `api/schemas.py`) need both developers to agree. Keep them identical.

## Stack and commands

- Python **3.12** via `uv` (system Python is 3.14; CadQuery/OCP wheels may not support it). Project root has `pyproject.toml`.
- Backend: `uv sync` then `uv run uvicorn api.main:app --reload --port 8000`
- Tests: `uv run pytest -q`
- Web (Vite + React + TS + Three.js): `cd web && npm install && npm run dev` (proxy `/api` → `:8000`); check types with `npm run build`.
- Whole path: `scripts/smoke.sh` (starts API, runs fixture inspect + generate, checks files; exit 0 = OK).
- These commands are created by build-plan tasks 1 and 8. If one doesn't exist yet, create it in the task, don't invent a different command.

## Hard rules

1. **Never invent dimensions.** Unknown = `null`, never 0 or a "typical" value. A photo estimate, a spoken number or an LLM output is a *proposal* until the operator presses Confirm.
2. **Never run code or shell written by a model on our server.** Ring CAD comes only from the fixed template in `cad/`. LLM output is parsed into typed fields, then validated. (Planned Devin mode: Devin runs its code in its own sandbox; our server only validates the files it returns. See `docs/status.md`.)
3. **The LLM does not measure pixels.** Geometry code (OpenCV/NumPy) measures. Nebius interprets, and asks the next question.
4. **Label modes honestly.** Every provider response carries `trace.mode` = `LIVE` / `REPLAY` / `MOCK`. The UI shows MOCK and REPLAY visibly. Never switch to a mock silently when a live call fails. Return an `ApiError` (502/504).
5. **Secrets stay server-side.** Keys only in `.env` (gitignored). Never in `web/`, logs, evidence files or commits.
6. **No raw photos or videos in git.** `sample-photos/` and `*.mp4` are gitignored (bystanders, screens, a 271 MB video). Tests use the local file if present and skip otherwise.
7. **Stale CAD is never shown as new.** Any accepted edit clears the preview and download links until a new generate succeeds.
8. **No fabricated sponsor evidence.** Evidence files come from real runs only (see the `save-evidence` skill). If Galtea finds no failure, we say so.

## Geometry conventions

- Card plane: homography maps the 4 clicked corners to `(0,0),(w,0),(w,h),(0,h)` in mm. Card size is unconfirmed until measured (ID-1 = 85.60 × 53.98 mm).
- Circle fit: algebraic (Kasa) fit, then report the RMS residual. Require ≥3 points per edge and warn below 120° of support.
- Angles: degrees, counter-clockwise, 0 = +x in the card plane. `missing_arc_deg` is the complement of the surviving arc.
- Ring CAD: revolve an (r, z) profile around Z. Rectangle from inner radius to outer radius, height = thickness. The optional groove is cut from the inner wall, centred at mid-height. The missing segment is the same solid restricted to `missing_arc_deg`.
- Units: mm everywhere in the API and CAD.

## Working style

- Small vertical slices. Keep `main` runnable. Every PR says what it proves (command + output).
- Mock first, matching the contract exactly, then replace one provider at a time with a LIVE call.
- Before saying "done", run `uv run pytest -q`, the web build and `scripts/smoke.sh` (the `smoke-test` skill).
- Docs and messages: simple B1–B2 English, short full sentences.

## Skills in this repo

- `smoke-test`: run the whole path and report pass/fail per step. Good for `/loop`.
- `provider-adapter`: how to add or fix a Nebius / SLNG / Galtea call (LIVE + MOCK, trace, timeouts).
- `save-evidence`: save real sponsor traces to `evidence/` without secrets.

Loop and teamwork recipes: [docs/claude-workflow.md](docs/claude-workflow.md).
