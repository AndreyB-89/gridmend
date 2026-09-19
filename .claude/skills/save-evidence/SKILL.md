---
name: save-evidence
description: Save real sponsor evidence (Nebius, SLNG, Galtea traces, CAD check results) into evidence/ for judges, without secrets and without fabricated results. Use after a real LIVE run or an evaluation run.
---

# Save evidence

Judges ask "did you really use it?". This skill saves proof from **real runs only**.

## Where

`evidence/<provider>/<YYYYMMDD-HHMM>-<short-name>.json` (+ `.md` summary). `evidence/raw/` is gitignored, for large or private files (audio, full photos).

## What each record holds

- `provider`, `model`, `mode` (must be `LIVE` to count as sponsor evidence), `request_id`, `latency_ms`, UTC timestamp;
- `build_commit` (`git rev-parse --short HEAD`) and whether the working tree was dirty;
- input summary: file names and hashes (`shasum -a 256`), transcript text, and **no** raw keys;
- output: the parsed result (and the raw provider JSON if small, with ids but no keys);
- for Galtea: test case ids, baseline result, fix commit, rerun result.

## Rules

- Never write a record for a MOCK or REPLAY run as sponsor evidence. You may save it under `evidence/mock/`, clearly named.
- Never edit numbers by hand. If a run failed, save the failure too. It is part of the Galtea before/after story.
- Before saving, scan the file for `sk-`, `Bearer `, `api_key`, `Authorization` and long random-looking tokens. Remove any you find. (Claude may not read `.env`, which is denied in settings.)
- Photos with people or screens in the background go to `evidence/raw/` only.
- After saving, add one line to `evidence/README.md`: time, provider, what it proves, file link.
