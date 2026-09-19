# Team working agreement

Current scope: broken middle yellow ring → checked STEP/STL, with no printer. Read [the current plan](docs/project-plan.md) and [sprint issues](docs/sprints.md). Plate v1.1 material is archived; do not implement it.

| Owner | Files and responsibility |
| --- | --- |
| Andrii | Fixtures, experiment, acceptance runs, evidence, pitch/submission; protects scope |
| Valentin | engine/, cad/, evals/, inspection/generation routes and backend bootstrap |
| Mortaza | web/, voice/files routes, integration and serving |

Both developers agree on contracts/types.ts (v2). Valentin mirrors it in Pydantic. Keep branches short (e.g. feat/ring-fit, feat/voice-review); open a PR into main, obtain peer review, and integrate completed slices continuously.

Each ticket needs one owner, an observable outcome, a testable done-when, relevant failure behavior and an evidence link/build commit. Andrii reviews geometry/accuracy claims. LIVE/REPLAY/MOCK must stay visible. Do not use intact reference photos as undeclared inputs to a damaged-only demonstration.

Integration freeze Sat 22:05; stop 23:00; resume Sun 09:00; code freeze 09:30; submit by 10:30 with buffer to 11:00. No new feature after integration freeze. No overnight tasks.

The repository is public in HackBarna-GridMend. Do not commit provider credentials or unreviewed photographs of background screens/bystanders. Local raw captures stay outside version control unless deliberately selected for publication. Licensing is still unselected.
