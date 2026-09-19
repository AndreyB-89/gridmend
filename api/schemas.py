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
