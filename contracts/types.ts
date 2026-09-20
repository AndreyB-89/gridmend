// GridMend ring-demo contract v3 (scope cut, see docs/build-plan.md).
// Every field is required. Unknown values are null; arrays are [] when empty.
// Pydantic mirror lives in api/schemas.py and must stay identical.
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
  side_calibration: Calibration | null; // v3: not used; always null
  top_roi_px: [number, number, number, number] | null; // x,y,width,height
  outer_edge_points_px: Point[]; // v3: operator clicks on the surviving outer edge, >=3
  inner_edge_points_px: Point[]; // v3: operator clicks on the surviving inner edge, >=3
  reviewed_voice_text: string; // <=2,000 chars; operator-confirmed transcription
  operator_note: string; // <=1,000 chars; data, not instructions
}
export interface Trace {
  provider: "NEBIUS" | "SLNG" | "LOCAL";
  model: string;
  mode: Mode;
  latency_ms: number;
  request_id: string | null;
}
export interface RingFit {
  // All values in card-plane millimetres after homography.
  outer_diameter_mm: number;
  inner_diameter_mm: number;
  concentric_offset_mm: number; // distance between fitted outer and inner centres
  rms_residual_mm: number; // circle-fit residual, worst of the two fits
  surviving_arc_deg: [number, number]; // start, end; counter-clockwise; 0 = +x in card plane
  missing_arc_deg: [number, number]; // complement of surviving_arc_deg
  support_deg: number; // angular span covered by clicked points
}
export interface PartShape {
  // The traced outline of any part, in card-plane millimetres (image y, grows down).
  // A ring is one shape among many. No hole means holes_mm is [] and fit is null;
  // the part is still measured and can still be built.
  outline_mm: Point[]; // closed polygon, >=3 points
  holes_mm: Point[][]; // one closed polygon per through hole; [] when there is none
  length_mm: number; // long side of the bounding box
  width_mm: number; // short side
  confidence: "HIGH" | "LOW"; // HIGH does not mean correct: a part not flat on the table reads wrong
}
export interface InspectResult {
  status: "NEEDS_INPUT" | "REVIEW" | "UNSUPPORTED";
  observations: string[];
  question: string | null;
  outer_diameter: Dimension;
  inner_diameter: Dimension;
  thickness: Dimension;
  fit: RingFit | null; // null when calibration or points are insufficient, or the part is not a ring
  shape: PartShape | null; // null when no card or no part was found
  top_overlay_url: string | null; // registered app artifact, not a model-generated URL
  warnings: string[];
  trace: Trace; // Nebius interpretation trace (LOCAL if Nebius not called)
}
export interface VoiceResult {
  transcript: string; // raw result; operator reviews before use
  trace: Trace;
}
export interface Groove {
  depth_mm: number; // radial, from inner wall outward
  width_mm: number; // axial, centred on ring mid-height
}
export interface GenerateRequest {
  // One rule decides the builder: shape present = general part (extrude the traced
  // outline, cut its holes); shape null = ring, which owns groove and missing arc.
  shape: PartShape | null;
  outer_diameter: Dimension;
  inner_diameter: Dimension;
  thickness: Dimension;
  groove: Groove | null; // v3: inner groove; null = plain rectangle profile
  profile_rz_mm: Point[] | null; // Should: closed polygon cross-section radius,z; null in v3 path
  profile_basis: "OBSERVED" | "SIMPLIFIED_RECTANGLE";
  profile_confirmed: boolean;
  missing_arc_deg: [number, number] | null; // from RingFit; null = no missing-segment export
  purpose: "DEMO_CAD_ONLY";
}
export type ProfileFeature =
  | "INNER_GROOVE"
  | "OUTER_BULGE"
  | "THICKNESS"
  | "OUTER_DIAMETER"
  | "INNER_DIAMETER";
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
  stl_url: string; // full restored ring
  missing_segment_stl_url: string | null; // the restored section only, for highlight/print
  summary_url: string; // JSON: GenerateRequest + checks + limitations
  checks: CadCheck[];
  limitations: string[];
  physical_fit_verified: false;
}
export interface ApiError {
  error: "INVALID_INPUT" | "NEEDS_INPUT" | "PROVIDER_FAILED" | "TIMEOUT" | "CAD_FAILED";
  message: string;
}
