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
