"""GridMend API: one process, local files, no database.

Run: uv run uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from api.schemas import (
    ApiError,
    Dimension,
    GenerateRequest,
    GenerateResult,
    InspectContext,
    InspectResult,
    ProfileEditRequest,
    ProfileEditResult,
    VoiceResult,
)

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = (ROOT / os.getenv("ARTIFACT_ROOT", "artifacts")).resolve()
ARTIFACTS.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD = 10 * 1024 * 1024
CAD_TIMEOUT_S = 30
PROVIDER_TIMEOUT_S = 45

app = FastAPI(title="GridMend", version="0.3")


class HttpError(Exception):
    def __init__(self, status: int, error: str, message: str):
        self.status, self.error, self.message = status, error, message


def fail(status: int, error: str, message: str) -> HttpError:
    return HttpError(status, error, message)


@app.exception_handler(HttpError)
async def _http_error(_, exc: HttpError):
    return JSONResponse(status_code=exc.status, content=ApiError(error=exc.error, message=exc.message).model_dump())


@app.exception_handler(RequestValidationError)
async def _validation_error(_, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []))
    return JSONResponse(
        status_code=422,
        content=ApiError(error="INVALID_INPUT", message=f"Invalid input at {where}: {first.get('msg', 'bad value')}").model_dump(),
    )


def provider_error(exc: Exception) -> HttpError:
    code = getattr(exc, "code", "PROVIDER_FAILED")
    status = 504 if code == "TIMEOUT" else 502
    return fail(status, code if code in ("TIMEOUT", "PROVIDER_FAILED") else "PROVIDER_FAILED", str(exc) or "Provider failed.")


async def read_upload(upload: UploadFile, what: str) -> bytes:
    data = await upload.read()
    if not data:
        raise fail(422, "INVALID_INPUT", f"The {what} is empty.")
    if len(data) > MAX_UPLOAD:
        raise fail(422, "INVALID_INPUT", f"The {what} is larger than 10 MB.")
    return data


def new_id() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]


def file_url(path: Path) -> str:
    return f"/api/files/{path.name}"


# ---------------------------------------------------------------- health


@app.get("/api/health")
def health():
    return {
        "status": "OK",
        "modes": {
            "nebius": "LIVE" if os.getenv("NEBIUS_API_KEY") else "MOCK",
            "slng": "LIVE" if os.getenv("SLNG_API_KEY") else "MOCK",
        },
    }


@app.get("/api/demo-clicks")
def demo_clicks():
    path = ROOT / "fixtures" / "demo-clicks.json"
    if not path.exists():
        raise fail(404, "INVALID_INPUT", "No demo clicks fixture on this machine.")
    data = json.loads(path.read_text())
    if (ROOT / data.get("image", "")).is_file():
        data["image_url"] = "/api/demo-photo"
    return data


@app.get("/api/demo-photo")
def demo_photo():
    path = ROOT / "fixtures" / "demo-clicks.json"
    image = (ROOT / json.loads(path.read_text())["image"]).resolve() if path.exists() else None
    if image is None or not image.is_file() or (ROOT / "sample-photos") not in image.parents:
        raise fail(404, "INVALID_INPUT", "Demo photo is not on this machine.")
    return FileResponse(image)


# ---------------------------------------------------------------- inspect


@app.post("/api/inspect", response_model=InspectResult)
async def inspect(top_image: UploadFile = File(...), context: str = Form(...), side_image: UploadFile | None = File(None)):
    import cv2

    from engine.fit import FitError, decode_image, fit_ring
    from engine.interpret import interpret

    try:
        ctx = InspectContext.model_validate_json(context)
    except ValidationError as exc:
        raise fail(422, "INVALID_INPUT", f"Invalid context: {exc.errors()[0]['msg']}")

    data = await read_upload(top_image, "photo")
    try:
        image = decode_image(data)
    except FitError as exc:
        raise fail(422, "INVALID_INPUT", str(exc))

    warnings: list[str] = []
    question: str | None = None
    fit = None
    overlay_url = None
    cal = ctx.top_calibration

    if cal.card_size_mm is None:
        question = "What is the size of the card? Enter its width and height in millimetres."
    elif cal.corners_px is None:
        question = "Click the four corners of the card."
    else:
        if not cal.size_confirmed:
            warnings.append("Card size is not measured yet. All millimetre values depend on it.")
        try:
            out = fit_ring(image, list(cal.corners_px), cal.card_size_mm, ctx.outer_edge_points_px, ctx.inner_edge_points_px)
            fit = out.fit
            warnings.extend(out.warnings)
            overlay = ARTIFACTS / f"overlay-{new_id()}.png"
            overlay.write_bytes(out.overlay_png)
            overlay_url = file_url(overlay)
        except FitError as exc:
            question = str(exc)

    # Smaller JPEG for the vision model; the fit already used full resolution.
    scale = 1280 / max(image.shape[:2])
    small = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1 else image
    ok, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])
    try:
        observations, llm_question, trace = await asyncio.wait_for(
            asyncio.to_thread(interpret, jpeg.tobytes() if ok else None, ctx, fit), PROVIDER_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        raise fail(504, "TIMEOUT", "The vision model did not answer in time. Please retry.")
    except Exception as exc:  # ProviderError and friends
        raise provider_error(exc)

    def photo_dim(value):
        # 1 decimal: same number as the observation text, no false precision.
        return Dimension(value_mm=round(value, 1), source="PHOTO", confirmed=False)

    return InspectResult(
        status="REVIEW" if fit else "NEEDS_INPUT",
        observations=observations,
        question=question or llm_question,
        outer_diameter=photo_dim(fit.outer_diameter_mm) if fit else Dimension.unknown(),
        inner_diameter=photo_dim(fit.inner_diameter_mm) if fit else Dimension.unknown(),
        thickness=Dimension.unknown(),
        fit=fit,
        top_overlay_url=overlay_url,
        warnings=warnings,
        trace=trace,
    )


@app.post("/api/auto-detect")
async def auto_detect_route(top_image: UploadFile = File(...)):
    """Proposes card corners and ring edge points. The operator checks and corrects them."""
    from dataclasses import asdict

    from engine.fit import FitError, auto_detect, decode_image

    data = await read_upload(top_image, "photo")
    try:
        image = decode_image(data)
    except FitError as exc:
        raise fail(422, "INVALID_INPUT", str(exc))
    return asdict(await asyncio.to_thread(auto_detect, image))


# ---------------------------------------------------------------- voice


@app.post("/api/voice", response_model=VoiceResult)
async def voice(audio: UploadFile = File(...)):
    from engine.providers.slng import transcribe

    data = await read_upload(audio, "recording")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(transcribe, data, audio.content_type or "audio/webm", audio.filename or "voice.webm"),
            PROVIDER_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise fail(504, "TIMEOUT", "Speech-to-text did not answer in time. Please retry.")
    except Exception as exc:
        raise provider_error(exc)


# ---------------------------------------------------------------- profile edit


@app.post("/api/profile-edit", response_model=ProfileEditResult)
async def profile_edit(req: ProfileEditRequest):
    from engine.profile_edit import propose

    if not req.reviewed_voice_text.strip():
        raise fail(422, "INVALID_INPUT", "The answer is empty.")
    try:
        result = await asyncio.wait_for(asyncio.to_thread(propose, req), PROVIDER_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise fail(504, "TIMEOUT", "The language model did not answer in time. Please retry.")
    except Exception as exc:
        raise provider_error(exc)
    # Belt and braces: a proposal is never confirmed.
    if result.candidate is not None and (
        result.candidate.profile_confirmed
        or any(
            getattr(result.candidate, d).confirmed and getattr(result.candidate, d) != getattr(req.accepted, d)
            for d in ("outer_diameter", "inner_diameter", "thickness")
        )
    ):
        raise fail(502, "PROVIDER_FAILED", "Internal rule broken: a proposal came back confirmed.")
    return result


# ---------------------------------------------------------------- generate


@app.post("/api/generate", response_model=GenerateResult)
async def generate(req: GenerateRequest):
    from cad.ring import CadError, NeedsInput, generate_ring, validate_request

    try:
        validate_request(req)
    except NeedsInput as exc:
        raise fail(422, "NEEDS_INPUT", str(exc))
    except CadError as exc:
        raise fail(422, "INVALID_INPUT", str(exc))

    design_id = "ring-" + new_id()
    try:
        out = await asyncio.wait_for(asyncio.to_thread(generate_ring, req, ARTIFACTS, design_id), CAD_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise fail(500, "CAD_FAILED", "CAD generation took longer than 30 seconds.")
    except CadError as exc:
        raise fail(500, "CAD_FAILED", str(exc))

    summary = ARTIFACTS / f"{design_id}-summary.json"
    summary.write_text(
        json.dumps(
            {
                "design_id": design_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "request": req.model_dump(),
                "checks": [c.model_dump() for c in out.checks],
                "limitations": out.limitations,
                "physical_fit_verified": False,
                "purpose": "DEMO_CAD_ONLY",
            },
            indent=2,
        )
    )
    return GenerateResult(
        status="READY",
        design_id=design_id,
        step_url=file_url(out.step_path),
        stl_url=file_url(out.stl_path),
        missing_segment_stl_url=file_url(out.missing_stl_path) if out.missing_stl_path else None,
        summary_url=file_url(summary),
        checks=out.checks,
        limitations=out.limitations,
        physical_fit_verified=False,
    )


# ---------------------------------------------------------------- files

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


@app.get("/api/files/{name}")
def files(name: str):
    if not SAFE_NAME.match(name) or name.startswith("."):
        raise fail(404, "INVALID_INPUT", "Unknown file.")
    path = (ARTIFACTS / name).resolve()
    if path.parent != ARTIFACTS or not path.is_file():
        raise fail(404, "INVALID_INPUT", "Unknown file.")
    return FileResponse(path, filename=name)


# ---------------------------------------------------------------- web app

WEB_DIST = ROOT / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
