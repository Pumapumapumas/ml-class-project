"""Unit tests for ``src.ocr.gemini``.

The Gemini SDK is faked (see ``conftest.py``) so these run with no network, no
real key, and without the real ``google-generativeai`` package installed. A
single ``@pytest.mark.api`` test exercises the real API when ``GEMINI_API_KEY``
is available, and skips otherwise.
"""

from __future__ import annotations

import logging
import os
import unicodedata
from pathlib import Path

import pytest

from src.ocr import gemini
from src.ocr.gemini import GeminiAdapter
from src.ocr.tests.conftest import FakeGeminiSDK


def test_successful_call_returns_nfc_normalized_text(fake_gemini: FakeGeminiSDK, telugu_page: Path):
    # Telugu text (so it is not flagged as a refusal) plus a deliberately
    # decomposed "e + combining acute" so NFC normalization has work to do.
    raw = "తెలుగుé"
    fake_gemini.respond_with(raw)

    result = GeminiAdapter().ocr(telugu_page)

    expected = unicodedata.normalize("NFC", raw)
    assert result.text == expected
    assert result.text != raw  # normalization actually changed the bytes
    assert "é" in result.text  # decomposed sequence collapsed to é
    assert result.model_name == "gemini-1.5-flash"
    assert result.latency_ms >= 0


def test_construction_configures_sdk_with_env_key(fake_gemini: FakeGeminiSDK):
    GeminiAdapter()
    assert fake_gemini.configured_key == "fake-test-key-not-real"


def test_refusal_heuristic_returns_empty_string(
    fake_gemini: FakeGeminiSDK, telugu_page: Path, caplog
):
    # Short English apology: no Telugu codepoints, under 30 chars -> refusal.
    fake_gemini.respond_with("I cannot read this.")

    with caplog.at_level(logging.WARNING, logger="src.ocr.gemini"):
        result = GeminiAdapter().ocr(telugu_page)

    assert result.text == ""
    assert result.raw_response == {"refusal": True, "raw_text": "I cannot read this."}
    assert any("refusal" in record.message.lower() for record in caplog.records)


def test_long_english_response_is_not_treated_as_refusal(
    fake_gemini: FakeGeminiSDK, telugu_page: Path
):
    # Over 30 chars: even without Telugu, the heuristic must not eat it — that
    # would silently drop real (if surprising) output.
    long_text = "This is a long English sentence well over the thirty char limit."
    fake_gemini.respond_with(long_text)

    result = GeminiAdapter().ocr(telugu_page)

    assert result.text == long_text


def test_empty_response_returns_empty_string_at_debug(
    fake_gemini: FakeGeminiSDK, telugu_page: Path
):
    fake_gemini.respond_with("")

    result = GeminiAdapter().ocr(telugu_page)

    assert result.text == ""
    assert result.raw_response == {"empty": True}


def test_blocked_response_is_treated_as_empty(fake_gemini: FakeGeminiSDK, telugu_page: Path):
    # A safety-blocked candidate raises ValueError from `.text`; the adapter
    # treats that as an empty page rather than a hard failure.
    fake_gemini.respond_with("", blocked=True)

    result = GeminiAdapter().ocr(telugu_page)

    assert result.text == ""


def test_rate_limit_retries_then_succeeds(
    fake_gemini: FakeGeminiSDK, telugu_page: Path, monkeypatch: pytest.MonkeyPatch
):
    # Keep the backoff measurable but small so latency_ms provably covers the
    # retry window without slowing the test suite.
    monkeypatch.setattr(gemini, "_backoff_delay", lambda attempt: 0.02)

    calls = {"n": 0}

    def handler(_content):
        calls["n"] += 1
        if calls["n"] < 3:
            raise fake_gemini.ResourceExhausted("rate limited")
        return fake_gemini.Response("తెలుగు పాఠం")

    fake_gemini.set_handler(handler)

    result = GeminiAdapter().ocr(telugu_page)

    assert result.text == "తెలుగు పాఠం"
    assert fake_gemini.call_count == 3  # two failures + one success
    # Two ~0.02s backoffs slept before the third attempt -> >= ~40 ms.
    assert result.latency_ms >= 30


def test_retry_budget_exhaustion_raises(
    fake_gemini: FakeGeminiSDK, telugu_page: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(gemini, "_backoff_delay", lambda attempt: 0.001)

    def always_rate_limited(_content):
        raise fake_gemini.ServiceUnavailable("still down")

    fake_gemini.set_handler(always_rate_limited)

    with pytest.raises(fake_gemini.ServiceUnavailable):
        GeminiAdapter().ocr(telugu_page)

    assert fake_gemini.call_count == gemini.MAX_ATTEMPTS


def test_missing_api_key_raises_at_construction(monkeypatch: pytest.MonkeyPatch):
    # No fake_gemini fixture here: the key check runs before the SDK import, so
    # the missing-key error must surface without the SDK ever being touched.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiAdapter()


def test_missing_image_file_raises(fake_gemini: FakeGeminiSDK, tmp_path: Path):
    fake_gemini.respond_with("ఒక")

    with pytest.raises(FileNotFoundError):
        GeminiAdapter().ocr(tmp_path / "does_not_exist.jpg")


@pytest.mark.api
def test_gemini_real_api_returns_unicode(telugu_page: Path):
    """Hit the real Gemini API when a key is present; skip otherwise."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set; skipping real-API test.")

    result = GeminiAdapter().ocr(telugu_page)

    assert isinstance(result.text, str)
    assert result.model_name == "gemini-1.5-flash"
    assert result.latency_ms > 0
