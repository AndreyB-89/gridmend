# GridMend sprint backlog

Current source: [ring-demo plan](project-plan.md). All times are Barcelona CEST, 19–20 September 2026.

**Publication status:** GitHub integration rejected issue creation after the organization transfer (403 Resource not accessible by integration). The nine tickets below are ready; no live issues or Projects board have been created by this update. Their canonical import payload is [sprint-issues.json](sprint-issues.json).

| Ticket | Sprint | Owner | Due | Dependencies |
| --- | --- | --- | --- | --- |
| [GM-01](#gm-01) — Confirm middle-ring specimen, scale and damaged capture set | S0 | Andrii | Sat 18:15 | See ticket |
| [GM-02](#gm-02) — Prove ring CAD runtime, Nebius access and small backend contract | S0 | Valentin | Sat 18:15 | See ticket |
| [GM-03](#gm-03) — Fit surviving ring geometry and generate checked CAD | S1 | Valentin | Sat 19:30 | See ticket |
| [GM-04](#gm-04) — Build capture, SLNG voice answers and dimension-review UI | S1 | Mortaza | Sat 19:30 | See ticket |
| [GM-05](#gm-05) — Connect Nebius interpretation, targeted questions and generation backend | S2 | Valentin | Sat 21:00 | See ticket |
| [GM-06](#gm-06) — Integrate damaged photo and voice into preview and CAD downloads | S2 | Mortaza | Sat 21:00 | See ticket |
| [GM-07](#gm-07) — Run Galtea, fix a genuine failure and preserve sponsor evidence | S3 | Andrii; Valentin supports the evaluation wrapper/fix | Sat 22:05; refresh after relevant fixes | See ticket |
| [GM-08](#gm-08) — Freeze integration, pass five cases and save a restartable demo | S3 | Mortaza; Andrii supports acceptance/recording | Sat integration freeze 22:05; stop 23:00 | See ticket |
| [GM-09](#gm-09) — Rehearse, freeze code and submit by Sunday deadline | S4 | Andrii; both developers support blockers | Sun code freeze 09:30; target submission 10:30; deadline 11:00 | See ticket |

## GM-01

**[S0][GM-01] Confirm middle-ring specimen, scale and damaged capture set**

**Owner:** Andrii
**Sprint:** S0
**Due (Barcelona CEST):** Sat 18:15
**Dependencies:** None

## Done when

- [ ] Confirm the card's actual size or supply a known-size alternative; record unknown until verified.
- [ ] Capture the broken middle ring from top and side with usable card edges and plane alignment; preserve intact comparison photos separately.
- [ ] Record profile observations, missing segment and T1–T5 expected outcomes; do not publish raw background screens or bystanders.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-02

**[S0][GM-02] Prove ring CAD runtime, Nebius access and small backend contract**

**Owner:** Valentin
**Sprint:** S0
**Due (Barcelona CEST):** Sat 18:15
**Dependencies:** None

## Done when

- [ ] Export and reopen a synthetic parameterized ring in STEP and STL; label synthetic dimensions.
- [ ] Save one actual Nebius image-model response and pin the available model.
- [ ] Provide FastAPI startup instructions and v2 mock payloads for Mortaza; no plate/revision/database scaffold.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-03

**[S1][GM-03] Fit surviving ring geometry and generate checked CAD**

**Owner:** Valentin
**Sprint:** S1
**Due (Barcelona CEST):** Sat 19:30
**Dependencies:** GM-01, GM-02

## Done when

- [ ] Rectify a verified card plane and fit surviving inner/outer arcs; manual boundary selection is supported.
- [ ] Obtain thickness/profile evidence or explicitly label the confirmed rectangular approximation; never seed missing dimensions.
- [ ] Generate current-parameter STEP/STL, reopen STEP and validate solid/bounds/profile/mesh; produce observed/restored overlay.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-04

**[S1][GM-04] Build capture, SLNG voice answers and dimension-review UI**

**Owner:** Mortaza
**Sprint:** S1
**Due (Barcelona CEST):** Sat 19:30
**Dependencies:** GM-02

## Done when

- [ ] Actual microphone audio reaches SLNG and returns a transcript; preserve a real run and latency.
- [ ] Operator can review a value and units, confirm it, and see the current parameter update; uncertain speech does not auto-confirm.
- [ ] UI supports top/side inputs, target/card corrections and clearly labeled mocks; microphone denial/silence have retry/type states.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-05

**[S2][GM-05] Connect Nebius interpretation, targeted questions and generation backend**

**Owner:** Valentin
**Sprint:** S2
**Due (Barcelona CEST):** Sat 21:00
**Dependencies:** GM-03, GM-04

## Done when

- [ ] Nebius combines damaged-image observations with reviewed voice answers and requests missing evidence.
- [ ] POST inspect/generate follow the v2 contract; fixed templates only, bounded inputs and actionable failure responses.
- [ ] Provide a Galtea callable wrapper for the same dialogue/interpretation path; T2–T5 fixtures remain distinct from acoustic evaluation.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-06

**[S2][GM-06] Integrate damaged photo and voice into preview and CAD downloads**

**Owner:** Mortaza
**Sprint:** S2
**Due (Barcelona CEST):** Sat 21:00
**Dependencies:** GM-03, GM-04

## Done when

- [ ] A fresh browser run completes actual image/voice/parameter/CAD flow without terminal intervention.
- [ ] Three.js previews the exported STL; STEP/STL/summary downloads belong to current parameters and stale links clear on edits.
- [ ] Run on the team laptop or an existing controlled host; timeout and generation failure show no false success.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-07

**[S3][GM-07] Run Galtea, fix a genuine failure and preserve sponsor evidence**

**Owner:** Andrii; Valentin supports the evaluation wrapper/fix
**Sprint:** S3
**Due (Barcelona CEST):** Sat 22:05; refresh after relevant fixes
**Dependencies:** GM-05, GM-06

## Done when

- [ ] Use Galtea to discover a consequential actual failure; preserve input, output, model/prompt and build.
- [ ] Valentin fixes the actual cause, then rerun the same failing input and all five acceptance cases; report absence of discovery honestly.
- [ ] Save actual Nebius/SLNG traces and Galtea before/after results, and complete Galtea's feedback survey.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-08

**[S3][GM-08] Freeze integration, pass five cases and save a restartable demo**

**Owner:** Mortaza; Andrii supports acceptance/recording
**Sprint:** S3
**Due (Barcelona CEST):** Sat integration freeze 22:05; stop 23:00
**Dependencies:** GM-06, GM-07

## Done when

- [ ] T1–T5 pass or remaining gaps are recorded; no new providers/templates/interfaces after 22:05.
- [ ] Export checks and two full successful journeys are recorded; README contains actual restart instructions.
- [ ] Save demo recording, sample CAD, evidence and morning blocker list before the hard 23:00 stop; no overnight work.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## GM-09

**[S4][GM-09] Rehearse, freeze code and submit by Sunday deadline**

**Owner:** Andrii; both developers support blockers
**Sprint:** S4
**Due (Barcelona CEST):** Sun code freeze 09:30; target submission 10:30; deadline 11:00
**Dependencies:** GM-08

## Done when

- [ ] Resume 09:00; fix integrated blockers only, rerun affected cases and tag final build at 09:30.
- [ ] Complete two timed rehearsals; verify repo, video, CAD and sponsor evidence links with honest CAD-only/approximation labels.
- [ ] Save actual submission receipt by 10:30 where possible and reserve 10:30–11:00 for access/submission problems.

## Evidence

Attach actual output/test results, commit and peer review.

[Current plan](https://github.com/HackBarna-GridMend/gridmend/blob/main/docs/project-plan.md)


## Create the issues

Once the connector has repository Contents and Issues write access, it can create these tickets directly. Alternatively, a teammate with authenticated GitHub CLI access can run:

```bash
python3 scripts/import_sprints.py
python3 scripts/import_sprints.py --apply
```

The first command previews only. The second creates missing issues; exact existing titles are skipped. Owner names are written in the body; GitHub assignees are deliberately unset until teammate usernames are known. The importer requires GitHub CLI (`gh`) installed and authenticated; it does not read or print tokens.

## Optional GitHub Projects board

Open [the organization Projects page](https://github.com/orgs/HackBarna-GridMend/projects) → New project → Board. Name it **GridMend — HackBarna delivery**. Select **Import items from repository** and choose `HackBarna-GridMend/gridmend` after the nine issues exist. GitHub documents this setup in [Creating an organization project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/creating-a-project).

Use the built-in Status columns Todo / In progress / Done. Optional: add a Sprint single-select field with S0, S1, S2, S3, S4 and populate it from the issue-title prefix. For this one-weekend event, custom iterations/automation are unnecessary. Keep due times in issue bodies; assign real teammate usernames when known.

The connected tool set has no Projects creation/write operation. Repo Issues remain sufficient to work from if a board is not created.
