"""Shared helpers for provider adapters (Nebius, SLNG). No FastAPI imports here."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

from dotenv import load_dotenv

load_dotenv()

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
TIMEOUT_S = 30.0


class ProviderError(Exception):
    """A LIVE provider call failed. The route maps this to ApiError 502/504."""

    def __init__(self, code: Literal["PROVIDER_FAILED", "TIMEOUT"], message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Timer:
    latency_ms: float = 0.0


@contextmanager
def timed() -> Iterator[Timer]:
    """Measure wall time. `with timed() as t: ...` then read `t.latency_ms`."""
    t = Timer()
    start = time.perf_counter()
    try:
        yield t
    finally:
        t.latency_ms = round((time.perf_counter() - start) * 1000.0, 1)


def env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def nebius_key() -> str | None:
    return env("NEBIUS_API_KEY")


def nebius_vision_model() -> str:
    return env("NEBIUS_MODEL") or "Qwen/Qwen2.5-VL-72B-Instruct"


def nebius_text_model() -> str:
    return env("NEBIUS_TEXT_MODEL") or nebius_vision_model()


def nebius_client():
    """OpenAI SDK client pointed at Nebius Token Factory. Only call when a key exists."""
    from openai import OpenAI

    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=nebius_key(), timeout=TIMEOUT_S, max_retries=0)


def map_openai_error(exc: Exception) -> ProviderError:
    """Turn an openai SDK exception into a ProviderError without echoing secrets."""
    import openai

    if isinstance(exc, openai.APITimeoutError):
        return ProviderError("TIMEOUT", "Nebius did not answer in time.")
    if isinstance(exc, openai.APIStatusError):
        return ProviderError("PROVIDER_FAILED", f"Nebius returned HTTP {exc.status_code}.")
    if isinstance(exc, openai.APIConnectionError):
        return ProviderError("PROVIDER_FAILED", "Could not connect to Nebius.")
    return ProviderError("PROVIDER_FAILED", f"Nebius call failed ({type(exc).__name__}).")
