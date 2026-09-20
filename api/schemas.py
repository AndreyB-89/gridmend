"""Pydantic mirror of contracts/types.ts (v3). Keep both files identical in meaning."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Point = tuple[float, float]
Mode = Literal["LIVE", "REPLAY", "MOCK"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Dimension(Strict):
    value_mm: Optional[float]
    source: Optional[Literal["PHOTO", "SPOKEN_MEASUREMENT", "MANUAL_MEASUREMENT"]]
    confirmed: bool

    @classmethod
    def unknown(cls) -> "Dimension":
        return cls(value_mm=None, source=None, confirmed=False)


class Calibration(Strict):
    card_size_mm: Optional[tuple[float, float]]
    size_confirmed: bool
    corners_px: Optional[tuple[Point, Point, Point, Point]]
    same_plane_confirmed: bool


class InspectContext(Strict):
    top_calibration: Calibration
    side_calibration: Optional[Calibration]
    top_roi_px: Optional[tuple[float, float, float, float]]
    outer_edge_points_px: list[Point]
    inner_edge_points_px: list[Point]
    reviewed_voice_text: str = Field(max_length=2000)
    operator_note: str = Field(max_length=1000)


class Trace(Strict):
    provider: Literal["NEBIUS", "SLNG", "LOCAL"]
    model: str
    mode: Mode
    latency_ms: float
    request_id: Optional[str]


class RingFit(Strict):
    outer_diameter_mm: float
    inner_diameter_mm: float
    concentric_offset_mm: float
    rms_residual_mm: float
    surviving_arc_deg: tuple[float, float]
    missing_arc_deg: tuple[float, float]
    support_deg: float


class InspectResult(Strict):
    status: Literal["NEEDS_INPUT", "REVIEW", "UNSUPPORTED"]
    observations: list[str]
    question: Optional[str]
    outer_diameter: Dimension
    inner_diameter: Dimension
    thickness: Dimension
    fit: Optional[RingFit]
    top_overlay_url: Optional[str]
    warnings: list[str]
    trace: Trace


class VoiceResult(Strict):
    transcript: str
    trace: Trace


class Groove(Strict):
    depth_mm: float
    width_mm: float


class GenerateRequest(Strict):
    outer_diameter: Dimension
    inner_diameter: Dimension
    thickness: Dimension
    groove: Optional[Groove]
    profile_rz_mm: Optional[list[Point]]
    profile_basis: Literal["OBSERVED", "SIMPLIFIED_RECTANGLE"]
    profile_confirmed: bool
    missing_arc_deg: Optional[tuple[float, float]]
    purpose: Literal["DEMO_CAD_ONLY"]


ProfileFeature = Literal["INNER_GROOVE", "OUTER_BULGE", "THICKNESS", "OUTER_DIAMETER", "INNER_DIAMETER"]


class ProfileEditRequest(Strict):
    accepted: GenerateRequest
    reviewed_voice_text: str = Field(max_length=2000)


class ProfileEditResult(Strict):
    feature: Optional[ProfileFeature]
    candidate: Optional[GenerateRequest]
    readback: str
    question: Optional[str]
    limitations: list[str]
    trace: Trace


class CadCheck(Strict):
    name: Literal["SOLID", "DIMENSIONS", "PROFILE", "STEP_REIMPORT", "STL_MESH"]
    passed: bool
    detail: str


class GenerateResult(Strict):
    status: Literal["READY"]
    design_id: str
    step_url: str
    stl_url: str
    missing_segment_stl_url: Optional[str]
    summary_url: str
    checks: list[CadCheck]
    limitations: list[str]
    physical_fit_verified: Literal[False]


class ApiError(Strict):
    error: Literal["INVALID_INPUT", "NEEDS_INPUT", "PROVIDER_FAILED", "TIMEOUT", "CAD_FAILED"]
    message: str

# Video workflow v1. Separate from photo-derived proposals.
VideoFamily = Literal['ring', 'cylinder', 'box']
VideoFeature = Literal['outer_diameter', 'inner_diameter', 'diameter', 'height', 'length', 'width', 'wall_thickness', 'cavity_depth', 'groove_depth', 'groove_width']


class SuppliedMeasurement(Strict):
    value_mm: Optional[float] = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    original_value: Optional[float] = None
    original_unit: Optional[str] = None
    source_text: Optional[str] = None
    message_id: Optional[str] = None
    confirmed: bool = False


class ReferenceSpec(Strict):
    family: Optional[VideoFamily] = None
    cavity: Optional[Literal['solid', 'through', 'blind']] = None
    profile: Optional[Literal['plain', 'inner_groove']] = None
    dimensions: dict[VideoFeature, SuppliedMeasurement] = Field(default_factory=dict)
    units: Literal['mm'] = 'mm'
    confirmed: bool = False


class VideoTurn(Strict):
    revision: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')


class VideoConfirm(Strict):
    revision: int = Field(ge=1)


class VideoArtifact(Strict):
    name: str
    sha256: str
    url: str


class VideoState(Strict):
    job_id: str
    revision: int
    status: str
    mode: Mode
    user_goal: str
    spec: ReferenceSpec
    observations: list[dict]
    questions: list[str]
    messages: list[dict]
    session_id: Optional[str]
    attempt: int
    retries: int
    max_retries: int
    limits: dict
    reference: list[VideoArtifact]
    result: list[VideoArtifact]
    validation: Optional[dict]
    terminal_reason: Optional[str]
    selected_models: dict
