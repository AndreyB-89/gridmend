"""SLNG speech-to-text (Deepgram nova-3 English) with LIVE and MOCK modes."""
from __future__ import annotations

import logging

import httpx

from api.schemas import Trace, VoiceResult
from engine.providers.common import TIMEOUT_S, ProviderError, env, timed

log = logging.getLogger(__name__)

STT_URL = "https://us-east.api.slng.ai/v1/stt/slng/deepgram/nova:3-en"
DEFAULT_MODEL = "nova:3-en"
MOCK_TRANSCRIPT = "the thickness is six millimetres"


def transcribe(audio: bytes, content_type: str, filename: str) -> VoiceResult:
    key = env("SLNG_API_KEY")
    if not key:
        return VoiceResult(
            transcript=MOCK_TRANSCRIPT,
            trace=Trace(provider="SLNG", model=DEFAULT_MODEL, mode="MOCK", latency_ms=0.0, request_id=None),
        )

    files = {"audio": (filename or "audio.webm", audio, content_type or "application/octet-stream")}
    data = {"language": "en", "smart_format": "true", "numerals": "true"}
    headers = {"Authorization": f"Bearer {key}"}
    log.info("SLNG STT request: %d bytes, %s", len(audio), content_type)
    with timed() as t:
        try:
            resp = httpx.post(STT_URL, headers=headers, files=files, data=data, timeout=TIMEOUT_S)
        except httpx.TimeoutException:
            raise ProviderError("TIMEOUT", "Speech-to-text did not answer in time.") from None
        except httpx.HTTPError as exc:
            raise ProviderError("PROVIDER_FAILED", f"Could not reach speech-to-text ({type(exc).__name__}).") from None
    if resp.status_code < 200 or resp.status_code >= 300:
        raise ProviderError("PROVIDER_FAILED", f"Speech-to-text returned HTTP {resp.status_code}.")
    try:
        body = resp.json()
        transcript = body["results"]["channels"][0]["alternatives"][0]["transcript"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("PROVIDER_FAILED", "Speech-to-text returned an unexpected response.") from None
    meta = body.get("metadata") or {}
    transcript = transcript.strip()
    if not transcript:
        raise ProviderError("PROVIDER_FAILED", "I heard nothing. Please try again.")
    return VoiceResult(
        transcript=transcript,
        trace=Trace(
            provider="SLNG",
            model=meta["model"] if isinstance(meta.get("model"), str) and meta["model"] else DEFAULT_MODEL,
            mode="LIVE",
            latency_ms=t.latency_ms,
            request_id=meta.get("request_id"),
        ),
    )
