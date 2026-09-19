# GridMend

**Photo + engineer voice → evidence-backed replacement CAD.**

HackBarna AI Summit Barcelona 2026 R&D demonstrator for damaged substation accessories.

## Current status

Repository starter: revised middle-ring project plan, small TypeScript contract v2, unknown-dimension specimen record and illustrative substation reference assets. The integrated web app, sponsor API connections and manufacturing CAD generator are **not implemented yet**.

## Start here

1. Read [the team project plan](docs/project-plan.md).
2. Use [ring contract v2](contracts/types.ts) as the shared API shape; Mortaza mirrors it in Pydantic/OpenAPI.
3. Use [the middle-ring specimen record](fixtures/ring-demo.json); actual measurements remain unknown until scale/captures are validated.
4. Copy `.env.example` to `.env` and supply your own sponsor credentials locally. Never commit `.env`.
5. Work from the [ownership and ticket guide](CONTRIBUTING.md). There is no app startup command until the implementation scaffold is added.

## Substation application and roadmap

The existing generic 110/10 kV substation model and component library remain part of GridMend: **36 illustrative component records and 27 draft manufacturing options across 13 records**. They provide the context for future identification and selection of 3D-printing, CNC, sheet-fabrication or specialist routes. The options are engineering-review candidates, not approved spares or current reconstruction coverage.

The ring is a simple physical demonstration of the photo-and-voice-to-CAD step. Next comes one verified industrial accessory and a manufactured/inspected specimen. See the [product roadmap](docs/roadmap.md) and [five-minute pitch](docs/pitch.md).

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
