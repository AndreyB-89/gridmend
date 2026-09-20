# Astra prompt — video to missing-part STL

Implement the workflow below in GridMend. Deliver working code and verification, not only a plan. Preserve the current UI design. Read `CLAUDE.md`, `docs/status.md`, the contracts, and the relevant code first. Preserve unrelated work.

## User outcome

I upload a video of a broken object and write a short message in the existing chat, for example: “Create the missing part of this ring.” Nebius asks the end user for the intended intact object’s required dimensions; dimensions are never inferred from the video. The app builds the complete reference CAD first. It then sends the original video, the complete reference STL, and the confirmed specification to Devin through its API. Devin autonomously creates the STL of the missing material. Our server validates the result and sends actionable failures back to Devin for up to 100 retries. Log the entire observable workflow. The existing viewer and downloads present the validated result.

“Complete reference” means the intended object before damage: a complete ring retains its central hole; a cylinder or box retains any explicitly specified cavity. It does not mean the surviving fragment or the replacement piece. Resolve solid-versus-hollow ambiguity in chat.

## Scope and UI

- Keep the layout, styling, chat, viewer, and visual language. No redesign, wizard, extra page, or separate Devin dashboard. Reuse the current upload control for video; make only necessary input, preview, chat-state, and download-label changes.
- Present questions, confirmation, progress, retries, and failures in the existing chat. Reuse the existing confirmation/build controls where appropriate. After sufficient input and confirmation, do not require manual coordination of Devin.
- Support ring, cylinder, and box reference primitives. Keep the existing photo/ring path working. Do not turn this into arbitrary object reconstruction or a new infrastructure project.
- The old project freeze and file-owner rules exist. This note specifies a requested feature beyond the old scope; surface any still-required owner/contract approvals before affected edits. Do not claim that both developers have approved a contract change. Keep Python and TypeScript contracts synchronized once changes are authorized.

## 1. Video ingestion and Nebius dialogue

Accept real video bytes server-side, store them outside git, and retain an identifier tied to this reconstruction. Validate actual media, duration, and size; handle invalid or oversized input clearly. Choose bounded limits that accommodate the project's real sample clips; do not reuse the current 10 MB photo limit blindly. Extract a bounded set of useful timestamped frames with deterministic media tools. Keep the original video for Devin.

Use a high-capability Kimi, Qwen, or DeepSeek model served by Nebius. At implementation time, query the account's model list and verify modality and structured-output support with a small real request. Select and record the exact available model ID and why it fits this task. Do not guess an ID, assume every family supports images/video, or retain Gemma as the default for this new path. Prefer a strong multimodal model from the requested families; if necessary, use separate compatible vision and reasoning models from those families and disclose both.

Maintain a structured conversation state: user goal, object family, observations with frame references, user-supplied dimensions with feature identification, units and confirmation, unresolved questions, and current reference revision. Feed that state and relevant conversation context into subsequent turns. Ask for every required dimension not yet supplied: outer diameter, inner diameter and axial height for a plain ring; diameter and height for a solid cylinder; length, width and height for a solid box. Ask for wall thickness or other parameters when cavities or features require them. Unknown values remain null. Video informs observed shape and damage; it must not populate the reference dimension fields. Do not infer, estimate, or prefill dimensions from pixels, familiar objects, or model guesses.

Read back user-supplied measurements and resolve ambiguous units, contradictions, or missing values through the existing chat/controls. Preserve explicit confirmation before generation. Once required dimensions and reference shape are confirmed, proceed automatically through the reconstruction job. Devin may reconstruct the damage boundary from video within the supplied metric reference; it must never invent or change the physical scale or supplied reference dimensions. This rule applies to the new video workflow; retain the existing photo workflow separately.

## 2. Build the complete reference first

Build the intact reference with trusted, fixed CadQuery templates for the supported primitives, using only validated typed parameters. Reuse the existing ring template. No model-generated code executes on our server.

Export `reference_full.stl` and, where supported, STEP. Validate the reference before starting Devin. Create a machine-readable specification containing units (mm), dimensions, shape/cavity semantics, coordinate frame, provenance, and reference revision/hash. STL does not encode units, so the sidecar is required. The reference geometry and scale remain fixed throughout Devin retries.

## 3. Integrate Devin as an actual remote worker

Read the user's existing [FIMI — cadrage demo et prompt Devin](</home/valentin/Second_brain/vault/2_Projet/Hackbarna_2026/FIMI - cadrage demo et prompt Devin.md>). Use its initial-session and same-session correction prompts as the basis of versioned runtime prompts. The source was read for this handoff. This newer request makes the complete reference mandatory before Devin starts, replacing the source prompt's optional full-object reconstruction; it also sets the retry limit to 100. Keep the source note unchanged.

Preserve its repair conventions: missing material only, without added assembly clearance, offsets, or connectors; independently supplied user measurements; no invented hidden features; reproducible generation script; and `summary.json` with `candidate_ready` or `needs_input`. `candidate_ready` means ready for our validator, never final acceptance. Devin must not modify the validator, thresholds, or reference, and must not build a UI, repository, or PR.

Read `DEVIN_API_KEY` only from the server environment or gitignored `.env`. A credential was supplied separately by the user; do not copy it into this note, code, prompts, tests, browser payloads, logs, or evidence. Do not print existing secret values.

Verify the API version supported by that credential. Upload the original video, complete reference STL, and specification using documented attachment handling. Start a session with the runtime task prompt and all attachments. File upload support alone does not establish native video understanding: prove Devin can access and decode the clip, extracting frames in its sandbox when necessary. A local path, thumbnail, or text summary is not a substitute for delivering the video.

Devin must analyze the observed surviving geometry, align it to the fixed reference, and reconstruct the missing material. Conceptually: `missing = intact reference − observed surviving material`, with explicitly reported uncertainty. It may choose tools and write/run reconstruction code only in its own sandbox. Do not substitute the current largest-angular-gap ring shortcut for the requested Devin path.

Require `repair_part.stl` (the missing piece), its reproducible generation script with parameters/dependencies/run instructions, `summary.json`, an aligned surviving-geometry estimate or other checkable representation, and reconstruction evidence/limitations. Preserve the source summary fields: status, units, supplied_dimensions, observed_geometry, assumptions, coordinate_frame, candidate_dimensions_mm, missing_inputs, changes_from_previous, and artifacts; unavailable artifact entries are null. Store returned scripts for reproducibility but never execute them on our server. Deliver artifacts in the reference's mm coordinate frame, or supply an explicit rigid transform into it. Alignment may rotate and translate, never rescale. Hidden or ambiguous damage must be reported; an unresolved reconstruction is not a successful result.

## 4. Independent validation and autonomous correction

Use a background job with session ID, reference revision, attempt number, status, and artifact records. Do not hold a single HTTP request open for the whole Devin run. Poll with backoff, handle provider errors, and prevent duplicate paid sessions on repeated clicks or ambiguous network retries. Invalidate stale results when the video or confirmed specification changes; late results must not overwrite a newer revision.

Download and validate artifacts locally without executing returned scripts. Verify readable finite geometry, nonzero volume, closed mesh, expected units/alignment, containment within the reference, and that the result is not simply the entire reference object. Check overlap with surviving material and coverage of the missing region using documented tolerances. Ground alignment/damage checks in sampled video evidence where feasible. A surviving mesh generated by Devin is useful evidence, not independent ground truth. Separate mesh validity, reference consistency, and visual reconstruction confidence. Adapt validators to each primitive; the ring's analytic volume check is not universal. Never claim physical fit from these checks.

On failure, automatically send the unchanged validator report, including check names, measured errors, units, tolerances, alignment information, and relevant evidence, back to the same Devin session using the source note's correction-message format. Fetch the corrected artifacts and validate again. Keep the reference immutable.

Set `DEVIN_MAX_RETRIES=100`: one initial reconstruction plus at most 100 automatic correction retries (101 candidate attempts maximum). A retry is one correction cycle, not a status poll or HTTP transport retry. Persist counters across restarts. Stop on the first accepted candidate; never run all 100 unnecessarily. Report exhaustion explicitly after the final failed candidate. Handle requests for genuinely missing evidence through the existing Nebius chat without burning correction retries while waiting. Make wall-time/provider-cost limits configurable and visible in the run record; if one stops a run before the retry limit, report that exact cause instead of success or retry exhaustion. Do not silently replace the user's 100-retry setting with a smaller cap.

### Complete run logging

Persist a chronological structured event log for every job outside git, alongside immutable per-attempt artifacts and validator reports. Log uploads and metadata/hashes, extracted-frame timestamps, user messages and supplied measurements, confirmations, selected models, exact rendered runtime prompts, redacted provider request/response bodies, provider/session/request IDs, status transitions, polling and transport errors, latencies, available usage/cost data, candidate hashes/paths, validation measurements and thresholds, correction messages, retry counters, input changes, and terminal reasons. Correlate every event with job ID, reference revision, session ID where available, and attempt/retry index. Record unavailable usage as null, never an invented value.

“Log everything” means all observable application/provider events and returned content. Redact credentials, authorization headers, and signed URL tokens before writing; reference binary media by local path/hash instead of duplicating base64 into logs. Keep original inputs, candidate STLs, scripts, summaries, and validation evidence locally outside git, and preserve run history across a process restart. Provide a local run manifest for inspection without introducing a new UI. Do not claim access to private provider reasoning or internal activity that the API does not expose.

Show the complete reference and missing piece distinctly using the existing viewer. Expose clearly labeled downloads only for current validated artifacts. Keep LIVE/MOCK/REPLAY labels honest; never silently fall back after a live failure.

## Acceptance and delivery

1. Existing UI remains visually unchanged apart from necessary video support and status/content labels; verify it in the browser.
2. A real clip plus “Create the missing part of this ring” makes Nebius ask the user for required dimensions, read back and confirm the supplied values, and produce the intact reference before any Devin reconstruction. Verify no reference dimension is populated from video inference.
3. A real Devin session receives the original video and exact reference artifact; its resulting missing-part STL is retrieved and independently checked.
4. A deliberately invalid test artifact exercises the full feedback/retry path. Label injected failures as tests; do not present them as a naturally occurring live Devin failure.
5. Cover missing user measurements, ambiguous/hollow objects, unreadable media, provider failure, missing artifacts, retry exhaustion, duplicate requests, and stale results with focused tests. Verify the 100-retry boundary (101 total candidates), early success, persisted counters, complete event/artifact logs, and secret redaction using offline provider doubles; do not spend 100 live retries just to test counting. Cover all three reference templates and preserve the existing photo path.
6. Run `uv run pytest -q`, `cd web && npm run build`, and `scripts/smoke.sh`; extend smoke coverage for the new path. Separate offline tests from billable live checks and report unavailable credentials/budget as an explicit live-validation blocker.

Deliver code, setup variables without secrets, the selected Nebius model ID(s), the Devin prompt source/path, validation criteria and tolerances, and exact verification results. Distinguish implemented, tested live, and still blocked. No fabricated traces or physical-fit claims.

## API references to recheck during implementation

- [Devin attachment upload](https://docs.devin.ai/api-reference/v1/attachments/upload-files-for-devin-to-work-with): legacy v1 supports personal/service API keys and uses one `ATTACHMENT:"{file_url}"` line per uploaded file in the prompt. Do not mix v1 authentication and payloads with a different API version.
- [Devin session creation](https://docs.devin.ai/api-reference/v1/sessions/create-a-new-devin-session): verify current request fields and session limits against the chosen API version.
- [Nebius model offering](https://nebius.com/services/token-factory) and [vision offering](https://nebius.com/solutions/vision): confirm exact account availability and modalities through the live API instead of treating a marketing name as a callable model ID.
