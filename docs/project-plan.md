# The demo must turn a photograph of the broken middle ring and a short spoken exchange into a reconstructed, downloadable STEP/STL model.

## What we're building

**GridMend — recover missing geometry from a damaged part.**

Repository: [HackBarna-GridMend/gridmend](https://github.com/HackBarna-GridMend/gridmend).

The physical specimen is Andrii's **middle yellow ring**, separated from the nested spinner. A known-size card provides scale. The app estimates surviving geometry, asks for missing information, highlights the restored section and generates an intact ring model.

**No printer is available. Success ends with checked CAD files and an interactive preview.** There is no physical-fit, free-motion, manufacturing-accuracy or service-qualification claim.

**Application: legacy 110 kV substation accessories. Demonstration: reconstruct one simple broken ring.** Customer hypothesis: maintenance teams sometimes lack usable CAD or timely replacements for legacy, discontinued accessories. Andrii supplies one concrete example if available; do not invent lead times or assert demand has been validated.

The existing substation work remains a product foundation: a generic 110/10 kV schematic across 10 equipment families, 36 illustrative component-type records, and 27 draft manufacturing options across 13 records. It provides the intended component-identification and process-selection context. The ring demonstrates the geometric reconstruction step in a controlled physical example; it does not establish industrial suitability.

**Roadmap:** existing substation/library foundation → ring photo-and-voice-to-CAD demonstration → one verified industrial accessory → manufactured/inspected specimen → controlled asset workflow. See [product roadmap](roadmap.md) for gates and candidate categories, and [pitch](pitch.md) for the presentation. No additional application features are added to this weekend's ring scope. All catalog manufacturing candidates remain NOT_APPROVED.

This plan supersedes the plate plan and contract v1.1. Historical material is retained under `docs/archive/` and `contracts/archive/`; the current contract is `contracts/types.ts`. No new database, complex revision protocol or plate generator is required.

### Facts and assumptions

| ID | Fact / assumption | Consequence or response if wrong |
| --- | --- | --- |
| F1 | Team: Andrii—product/energy; Valentin—ML/software; Mortaza—full stack/cloud/AI. | Ownership below is authoritative for this demo. |
| F2 | No printer. Finish Saturday at 23:00; restart Sunday at 09:00; submit by 11:00 Barcelona time. | CAD files are the deliverable. No overnight work or physical print milestone. |
| F3 | Intact and broken middle-ring photographs, including groove close-ups, have been supplied. Dimensions remain unverified. | Andrii checks capture/calibration quality before the main reconstruction test. Do not label intact photographs as damage evidence. |
| A1 | Revised remaining-work baseline is Saturday 19 September **17:45 CEST**. | If late, reduce polish and optional speech output; recompute the 60% freeze using active work time, preserving the sleep interval and submission deadline. |
| A2 | The Calicéo card is ID-1 size, nominally 85.60 × 53.98 mm, only after Andrii confirms that format. | Until confirmed, keep metric dimensions null; use another known-size reference. A familiar logo does not establish size. |
| A3 | A substantial undistorted arc survives, and the selected ring was circular. | If fragments are bent, perspective is unresolved or circle fit is unstable, request another view/fragment arrangement. Do not force a nominal circle. |
| A4 | The ring has an axisymmetric cross-section that can be established from exposed surfaces. | Hidden grooves/pivots cannot be reconstructed from these photos. Permit an explicitly confirmed rectangular-envelope approximation, labeled as such; do not call it an exact replacement. |
| A5 | Nebius vision, SLNG STT and CadQuery are usable by 18:15. | Test immediately. If unavailable, record the blocked sponsor/function; do not silently replace live inference or generation with a replay. |
| A6 | Main pitch is five minutes; an English speaker and ordinary phone/laptop microphone suffice. | Use the three-minute script if required. Translation and continuous conversation are out of scope. |
| A7 | Existing generic assets may be reused under event rules. | Andrii checks eligibility; main ring path must work without them. |

Current photos include a surviving broken arc and a close-up supporting an inner concave groove. Andrii reports an outer convex bulge mating with the surrounding ring. Exact cross-section dimensions remain unknown. The USB connector in the latest close-up is not a calibrated scale. The top image provides a useful target view. Side image 3 is the clearest of the supplied side views, but coplanarity and exact profile remain unverified. Some card edges are partly obscured in other images. Andrii should capture a clean side view of the selected ring with all card edges visible and aligned to the measured side. Intact photos are held-out comparison material for the principal damaged-only run; any intact-photo assistance must be disclosed separately.

References: [ID-1 dimensions](https://www.iso.org/standard/31432.html), [planar perspective correction](https://docs.opencv.org/4.5.1/d9/dab/tutorial_homography.html). Card calibration applies to its plane; raised surfaces and camera distortion still introduce error. Do not assign an unmeasured ±mm accuracy claim.

## Scope

| MoSCoW | Deliverable |
| --- | --- |
| **Must** | One damaged middle ring; known-scale top/side capture; operator-adjustable target/card outlines; real Nebius interpretation; real SLNG voice answers; spoken profile correction with preview and separate confirmation; dimension confirmation; one axisymmetric ring CAD generator; damaged/restored comparison; actual STEP/STL/JSON downloads; independent file checks; five acceptance cases; actual sponsor evidence; pitch showing the existing substation/catalog foundation and industrial roadmap; recording and submission. |
| **Should** | Automatic edge detection with manual correction; spoken questions through SLNG TTS; automatic side-profile polygon capture; held-out intact-photo comparison; stable hosted demo if existing deployment is quick. |
| **Could** | A second ring size using the same generator; an in-app link to the existing substation model. The substation/catalog story is already required in the pitch. |
| **Won't** | Printing or fit claims; the full spinner mechanism; hidden joint reconstruction; arbitrary image-to-exact-CAD; generative meshes presented as manufacturing CAD; new model training; cups or plates as a second main path; full substation scene rebuild; SQL database; accounts; idempotency/revision/hash framework; automatic machine control; unmute, telephony, translation; a fourth sponsor integration. |

Andrii protects scope. No new template, provider or feature after integration freeze. Manual edge correction is an honest supported interaction, not a hidden backstage operation. Loss of a core function is reported as a gap, not reclassified as success.

## Tools

| Tool | Necessary role | Evidence for judges |
| --- | --- | --- |
| **Nebius Token Factory** | Interpret photo plus dialogue: selected part, missing section, circularity hypothesis, next question. | Actual model/run and an output that changes the workflow. Pixel measurement is performed by geometry code, not guessed by the language model. |
| **SLNG STT** | Spoken answers provide dimensions, corrections and shape confirmations used in modeling. | Actual audio→transcript→confirmed parameter→updated CAD trace; measured latency. TTS is optional. |
| **Galtea** | Probe dialogue/interpretation failures, fix a real cause and rerun. | Genuine failing input, fix and before/after result; mandatory feedback survey. |
| OpenCV + NumPy | Card-plane rectification, contour/circle fitting and overlays. | Visible detected boundaries and repeatable measurements; manual selection fallback. |
| CadQuery/OpenCascade | Fixed ring template: annular extrusion or revolved axisymmetric profile; STEP/STL export. | New CAD generated from the current parameters; valid reimport. |
| React + TypeScript + Three.js | One screen: images, voice, parameter review, actual exported-mesh preview. | Operator completes the journey without terminal intervention. |
| FastAPI + local files | Small HTTP interface, provider calls and synchronous generation. | One process; no database, queue platform or login system. |

Sponsor summaries follow the [official challenge page](https://www.hackbcn.com/en/events/aisummit26). Nebius requires a meaningful core role; SLNG accepts core STT/TTS use; Galtea requires actual discovery/fix/rerun and its [survey](https://tally.so/r/J9Pyar). Norma is not a delivery requirement. Do not plant flaws to manufacture prize evidence.

Keep provider credentials server-side. Use the team laptop/local server as the baseline; a public GitHub repo does not require an unrestricted public paid-inference endpoint. Mortaza uses an already-available controlled host if practical. Pin the working SDK/model versions after the dependency spike. [SLNG docs](https://docs.slng.ai/), [Nebius docs](https://docs.tokenfactory.nebius.com/quickstart), [Galtea docs](https://docs.galtea.ai/quickstart), [CadQuery docs](https://cadquery.readthedocs.io/en/latest/intro.html).

## Roles

| Owner | Deliverables | File ownership |
| --- | --- | --- |
| **Andrii — product / scope / experiment** | Prepare specimen and captures; confirm scale/profile truth; run acceptance cases; operate Galtea once wrapper exists; preserve evidence; prepare the substation/catalog roadmap visual; pitch and submit. | `fixtures/`, `evidence/`, `docs/` |
| **Valentin — geometry / inference / CAD** | Nebius reasoning; OpenCV fitting; CAD/profile generator and checks; small inspection/generation backend; Galtea callable wrapper. | `engine/`, `cad/`, `evals/`, `api/routes/inspect.py`, `api/routes/generate.py`, backend bootstrap |
| **Mortaza — interaction / voice / integration** | Capture UI, microphone + SLNG endpoint, parameter confirmation, Three.js preview, downloads, local/hosted serving, browser verification. | `web/`, `api/routes/voice.py`, `api/routes/files.py`, deployment |

Both developers agree on `contracts/types.ts` before implementing; Valentin mirrors it in Pydantic. Andrii handles specimen preparation and evidence collection while code is built. The other developer reviews changes affecting the shared interface. GitHub usernames for Valentin/Mortaza are not established; issue bodies name owners without guessing account assignments.

## Timeline

**Barcelona CEST. Saturday 19 September → Sunday 20 September 2026.** Remaining active time from 17:45 is 315 minutes tonight + 120 tomorrow = **435 minutes**. Integration freeze at **22:05** is 260/435 ≈ **60%**. Code freeze Sunday **09:30** is approximately 79% of active time. The official code deadline is Sunday 11:00; the team stops work tonight at 23:00.

| Sprint | Time | Goal | Done when |
| --- | --- | --- | --- |
| **S0 — Select and prove** | Sat 17:45–18:15 | Confirm specimen/scale and eliminate runtime access risk. | Andrii has the selected ring and capture checklist; actual Nebius/SLNG calls succeed; a parameterized test ring exports/reimports STEP/STL; both developers accept the small contract. No claim that test dimensions came from the photos. |
| **S1 — Two working halves** | 18:15–19:30 | Geometry path and voice/UI path each work. | Valentin obtains fitted inner/outer boundaries on an actual image and exports a ring; Mortaza records real audio, displays transcript and changes a reviewed parameter. Typed mocks are visibly labeled. |
| **S2 — One complete journey** | 19:30–21:00 | Integrate damaged photo + voice + scale → files. | A new damaged-ring run produces downloadable CAD; the missing region is highlighted; thickness/profile questions are visible; Galtea baseline begins. |
| **S3 — Evidence and integration freeze** | 21:00–22:05 | Fix actual failures and close promised scope. | Five cases pass; real sponsor evidence is saved or gaps named; all endpoints/templates/providers integrated. **At 22:05 no new features, dependencies or interfaces.** |
| **S3 — Stabilize and stop** | 22:05–23:00 | Leave a reproducible demo before sleeping. | Core path succeeds twice; files reopen; recording and local copies exist; outstanding blockers are written down. **Stop at 23:00.** |
| **REST** | 23:00–09:00 | Sleep. | No scheduled overnight work or unattended requirement. |
| **S4 — Fix blockers only** | Sun 09:00–09:30 | Recover the same integrated build. | Rerun affected tests; final code tagged. **Code freeze at 09:30.** |
| **S4 — Rehearse and submit** | 09:30–10:30 | Finish pitch and submission. | Two timed rehearsals; repo/video/files/evidence links verified; actual submission receipt saved by 10:30. |
| **Buffer** | 10:30–11:00 | Resolve submission/access issues. | Submission confirmed by official deadline; no feature work. |

If no image-derived geometry works by 19:30, both developers prioritize assisted edge selection and circle fitting. If runtime CAD still fails, stop UI polish. If voice fails, retain labeled typed fallback but mark SLNG incomplete. At 21:00 drop optional TTS/profile polish; do not drop the CAD path to chase extra prizes.

Sprint issue index and optional board setup: [sprints.md](sprints.md).

## Data contract

**Ring-demo v2**, replacing the plate contract. No database IDs for photos, auth/revision subsystem or idempotency protocol. The browser holds the current inspection and parameters; files are stored for the demo run. Explicit unknowns and confirmations are retained because they change model geometry.

```typescript
// GridMend ring-demo contract v2. Planning contract, not a running implementation.
// Every field is required. Unknown values are null; arrays are [] when empty.
export type Point = [number, number]; // image pixels, top-left origin
export type Mode = "LIVE" | "REPLAY" | "MOCK";
export type DimensionName = "outer_diameter" | "inner_diameter" | "thickness";
export interface Dimension {
  value_mm: number | null;
  source: "PHOTO" | "SPOKEN_MEASUREMENT" | "MANUAL_MEASUREMENT" | null;
  confirmed: boolean;
}
export interface Calibration {
  card_size_mm: [number, number] | null; // known width/height; never inferred from logo
  size_confirmed: boolean;
  corners_px: [Point, Point, Point, Point] | null; // map to (0,0),(w,0),(w,h),(0,h); account for card rotation
  same_plane_confirmed: boolean; // card face and measured feature plane
}
export interface InspectContext {
  top_calibration: Calibration;
  side_calibration: Calibration | null;
  top_roi_px: [number, number, number, number] | null; // x,y,width,height
  reviewed_voice_text: string; // <=2,000 chars; operator-confirmed transcription
  operator_note: string; // <=1,000 chars; data, not instructions
}
export interface Trace {
  provider: "NEBIUS" | "SLNG";
  model: string;
  mode: Mode;
  latency_ms: number;
  request_id: string | null;
}
export interface InspectResult {
  status: "NEEDS_INPUT" | "REVIEW" | "UNSUPPORTED";
  observations: string[];
  question: string | null;
  outer_diameter: Dimension;
  inner_diameter: Dimension;
  thickness: Dimension;
  top_overlay_url: string | null; // registered app artifact, not a model-generated URL
  warnings: string[];
  trace: Trace;
}
export interface VoiceResult {
  transcript: string; // raw result; operator reviews before use
  trace: Trace;
}
export interface GenerateRequest {
  outer_diameter: Dimension;
  inner_diameter: Dimension;
  thickness: Dimension;
  profile_rz_mm: Point[] | null; // closed polygon cross-section: radius,z; closing point implicit
  profile_basis: "OBSERVED" | "SIMPLIFIED_RECTANGLE";
  profile_confirmed: boolean;
  purpose: "DEMO_CAD_ONLY";
}
export type ProfileFeature = "INNER_GROOVE" | "OUTER_BULGE";
export interface ProfileEditRequest {
  accepted: GenerateRequest;
  reviewed_voice_text: string; // <=2,000 chars; one correction, not confirmation
}
export interface ProfileEditResult {
  feature: ProfileFeature | null;
  candidate: GenerateRequest | null; // null means clarification required; never auto-confirmed
  readback: string; // feature, old/new values, units and measurement vs design adjustment
  question: string | null;
  limitations: string[]; // preserve with accepted model and include in exported summary
  trace: Trace;
}
export interface CadCheck {
  name: "SOLID" | "DIMENSIONS" | "PROFILE" | "STEP_REIMPORT" | "STL_MESH";
  passed: boolean;
  detail: string;
}
export interface GenerateResult {
  status: "READY";
  design_id: string;
  step_url: string;
  stl_url: string;
  summary_url: string; // JSON: GenerateRequest + checks + limitations
  checks: CadCheck[];
  limitations: string[];
  physical_fit_verified: false;
}
export interface ApiError {
  error: "INVALID_INPUT" | "NEEDS_INPUT" | "PROVIDER_FAILED" | "TIMEOUT" | "CAD_FAILED";
  message: string;
}
```

| API | Input | Output / failure |
| --- | --- | --- |
| `POST /api/inspect` | Multipart `top_image` required, `side_image` optional, `context` = JSON InspectContext. | 200 InspectResult. Re-submit with updated context when the operator corrects boundaries or adds evidence. Preserve measurements already confirmed in the UI; show new estimates separately. |
| `POST /api/voice` | Multipart `audio` file; English, one speaker, ≤30 seconds. | 200 VoiceResult. Operator reviews transcript before it becomes `reviewed_voice_text`. Silence is an error, not a fabricated answer. |
| `POST /api/profile-edit` | JSON ProfileEditRequest; reuse Nebius interpretation and fixed profile operations. | 200 ProfileEditResult. Candidate has profile_confirmed=false; changed dimensions are unconfirmed. Null candidate requires a question. Confirm/cancel/undo are client actions on the visible proposal. |
| `POST /api/generate` | JSON GenerateRequest. | 200 GenerateResult only after export checks. 422 missing/invalid inputs; 500 CAD_FAILED. |
| `GET /api/files/{filename}` | Server-issued basename from a result. | File bytes; 404 unknown file. Reject traversal; no arbitrary paths or model-created URLs. |

Errors use ApiError; provider failure 502, timeout 504. Limit each image/audio upload to 10 MiB and decoded images to 20 megapixels. JPEG/PNG/WebP images; pin audio encodings to the actual tested SLNG model. Maximum provider wait 30 seconds, CAD 30 seconds; sequential runs on the demo laptop. Do not return raw provider secrets/errors.

All numbers are finite; millimetres for CAD. Null values have source=null and confirmed=false. POST /generate recomputes validity and ignores no invalid fields; reject unknown fields. New edits immediately clear old preview/download links until a new successful generation. No stale CAD displayed as a new result.

For profile edits, validate the candidate before returning it; derive inner/outer diameters from minimum/maximum profile radius. Preserve the edit readback and limitations alongside the generated summary in the downloaded JSON. An adjustment with no measurement basis must not be assigned a measurement source.

`profile_rz_mm` uses radius from the ring axis and height from its bottom; at least 4 and at most 16 vertices for an observed, simple closed cross-section, within the confirmed inner/outer radius and height. No self-intersection or negative radius. A null profile is permitted only with `profile_basis=SIMPLIFIED_RECTANGLE` and `profile_confirmed=true`; result labels the approximation. Hidden mechanism fit is never asserted.

No fabricated nominal dimensions are seeded. [ring-demo.json](../fixtures/ring-demo.json) starts with null dimensions. Separate synthetic numeric fixtures may test the generator, but are labeled synthetic and never presented as measured specimen values.

## Core logic

1. **Select the middle ring.** Do not measure the full nested stack or the brown spinner. Operator corrects the target region.
2. **Establish scale per view.** Confirm card dimensions and identify four nominal rectangular corners from its straight edges, accounting for rounded corners. Use a planar transform only when the card and measured feature share a plane. Top and side calibrations are separate.
3. **Find surviving arcs.** Exclude fracture edges, shadows, card and other rings. Fit inner/outer circles in the rectified top view. Require at least a half-circle of distributed surviving support for this demo (a conservative capture heuristic, not an accuracy guarantee). Insufficient support or inconsistent contours → ask for another view; preserve uncertainty. Do not measure the damaged outline's bounding box as the original diameter.
4. **Recover the missing region.** Under the confirmed circular-ring hypothesis, extend the fitted boundaries around the missing section. Overlay observed edges and restored section in different colors. Image processing supplies measurements; Nebius interprets context and chooses the next question.
5. **Resolve thickness/profile.** Represent the inner groove and outer bulge in a radius-height cross-section, then revolve it 360° if circumferential uniformity is confirmed. The polygon is a faceted approximation of curved surfaces; disclose this. Visible lip diameters may differ from groove-root and maximum-bulge diameters. Fracture cavities/infill are not automatically design features. Side capture supplies thickness only with usable scale/plane alignment. Inspect exposed surfaces. A plain annulus is acceptable only as an explicitly selected envelope approximation if the true profile is unresolved. Lettering is cosmetic and omitted with disclosure.
6. **Use speech as input and correction.** Follow the profile-edit interaction below. The app asks a short question. SLNG transcribes the answer; the operator confirms the displayed value and units. “Maybe 9 or 19” remains unknown. A clear confirmed measured value can update a dimension. “Looks about…” is an estimate requiring measurement, not an automatic confirmation.
7. **Generate deterministically.** Require positive dimensions, outer>inner, bounded size (outer ≤200 mm, thickness ≤50 mm, demo limits), profile confirmation and a fixed template. Never run model-generated Python or shell.
8. **Check files, then publish.** One valid solid; expected bounds and profile; STEP reimport repeats checks; STL is closed/manifold with positive volume. Compare CAD against requested parameters within numerical tolerance 0.05 mm. This checks software output, not photographic or manufacturing accuracy.

InspectResult dimensions are initially unconfirmed. A voice answer or visual correction must not silently become confirmed. CAD summary records source values, approximation labels and physical_fit_verified=false. Compare held-out intact photographs only after the damaged-input run; without independent metrology, call this a consistency comparison, not an accuracy measurement.

### Voice-guided profile correction

**Build target, not an implemented capability claim.** Keep this inside GM-03 through GM-06; no general CAD assistant or extra sponsor. SLNG supplies real speech transcription; Nebius interprets a bounded edit; fixed geometry code builds the proposed profile. Spoken readback through TTS remains optional: visual readback is required.

| Step | Operator / app behavior |
| --- | --- |
| Identify | “The inside has a groove; the outside bulges.” Highlight INNER_GROOVE or OUTER_BULGE in the cross-section. Qualitative description establishes feature intent, not its millimetre dimensions. |
| Correct | Operator specifies a measured profile value, or an explicitly labeled design adjustment. “Make the inner groove 0.5 millimetres deeper” is an example adjustment, not a measurement of this specimen. |
| Preview | Show old/new profile overlay, feature name, units, direction and changed values. Groove depth is radial; increasing it moves the groove root away from the axis and changes its local diameter by twice the radial change. Reject edits that leave no wall or invalidate the profile. |
| Clarify | “Rounder”, an unknown starting depth, unclear feature or missing units produces a targeted question. No arbitrary curve or dimension is invented. |
| Confirm | Only a separate “Confirm” after the proposal is visible accepts that pending edit. “Cancel” discards it. “Undo” restores the immediately previous accepted profile. One combined “change it and confirm” utterance creates a proposal only. |
| Export | Accepted edits invalidate previous downloads. Recompute profile bounds, validate and regenerate through the existing generator; preview the resulting exported STL. |

Client state is only `accepted`, `pending` (nullable) and `previous` (nullable). A pending profile preview is labeled DRAFT; it is not a passed CAD export. Confirmation binds to the displayed proposal, is disabled while another speech request is running, and is cleared by a new edit. Typed controls provide the same confirm/cancel/undo actions. No revision service or database is added.

**Assumption A8:** one axisymmetric, piecewise-linear profile captures enough visible shape for the CAD-only demonstration. If wrong, ask for additional profile evidence or explicitly select the envelope approximation. Keep exact-fit claims out. Synthetic adjustments must be labeled in the exported summary; operator acceptance does not turn a design choice into a measured fact.

## Integration flow

```text
Damaged top/side photos + confirmed scale card
  → selected ring + rectified views + surviving-arc fit
  ↔ Nebius interpretation and targeted question
  ↔ SLNG spoken correction → highlighted feature + draft profile
  ↔ separate spoken confirmation / cancel / undo
  → dimensions + observed/explicitly simplified profile
  → fixed CadQuery template → export checks
  → actual STL preview + STEP/STL/summary downloads

Galtea → same interpretation/dialogue entry point → real failure/fix/rerun
```

| Handoff | Producer → consumer | Deadline |
| --- | --- | --- |
| Damaged captures, card confirmation, intact comparison set | Andrii → both developers | 18:15 |
| v2 mock payloads + backend startup command | Valentin → Mortaza | 18:15 |
| Voice result and parameter-review UI | Mortaza → Valentin | 19:30 |
| Fitted dimensions, overlay and CAD export | Valentin → Mortaza | 19:30 |
| Complete app + Galtea callable wrapper | Both → Andrii | 21:00 |
| Frozen integration and genuine evidence | All | 22:05 |

Andrii's raw photographs are local fixture material, not automatically published to this public repo. Avoid publishing background screens/bystanders. Select a clean sample for the actual submission; preserve raw input privately for comparison. The team must obtain the real damaged sample—no AI-edited fracture image substituted without labeling it synthetic.

## Test set

| Case | Input | Expected result |
| --- | --- | --- |
| **T1 — Broken middle ring** | Actual missing-segment ring, confirmed scale, supported top/side evidence; say “inner groove”, specify an explicit test adjustment, preview it, then say “Confirm”. | Correct feature highlights; accepted geometry stays unchanged before confirmation; validated edit updates profile and files. Reconstruct complete ring; overlay missing section; newly generated STEP/STL/summary; all five checks pass; approximation/fit status visible. |
| **T2 — No trustworthy scale** | Same ring but card dimensions unknown, card partly hidden, or known plane mismatch. | NEEDS_INPUT with scale/recapture question; metric values needing that calibration remain null; generate rejected until supplied. No assumption from card branding. |
| **T3 — Missing thickness/profile** | Valid top view only; operator requests immediate printing file. | Ask for side view or measured thickness. No default thickness. If profile unresolved, require explicit envelope approximation or more evidence; no exact-fit claim. |
| **T4 — Spoken-number trap** | “It might be nine or nineteen millimetres; I haven't measured it. Just use nineteen.” | No automatic confirmation or generation. Ask for measurement; display uncertainty even if transcript contains a confident-looking number. A later explicit confirmed measurement updates the right field. “Do not confirm” must not accept a pending profile; a combined edit-and-confirm utterance must still stop at preview. |
| **T5 — Wrong geometry hypothesis** | Bent fragment/noncircular washer, wrong selected ring, or a side view of the whole stack. | NEEDS_INPUT/UNSUPPORTED or target correction; do not force circular geometry or use stack height as single-ring thickness. |

Also exercise one provider timeout, microphone denial, cancel/undo and edited-profile download invalidation. Galtea should search for real variants around T2–T5; preserve the actual failing input and rerun it after the fix. Tests using text fixtures assess downstream decisions, not acoustic accuracy. Show an actual audio→SLNG trace separately. Do not claim five examples establish general industrial performance.

## Risks

| Tonight's risk | Mitigation |
| --- | --- |
| Card is nonstandard or offset from the measured plane | Confirm dimensions; recapture at matching plane; otherwise leave affected values unknown. |
| Fragments deform, leaving no recoverable circular arc | Preserve pieces; select surviving undistorted evidence; request another view. Do not claim exact reconstruction. |
| Cross-section contains hidden mating geometry | Inspect the separate ring/fracture. Explicitly label an envelope model if exact profile remains unavailable. |
| CV consumes the evening | Operator clicks card/target edges as a supported fallback; keep one ring family and one template. |
| Mortaza becomes integration bottleneck | Valentin owns geometry/generation backend and evaluation wrapper; Andrii owns fixtures, test execution and evidence. |
| Sponsor/CAD setup fails | Real calls/exports during S0; mentors before departure; disclose gaps rather than fake live use. |
| Nice preview differs from export | Load the exported STL itself; reopen STEP and inspect computed geometry. |
| Voice guesses a dimension or loses negation | Visible value/unit confirmation; uncertainty handling; T4 and Galtea adversarial tests. |
| Gallery photo accidentally becomes alleged damaged input | Separate intact reference set; visibly label every staged/recorded run. |
| Late changes consume sleep/submission | Integration freeze 22:05, hard stop 23:00, code freeze 09:30, submit 10:30. |

## Demo script

**Show the substation application first, the ring reconstruction next, then the industrial roadmap.** Andrii uses existing assets; no new substation UI build. Full wording and judge Q&A: [pitch.md](pitch.md).

| Time | Say / show | Evidence boundary |
| --- | --- | --- |
| **0:00–0:35** | Show the existing generic 110 kV substation model and point to an accessory category. “Our application is maintenance of legacy substation equipment, where a replacement accessory or its CAD may be difficult to obtain.” | Label the scene generic and the availability problem a hypothesis unless supported by a real example. |
| **0:35–0:55** | Hold up the broken middle ring. “This simple specimen lets us demonstrate one essential step: recovering missing geometry from photos and an engineer's answers.” | The ring is a lab proxy. It is not a substation-qualified part. |
| **0:55–2:40** | Run damaged image + card calibration. Say “The inside has a groove”; show the highlighted cross-section, make one explicit profile correction, preview it and say “Confirm”. Show surviving arcs and the restored segment. | Real Nebius/SLNG calls if working; mark replay/manual corrections openly. |
| **2:40–3:20** | Rotate the generated ring; show restored geometry and actual STEP/STL downloads. | Show independent export checks and any profile approximation. No printer is available; fit and motion are untested. |
| **3:20–4:00** | Show a genuine Galtea-discovered failure, the fix and rerun. | If no failure was discovered, report that rather than fabricating a story. |
| **4:00–4:40** | Return to the catalog: “We already have an illustrative component library and draft manufacturing routes. The next stage connects this reconstruction workflow to one verified industrial accessory.” Show polymer AM, CNC metal and sheet-fabrication candidates. | Library records are authored screening proposals, not approved replacements or implemented reconstruction coverage. |
| **4:40–5:00** | “Our next validation is one real accessory, a reviewed material/process choice and an independently inspected specimen.” Name the partner/evidence sought. | No invented customer commitment, savings, accuracy or deployment claim. |

Three-minute version: substation application 0:00–0:25; ring photo/voice 0:25–1:25; CAD/download 1:25–2:00; actual failure/fix 2:00–2:30; industrial roadmap and next validation 2:30–3:00.


Fallback: after a provider timeout, explicitly switch to a recorded run and show when it was captured. Keep CAD generation live if its engine works. A static CAD file/recording is backup evidence, not proof the current run reconstructed the object. Rehearse twice before submission.

## Definition of done

Every ticket has one named owner, one observable outcome, a testable done-when and an evidence link. Done requires the actual consumer path, one relevant failure case and peer review. A screenshot alone does not prove export, provider use or physical accuracy. Record exact commands/build commit in evidence; do not invent pass results.

Project done when:

- [ ] Actual broken middle-ring capture → voice-supported reconstruction → newly generated CAD works from a fresh browser session.
- [ ] A spoken profile correction highlights the intended feature, previews before acceptance, and supports separate confirm/cancel/undo; no unmeasured adjustment is labeled measured.
- [ ] Current parameters, preview and downloads agree; STEP/STL independently pass checks.
- [ ] T1–T5 behave as specified; scale, thickness and uncertainty are not guessed into confirmed values.
- [ ] No physical-print/fit claim; profile approximation and photo-derived measurement limitations are explicit.
- [ ] Actual Nebius and SLNG traces saved; genuine Galtea discovery/fix/rerun and survey saved, or missing prize evidence marked incomplete.
- [ ] Team can restart the build using README commands added by implementation owners.
- [ ] Pitch distinguishes the existing substation/catalog foundation, demonstrated ring behavior and future industrial validation; no catalog-based reproducibility percentage.
- [ ] Final repo, video, sample CAD and evidence links work; receipt saved before Sunday 11:00.
