---
name: smoke-test
description: Run the whole GridMend path (tests, web build, API inspect → generate → files) and report pass/fail per step. Use before saying a task is done, after merging to main, and inside /loop during integration.
---

# Smoke test

Goal: know in 2 minutes whether `main` can still do the demo. Report only. Do **not** fix anything inside this skill unless the user asked for fixes.

## Steps

Run from the repo root. Stop at the first step that cannot run, and report what is missing.

1. `git status --short` and `git log --oneline -3`. Note uncommitted changes.
2. `uv run pytest -q`
3. `cd web && npm run build` (type check + bundle).
4. `scripts/smoke.sh`. It must:
   - start the API on a free port, wait for `GET /api/health`;
   - `POST /api/inspect` with the demo photo `sample-photos/20260919_180605.jpg` and the saved clicks in `fixtures/demo-clicks.json` (skip with a clear message if the photo is not on this machine);
   - `POST /api/generate` with synthetic dimensions (labeled synthetic) plus the fitted `missing_arc_deg`;
   - download `step_url`, `stl_url`, `missing_segment_stl_url`, `summary_url`, and check that each is non-empty;
   - check all `checks[].passed` are true;
   - stop the API; exit non-zero on any failure.
5. Grep for leaks: `git diff --cached; git ls-files | grep -Ei '\.env$|\.mp4$|sample-photos/'` must print nothing. Grep `web/` for `NEBIUS_API_KEY|SLNG_API_KEY|GALTEA_API_KEY` values (not names).

## Report format

One line per step: `PASS` / `FAIL` / `SKIP` + one short reason. Then:
- which provider ran in which mode (`LIVE` / `MOCK`), from the traces;
- the first failing command with the exact error text (max 10 lines).

If everything passes, say so in one line. Never report PASS for a step that did not run.
