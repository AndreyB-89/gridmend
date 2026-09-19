"""Nebius Token Factory JSON chat helper (OpenAI-compatible). Raises ProviderError on failure."""
from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from api.schemas import Trace
from engine.providers.common import ProviderError, map_openai_error, nebius_client, timed

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


def chat_json(messages: list[dict[str, Any]], schema: type[M], model: str) -> tuple[M, Trace]:
    """Ask for a JSON object, validate it with `schema`. One retry on invalid JSON, then ProviderError."""
    client = nebius_client()
    total_ms = 0.0
    request_id: str | None = None
    last_problem = ""
    for attempt in range(2):
        with timed() as t:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=600,
                )
            except ProviderError:
                raise
            except Exception as exc:  # openai errors, mapped without secrets
                raise map_openai_error(exc) from None
        total_ms += t.latency_ms
        request_id = getattr(resp, "id", None) or request_id
        try:
            content = resp.choices[0].message.content or ""
            parsed = schema.model_validate(json.loads(_strip_fences(content)))
        except (json.JSONDecodeError, ValidationError, IndexError, AttributeError, TypeError) as exc:
            last_problem = type(exc).__name__
            log.warning("Nebius returned invalid JSON (attempt %d): %s", attempt + 1, last_problem)
            continue
        trace = Trace(provider="NEBIUS", model=model, mode="LIVE", latency_ms=round(total_ms, 1), request_id=request_id)
        return parsed, trace
    raise ProviderError("PROVIDER_FAILED", f"Nebius returned invalid JSON twice ({last_problem}).")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def list_models() -> list[str]:
    try:
        return sorted(m.id for m in nebius_client().models.list())
    except Exception as exc:
        raise map_openai_error(exc) from None
