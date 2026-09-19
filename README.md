# GridMend

**Photo + engineer voice → evidence-backed replacement CAD.**

HackBarna AI Summit Barcelona 2026 R&D demonstrator for damaged substation accessories.

## Current status

Repository starter: project plan, TypeScript data contract, controlled plate specification and existing illustrative substation assets. The integrated web app, sponsor API connections and manufacturing CAD generator are **not implemented yet**.

## Start here

1. Read [the team project plan](docs/project-plan.md).
2. Use [contract v1.1](contracts/types.ts) as the shared API shape; Mortaza mirrors it in Pydantic/OpenAPI.
3. Use [the controlled plate specification](fixtures/plate-spec.json) for the first CAD template.
4. Copy `.env.example` to `.env` and supply your own sponsor credentials locally. Never commit `.env`.
5. Work from the [ownership and ticket guide](CONTRIBUTING.md). There is no app startup command until the implementation scaffold is added.

## One demo

Upload a damage image, record and review a short engineer observation, identify the component with Nebius, confirm its reference/dimensions, generate STEP/STL, and inspect independent geometry checks. Missing dimensions and unsuitable material substitutions must block generation.

Primary sponsor targets: **Nebius, SLNG, Galtea**. Norma is an optional fourth target. Sponsor use and eligibility require actual evidence; this repository starter proves neither.

## Team

| Owner | Responsibility |
| --- | --- |
| Andrii | Product, energy domain, scope, fixture truth, pitch/submission |
| Valentin | ML, inference, decision rules, CAD, Galtea |
| Mortaza | Full stack, voice capture/API, integration, deployment, optional Norma |

## Layout

- `web/` — React/TypeScript inspection UI and 3D viewer.
- `api/` — FastAPI HTTP/state and SQLite persistence.
- `engine/` — Nebius/SLNG adapters and decision rules.
- `cad/` — allowlisted parametric template and independent validation.
- `contracts/` — shared data contract.
- `fixtures/`, `catalog/` — controlled demo data.
- `evals/`, `evidence/` — acceptance cases and actual sponsor evidence.
- `reference/substation-library/` — existing generic, illustrative assets; not the frozen application catalog.

## Timebox

Barcelona CEST, 19 September 2026: integration freeze **21:00**, code freeze **22:30**, internal deadline **00:00 on 20 September**. Check the plan for dependency kill points and official-event deadline differences.

## Provenance and scope

The reference scene is generic and is not a real utility asset or manufacturing CAD. Plate dimensions are a team-designed demo fixture. All generated artifacts remain NOT_APPROVED for operational use. No news photos, real station documents or credentials are bundled.

The working name is provisional; no trademark or domain clearance has been performed. Licensing has not been selected. Confirm hackathon reuse rules before incorporating reference assets into the judged build.

## Contributors 

- Andrii 
- Mortaza 
- Valentin
