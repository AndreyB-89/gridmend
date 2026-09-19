---
name: provider-adapter
description: Add or fix a sponsor API call in GridMend (Nebius Token Factory LLM/vision, SLNG speech-to-text/TTS, Galtea evaluation) with LIVE/MOCK modes, traces, timeouts and no leaked keys.
---

# Provider adapter

Adapters live in `engine/providers/` (one file per provider). Routes call adapters; adapters never import FastAPI.

## Pattern (every provider)

- Read the key from the environment (`.env` via `python-dotenv`). No key → mode `MOCK`, returning a fixed response that matches the contract. A MOCK response is always visible in the UI.
- Key present → mode `LIVE`. On error or timeout, raise, and the route returns `ApiError` with 502 (`PROVIDER_FAILED`) or 504 (`TIMEOUT`). **Never fall back to MOCK silently.**
- Timeout 30 s. Use `httpx` for plain HTTP.
- Return a `Trace`: `provider`, `model`, `mode`, `latency_ms` (measured around the call), `request_id` (from the provider response if there is one).
- Log without secrets and without full audio/image bytes.
- Write one unit test with the MOCK path, and one test for "LIVE call fails → error, not mock" (monkeypatch the HTTP call).

## Nebius Token Factory (LLM + vision)

- OpenAI-compatible. Base URL `https://api.tokenfactory.nebius.com/v1/`, key `NEBIUS_API_KEY`, model `NEBIUS_MODEL`.
- Use the `openai` Python SDK with `base_url`. Images go in as `image_url` with a base64 `data:` URL.
- Pick a **vision-capable** model from the team's model list (`GET /v1/models`) and pin it in `.env`. Don't copy the text-only quickstart model.
- Ask for JSON only (`response_format={"type": "json_object"}` if the model supports it). Parse it into Pydantic. On invalid JSON: one retry, then an error.
- The model **proposes**: observations, the next question, and a candidate edit. It never sets `confirmed=true`, never gives pixel measurements, and never returns code. Put transcript and operator notes in the prompt as clearly marked **data**, not instructions.
- Spoken-number rule (case T4): if the text has doubt ("maybe", "or", "I haven't measured", "about"), `candidate=null` and ask a question.

## SLNG speech-to-text

- `POST https://us-east.api.slng.ai/v1/stt/slng/deepgram/nova:3-en` (other regions: us-west, au, in).
- Header `Authorization: Bearer $SLNG_API_KEY`. Body `multipart/form-data`: `audio` = file, `language` = `en`. Useful options: `smart_format=true`, `numerals=true`.
- Transcript: `results.channels[0].alternatives[0].transcript`. Request id: `metadata.request_id`.
- The browser records with `MediaRecorder` (usually `audio/webm;codecs=opus`). Test that SLNG accepts it. If not, set `encoding`/`sample_rate`, or convert on the server with ffmpeg.
- An empty transcript is an error ("I heard nothing"), not an empty success.
- Docs: https://docs.slng.ai/llms.txt (TTS: Aura 2 English, optional, a Should).

## Galtea

- Only after the MOCK/LIVE Nebius path works. Wrap the same function the route uses (e.g. `engine.profile_edit.propose(...)`), not a copy of it.
- Docs: https://docs.galtea.ai/quickstart. Keys: `GALTEA_API_KEY`, `GALTEA_PRODUCT_ID`.
- Scope tonight: case T4 (spoken-number trap) and its variants. Run the baseline **before** fixing anything. Save the results with the `save-evidence` skill.
