# Team working agreement

Use a short branch per slice, such as `feat/voice-capture` or `feat/plate-generator`. Open a pull request into `main` and have the other technical teammate review it. Keep `main` usable; do not collect three disconnected implementations until the final hour.

Mortaza owns `web/`, `api/`, `contracts/` and deployment. Valentin owns `engine/`, `cad/` and `evals/`. Andrii owns `fixtures/`, `catalog/`, `evidence/` and product claims. A contract change needs Mortaza plus its consumer. Andrii protects scope.

## First tickets

| Ticket | Owner | Done when |
| --- | --- | --- |
| Prove Nebius image model and CAD runtime | Valentin | Actual image response saved and STEP/STL plate reopens |
| Scaffold FastAPI/UI against contract v1.1 | Mortaza | UI renders typed mocked ready/needs-input/blocked states |
| Confirm fixture truth and reuse rules | Andrii | Drawing/reference and five expected outcomes recorded |
| Prove microphone → SLNG transcript | Mortaza + Valentin | Fresh clip returns real transcript by 17:30 |
| Integrate photo + reviewed voice → CAD | Both technical owners | Full path works with reference-confirmed dimensions |
| Find and fix consequential failure with Galtea | Valentin + Andrii | Actual baseline failure, fix and rerun saved |

## Every ticket

Name one owner, scoped outcome, contract impact and testable done-when. Include working and relevant failure-case evidence, commit SHA and peer review. Keep LIVE/REPLAY/MOCK and staged/real provenance visible. Never present an unimplemented feature as working.

Use `docs/project-plan.md` for full acceptance criteria, sponsor evidence and freezes. Public visibility, teammate access, deployment and license remain explicit setup choices.
