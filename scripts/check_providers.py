"""Check provider keys and models before a LIVE demo. Never prints keys.

Run: uv run python scripts/check_providers.py   (exit 1 if any check FAILs)
"""
from __future__ import annotations

import difflib
import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402

from engine.providers.common import TIMEOUT_S, ProviderError, env, nebius_key, nebius_text_model, nebius_vision_model  # noqa: E402

failed = False


def line(status: str, name: str, reason: str = "") -> None:
    global failed
    failed |= status == "FAIL"
    print(f"{status} {name}: {reason}".rstrip(": "))


def model_check(name: str, models: list[str]) -> tuple[bool, str]:
    """Is `name` in the model list? If not, say which names are close."""
    if name in models:
        return True, f"{name} found"
    lower = {m.lower(): m for m in models}
    close = difflib.get_close_matches(name.lower(), list(lower), n=3, cutoff=0.5)
    close += [m.lower() for m in models if name.lower() in m.lower() and m.lower() not in close]
    hint = f"; close: {', '.join(lower[c] for c in close[:3])}" if close else ""
    return False, f"{name} not in /v1/models{hint}"


def silent_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class _Ping(BaseModel):
    ok: bool


def check_nebius() -> None:
    if not nebius_key():
        line("SKIP", "Nebius", "MOCK (no key)")
        return
    from engine.providers import nebius

    try:
        models = nebius.list_models()
    except ProviderError as exc:
        line("FAIL", "Nebius list_models", exc.message)
        return
    line("PASS", "Nebius list_models", f"{len(models)} models")
    targets = [("NEBIUS_MODEL (vision)", nebius_vision_model()), ("NEBIUS_TEXT_MODEL (text)", nebius_text_model())]
    for label, name in targets:
        ok, reason = model_check(name, models)
        line("PASS" if ok else "FAIL", label, reason)
    for name in dict.fromkeys(n for _, n in targets):  # JSON mode on each distinct model
        msgs = [{"role": "user", "content": 'Reply with this JSON object only: {"ok": true}'}]
        try:
            out, trace = nebius.chat_json(msgs, _Ping, name)
            line("PASS" if out.ok else "FAIL", f"Nebius chat_json {name}", f"{trace.latency_ms} ms")
        except ProviderError as exc:
            line("FAIL", f"Nebius chat_json {name}", exc.message)


def check_slng() -> None:
    key = env("SLNG_API_KEY")
    if not key:
        line("SKIP", "SLNG", "MOCK (no key)")
        return
    import httpx

    from engine.providers import slng

    files = {"audio": ("check.wav", silent_wav(), "audio/wav")}
    data = dict(slng.STT_FORM)  # same as slng.transcribe
    try:
        resp = httpx.post(slng.STT_URL, headers={"Authorization": f"Bearer {key}"}, files=files, data=data, timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        line("FAIL", "SLNG STT", f"request failed ({type(exc).__name__})")
        return
    ok = 200 <= resp.status_code < 300
    line("PASS" if ok else "FAIL", "SLNG STT", f"HTTP {resp.status_code} (silent 1 s WAV; empty transcript is OK)")


if __name__ == "__main__":
    check_nebius()
    check_slng()
    sys.exit(1 if failed else 0)
