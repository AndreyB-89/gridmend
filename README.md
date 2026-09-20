# GridMend

**Photo + engineer voice → evidence-backed replacement CAD.**

HackBarna AI Summit Barcelona 2026 R&D demonstrator for damaged substation accessories.

## Current status

Repository starter with a working standalone substation route explorer: revised middle-ring project plan, small TypeScript contract v2, unknown-dimension specimen record and illustrative substation reference assets. Implementation in progress on `feat/api-web`: FastAPI backend, CadQuery ring generator, card-scale circle fit, SLNG/Nebius adapters with visible MOCK mode, React + Three.js UI.

## Run it

Needs `uv` and Node 22. Python 3.12 is picked automatically (`.python-version`).

```bash
cp .env.example .env          # add NEBIUS_API_KEY, NEBIUS_MODEL, SLNG_API_KEY (without keys: MOCK mode, shown in the UI)
uv sync
cd web && npm install && npm run build && cd ..
uv run uvicorn api.main:app --port 8000     # open http://127.0.0.1:8000
```

Web development with hot reload: `cd web && npm run dev` (proxies `/api` to port 8000).
Tests: `uv run pytest -q`. Whole path: `scripts/smoke.sh`.

## Video reconstruction on `devin-api`

Upload the video, then give the final goal and measured dimensions in the chat:

> Build the missing part of this ring with rectangular cross section, outer diameter 40 mm, inner diameter 36 mm and height 9 mm.

The Nebius/LangChain agent treats the **complete intact reference** as an intermediate step. The operator does not need to request it separately. It calls the trusted measurement tool, asks for missing or conflicting values, and waits for **Confirm and build**. Its CadQuery tool then exports and checks the complete STL and STEP, retaining the ring's central hole. Dimensions and confirmation come from the operator; model-generated code is never executed.

Only after these checks does GridMend send the original video, full reference STL, specification and frame manifest to Devin. The existing independent validator and same-session correction loop check the proposed missing material.

Video reconstruction targets an **approximate hackathon demo**. Both the survivor and visible missing-region silhouettes must reach 70% IoU in at least two clear views. IoU measures silhouette overlap, not reconstruction accuracy or probability. The thresholds are not calibrated guarantees. Mesh integrity, confirmed dimensions, containment, at most 1% sampled overlap and at most 2% uncovered reference volume remain mandatory. Approximation notes are preserved in the validation report; an outstanding input request still prevents acceptance. The complete reference is shown with the proposed missing material highlighted in red.

When the operator answers a Devin question without changing the specification, GridMend resumes the same session and candidate attempt. A delayed copy of that answered question cannot stop polling while Devin is still working.

Video ingestion performs local decoding and frame extraction. It does not wait for a Nebius image analysis. The reference agent uses text and tools; `NEBIUS_VIDEO_MODEL` overrides its model, otherwise it uses `NEBIUS_TEXT_MODEL` (default `Qwen/Qwen3-235B-A22B-Instruct-2507`). LIVE requires server-side `NEBIUS_API_KEY` and `DEVIN_API_KEY`; `RECONSTRUCTION_MODE=MOCK` builds only the reference and starts no paid session.

The supported intact templates are rings, cylinders and boxes, with their supported profiles and cavities. Computational validation does not establish physical fit.

## Start here

1. What we build tonight: [build plan v3](docs/build-plan.md). Rules: [project plan](docs/project-plan.md).
2. Contract: [contracts/types.ts](contracts/types.ts) (v3), mirrored in `api/schemas.py`.
3. Fixture: [ring-demo.json](fixtures/ring-demo.json). Raw photos stay local in `sample-photos/` (gitignored).
4. Agents: [CLAUDE.md](CLAUDE.md) / AGENTS.md and [docs/claude-workflow.md](docs/claude-workflow.md).

## Substation application and roadmap

The existing generic 110/10 kV substation model and component library remain part of GridMend: **36 illustrative component records and 27 draft manufacturing options across 13 records**. They provide the context for future identification and selection of 3D-printing, CNC, sheet-fabrication or specialist routes. The options are engineering-review candidates, not approved spares or current reconstruction coverage.

Open the [component explorer](reference/substation-explorer.html) locally in a browser (download the HTML from GitHub first). It includes route filters, process/material details, supplier dispositions and component-brief downloads. See [viewer instructions](reference/substation-library/README.md#open-the-explorer).

The ring is a simple physical demonstration of the photo-and-voice-to-CAD step. Next comes one verified industrial accessory and a manufactured/inspected specimen. See the [product roadmap](docs/roadmap.md) and [five-minute pitch](docs/pitch.md).

Preview the broader [energy asset explorer](reference/energy-asset-explorer.html): substation, BESS, PCS, solar, wind and thermal tabs with shared accessory and tooling candidates. [Scope and rebuild instructions](reference/energy-asset-library/README.md). The spinner remains the reconstruction demo.

## One demo

Photograph the broken middle yellow ring beside a confirmed-size card. Use Nebius interpretation, geometric fitting and SLNG spoken answers to establish its dimensions/profile; generate an intact ring STEP/STL model and highlight the missing section. No printer is available: CAD files and computational checks are the deliverable, with no physical-fit claim.

Primary sponsor targets: **Nebius, SLNG, Galtea**. Norma is outside the revised delivery scope. Sponsor use and eligibility require actual evidence; this repository starter proves neither.

## Team

| Owner | Responsibility |
| --- | --- |
| Andrii | Product, energy domain, scope, fixture truth, pitch/submission |
| Valentin | Geometry/inference, inspection/generation backend, CAD, Galtea wrapper |
| Mortaza | UI, SLNG capture/API, preview/downloads, integration and serving |

## Layout

- `web/` — React/TypeScript inspection UI and 3D viewer.
- `api/` — small FastAPI interface and local files; no database required.
- `engine/` — Nebius/SLNG adapters and decision rules.
- `cad/` — allowlisted parametric template and independent validation.
- `contracts/` — shared data contract.
- `fixtures/`, `catalog/` — controlled demo data.
- `evals/`, `evidence/` — acceptance cases and actual sponsor evidence.
- `reference/substation-library/` — existing generic, illustrative assets; not the frozen application catalog.

## Timebox

Barcelona CEST: integration freeze **Saturday 19 September 22:05**; stop **23:00**; resume **Sunday 20 September 09:00**; code freeze **09:30**; target submission **10:30**, official deadline **11:00**. See [sprint issues and board setup](docs/sprints.md).

## Provenance and scope

The reference scene is generic and is not a real utility asset or manufacturing CAD. The old plate fixture/plan are historical only. Current middle-ring dimensions are unset; card size and geometry must be established from evidence. All generated artifacts remain NOT_APPROVED for operational use. No news photos, real station documents or credentials are bundled.

The working name is provisional; no trademark or domain clearance has been performed. Licensing has not been selected. Confirm hackathon reuse rules before incorporating reference assets into the judged build.

## Contributors 

- Andrii 
- Mortaza 
- Valentin
