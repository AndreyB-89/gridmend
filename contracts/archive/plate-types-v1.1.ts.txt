// GridMend wire contract v1.1. Source: docs/project-plan.md
export type Id = string;
export type Sha256 = string;
export type UTC = string;
export interface VoiceNote {
  id: Id;
  image_ids: Id[];                    // 1–3 registered images for this observation
  audio_sha256: Sha256;
  audio_url: string;                  // authenticated stored audio download
  content_type: string;              // validated against pinned STT model support
  duration_ms: number;               // >0 and <=30,000
  provenance: "REAL_AUTHORIZED" | "STAGED_RECORDING";
  provider_upload_allowed: true;
  language_requested: "en";
  raw_transcript: string;             // immutable SLNG output
  reviewed_transcript: string | null;
  reviewed_by: "ANDRII" | "VALENTIN" | "MORTAZA" | null;
  reviewed_at: UTC | null;
  revision: number;
  provider: "SLNG";
  model_id: string;
  provider_request_id: string | null;
  latency_ms: number;                // server send to final provider response
  mode: "LIVE";                      // fresh real API call; recording may be staged
  created_at: UTC;
}
export interface VoiceReviewRequest {
  expected_revision: number;
  reviewed_transcript: string;       // <=2,000 characters; operator may correct STT
  reviewed_by: "ANDRII" | "VALENTIN" | "MORTAZA";
}
export type Mode = "LIVE" | "REPLAY" | "MOCK";
export type Provenance = "REAL_AUTHORIZED" | "STAGED_PHOTO" | "SYNTHETIC" | "NEWS_REFERENCE";
export type Family = "ACCESSORY_PLATE" | "CABLE_GUIDE" | "HV_INSULATOR" | "OTHER";
export type Recognition = "CANDIDATE" | "UNKNOWN" | "OUT_OF_SCOPE";
export type MatchStrength = "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type DamageTag = "BROKEN" | "DEFORMED" | "APPARENT_MELTING" |
  "DISCOLORATION" | "MISSING_REGION" | "NO_VISIBLE_DAMAGE" | "UNCERTAIN";
export type ParameterKey = "width_mm" | "height_mm" | "thickness_mm" |
  "hole_diameter_mm" | "hole_pitch_x_mm" | "hole_pitch_y_mm";
export type EvidenceSource = "REFERENCE_DRAWING" | "MANUAL_MEASUREMENT";
export type Process = "CNC_MILL_METAL" | "SHEET_CUT_METAL" | "AM_POLYMER" |
  "CNC_POLYMER" | "CNC_WOOD" | "SPECIALIST";
export type MaterialFamily = "METAL" | "POLYMER" | "ELECTRICAL_LAMINATE" |
  "TRANSFORMER_WOOD" | "WORKSHOP_WOOD" | "UNKNOWN";
export type Purpose = "ENGINEERING_REVIEW" | "FIT_CHECK_ONLY";
export type AssessmentStatus = "NEEDS_CONFIRMATION" | "NEEDS_INPUT" |
  "READY_FOR_CAD" | "BLOCKED";
export type Blocker = "IDENTITY_UNCONFIRMED" | "UNKNOWN_COMPONENT" | "OUT_OF_SCOPE" |
  "NO_TEMPLATE" | "MISSING_DIMENSION" | "UNCONFIRMED_DIMENSION" |
  "INVALID_GEOMETRY" | "MATERIAL_CONFLICT" | "MATERIAL_UNVERIFIED" |
  "PROVENANCE_RESTRICTED" | "UPSTREAM_UNAVAILABLE";

export interface MaterialSpec {
  family: MaterialFamily;
  grade: string | null;               // e.g. demo drawing says "Aluminium 6061-T6"
  evidence_id: Id | null;              // registered reference, not a guessed property
  basis: "DEMO_DRAWING" | "UNVERIFIED";
}
export interface ParameterSpec {
  key: ParameterKey;
  nominal_mm: number | null;
  tolerance_mm: number | null;
  evidence_id: Id | null;
}
export interface ReferenceRecord {
  id: Id;
  title: string;
  revision: string;
  sha256: Sha256;
  url: string;
  provenance: "TEAM_DEMO_DRAWING" | "AUTHORIZED_DRAWING";
  approved_for_service: false;
}
export interface RouteOption {
  id: Id;
  process: Process;
  material_family: MaterialFamily;
  permitted_purposes: Purpose[];
  screening: "DRAFT_CANDIDATE" | "SPECIALIST_ONLY";
  rationale: string;
  required_checks: string[];
}
export interface ComponentRecord {
  id: Id;
  name: string;
  family: Family;
  scene_node_ids: string[];           // stable names in the bundled schematic
  catalog_revision: string;
  evidence_level: "DEMO_FIXTURE" | "DRAFT_SCREENING";
  template_id: "RECT_PLATE_4H_V1" | null;
  reference_id: Id | null;
  compatible_reference_ids: Id[];     // operator selects one; never merge references
  parameters: ParameterSpec[];
  intended_material: MaterialSpec;
  routes: RouteOption[];
  generation_supported: boolean;
  service_release: "NOT_APPROVED";
}
export interface CatalogResponse {
  api_version: "1.1";
  revision: string;
  components: ComponentRecord[];
  references: ReferenceRecord[];
}

export interface ImageRecord {
  id: Id;
  sha256: Sha256;
  content_type: "image/jpeg" | "image/png" | "image/webp";
  width_px: number;
  height_px: number;
  bytes: number;
  provenance: Provenance;
  provider_upload_allowed: boolean;
  preview_url: string;
  created_at: UTC;
}
export interface AssessmentRequest {
  api_version: "1.1";
  image_ids: Id[];                     // 1–3 images, all registered
  voice_note_id: Id | null;            // null supports the photo-only baseline/fallback
  voice_note_revision: number | null;  // exact reviewed revision; null iff no voice note
  catalog_revision: string;
  reference_id: Id | null;
  incident_reported: "FIRE" | "IMPACT" | "BOTH" | "UNKNOWN";
  user_note: string;                  // <= 1,000 characters; data, never instructions
  execution_mode: Mode;
  replay_run_id: Id | null;           // required for REPLAY, null otherwise
}
export interface ImageBox {
  image_id: Id;
  x: number; y: number; width: number; height: number;
  // Normalized [0,1], top-left origin; x+width<=1, y+height<=1.
}
export interface Prediction {
  recognition: Recognition;
  component_id: Id | null;            // must exist in the requested catalog
  family: Family | null;
  match_strength: MatchStrength;      // qualitative; never called calibrated probability
  damage_tags: DamageTag[];
  observations: string[];
  unknowns: string[];
  region: ImageBox | null;            // approximate display hint, not measurement
}
export interface InferenceTrace {
  run_id: Id;
  mode: Mode;
  provider: "NEBIUS" | null;
  model_id: string | null;
  provider_request_id: string | null;
  prompt_version: string;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  recorded_run_id: Id | null;
}
export interface Measurement {
  key: ParameterKey;
  value_mm: number | null;
  tolerance_mm: number | null;
  source: EvidenceSource | null;
  evidence_id: Id | null;
  confirmed: boolean;
}
export interface ConfirmationRequest {
  expected_revision: number;
  component_id: Id | null;
  reference_id: Id | null;
  measurements: Measurement[];        // exactly one entry for each of the six keys
  route_id: Id | null;
  proposed_material: MaterialSpec;
  purpose: Purpose;
  confirmed_by: "ANDRII" | "VALENTIN" | "MORTAZA";
  correction_note: string | null;     // required if changing predicted identity
}
export interface Confirmation extends ConfirmationRequest {
  confirmed_at: UTC;                  // server timestamp
}
export interface Decision {
  status: AssessmentStatus;
  blocker_codes: Blocker[];
  questions: string[];
  selected_component_id: Id | null;
  selected_route_id: Id | null;
  generation_allowed: boolean;
  purpose: Purpose;
  service_release: "NOT_APPROVED";
}
export interface Assessment {
  api_version: "1.1";
  id: Id;
  revision: number;
  created_at: UTC;
  updated_at: UTC;
  request: AssessmentRequest;
  prediction: Prediction;
  inference: InferenceTrace;
  voice_note: VoiceNote | null;        // immutable reviewed snapshot used for this run
  confirmation: Confirmation | null;
  decision: Decision;
}

export interface DesignRequest {
  assessment_id: Id;
  expected_assessment_revision: number;
}
export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
export type CheckName = "SOLID_VALID" | "SINGLE_SOLID" | "DIMENSIONS" |
  "HOLE_GEOMETRY" | "VOLUME" | "STEP_REIMPORT" |
  "MESH_CLOSED" | "MATERIAL_ROUTE";
export interface GeometryCheck {
  name: CheckName;
  passed: boolean;
  measured: number | null;
  expected: number | null;
  limit: number | null;
  unit: "mm" | "mm3" | "count" | null;
  detail: string;
}
export interface Artifact {
  id: Id;
  format: "STEP" | "STL" | "JSON" | "DXF";
  sha256: Sha256;
  bytes: number;
  download_url: string;
  purpose: Purpose;
  service_release: "NOT_APPROVED";
}
export interface DesignJob {
  api_version: "1.1";
  id: Id;
  status: JobStatus;
  created_at: UTC;
  completed_at: UTC | null;
  assessment_id: Id;
  assessment_revision: number;
  specification_hash: Sha256;
  template_id: "RECT_PLATE_4H_V1";
  template_revision: string;
  validation_revision: string;
  purpose: Purpose;
  checks: GeometryCheck[];
  artifacts: Artifact[];              // [] unless all required checks pass
  error: ApiError | null;
}
export interface ManufacturingManifest {
  schema_version: "1.1";
  design_id: Id;
  assessment_id: Id;
  assessment_revision: number;
  specification_hash: Sha256;
  component_id: Id;
  catalog_revision: string;
  template_id: "RECT_PLATE_4H_V1";
  template_revision: string;
  reference: ReferenceRecord;
  measurements: Measurement[];
  route: RouteOption;
  proposed_material: MaterialSpec;
  purpose: Purpose;
  input_images: ImageRecord[];
  voice_note: VoiceNote | null;        // same snapshot as assessment; provenance retained
  inference: InferenceTrace;
  geometry_checks: GeometryCheck[];
  geometry_artifacts: Artifact[];      // STEP/STL and optional DXF; excludes manifest itself
  build_commit: string;
  manufactured: false;                // physical specimen evidence is separate
  service_release: "NOT_APPROVED";
}
export type ErrorCode = "INVALID_INPUT" | "UNAUTHORIZED" | "NOT_FOUND" | "INTERNAL_ERROR" |
  "REVISION_CONFLICT" | "IDEMPOTENCY_CONFLICT" | "BLOCKED_ASSESSMENT" |
  "UPSTREAM_TIMEOUT" | "UPSTREAM_FAILURE" | "CAD_VALIDATION_FAILED";
export interface ApiError {
  code: ErrorCode;
  message: string;
  retryable: boolean;
  fields: string[];
}
export interface ErrorResponse { api_version: "1.1"; request_id: Id; error: ApiError; }
export interface HealthResponse {
  api_version: "1.1";
  status: "OK" | "DEGRADED";
  build_commit: string;
  cad_ready: boolean;
  nebius_configured: boolean;          // configuration present, not a live success claim
  catalog_revision: string;
}

// Internal Nebius adapter output: exactly Prediction. No dimensions, route,
// material grade, executable code, approval or download URL is accepted from the model.
// Internal engine interface:
// analyze(request: AssessmentRequest, images: ImageRecord[], catalog: CatalogResponse)
//   -> { prediction: Prediction; inference: InferenceTrace }
// decide(assessment: Assessment, catalog: CatalogResponse) -> Decision
// generate(snapshot: Assessment, catalog: CatalogResponse) -> DesignJob
