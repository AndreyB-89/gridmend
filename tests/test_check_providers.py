"""Pure helpers of scripts/check_providers.py. No network."""
import io
import wave

from scripts.check_providers import model_check, silent_wav

MODELS = ["Qwen/Qwen2.5-VL-72B-Instruct", "Qwen/Qwen3-32B", "meta-llama/Llama-3.3-70B-Instruct"]


def test_model_found():
    ok, reason = model_check("Qwen/Qwen3-32B", MODELS)
    assert ok and "found" in reason


def test_model_missing_shows_close_matches():
    ok, reason = model_check("qwen/qwen2.5-vl-72b-instruct", MODELS)
    assert not ok and "Qwen/Qwen2.5-VL-72B-Instruct" in reason


def test_model_missing_no_match():
    ok, reason = model_check("zzz", MODELS)
    assert not ok and "not in /v1/models" in reason


def test_silent_wav_is_1s_16k_mono():
    with wave.open(io.BytesIO(silent_wav()), "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1 and w.getnframes() == 16000
