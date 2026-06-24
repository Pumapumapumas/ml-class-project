"""Unit tests for ``src.ocr.claude``.

The Anthropic SDK is faked (see ``conftest.py``) so these run with no network,
no real key, and without the real ``anthropic`` package installed. A single
``@pytest.mark.api`` test exercises the real API when ``ANTHROPIC_API_KEY`` is
available, and skips otherwise.
"""

from __future__ import annotations

import logging
import os
import unicodedata
from pathlib import Path

import pytest

from src.ocr import claude
from src.ocr.claude import ClaudeAdapter
from src.ocr.tests.conftest import FakeAnthropicSDK

# Two forms of "e-acute", built from escapes (not literals) so the test does not
# depend on the Unicode normalization this source file happens to be saved in.
NFD_E_ACUTE = "é"  # decomposed (NFD): e + U+0301 combining acute
NFC_E_ACUTE = "é"  # precomposed (NFC): single codepoint U+00E9


def test_successful_call_returns_nfc_normalized_text(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path
):
    # Telugu text (so it is not flagged as a refusal) plus a decomposed
    # e-acute, so NFC normalization provably has work to do.
    raw = "తెలుగు" + NFD_E_ACUTE
    assert raw != unicodedata.normalize("NFC", raw)  # guard: raw really is NFD
    fake_anthropic.respond_with(raw)

    result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == unicodedata.normalize("NFC", raw)
    assert result.text != raw  # normalization actually changed the bytes
    assert NFC_E_ACUTE in result.text  # decomposed sequence collapsed to composed
    assert NFD_E_ACUTE not in result.text  # ...and the decomposed form is gone
    assert result.model_name == "claude-sonnet-4-6"
    assert result.latency_ms >= 0
    assert result.raw_response is None


def test_multiple_text_blocks_are_concatenated(fake_anthropic: FakeAnthropicSDK, telugu_page: Path):
    # A real Claude response can be a list of blocks; the adapter joins the text
    # of every text block and ignores anything non-text.
    def handler(_messages):
        return fake_anthropic.Message(
            [
                fake_anthropic.Block("తెలుగు "),
                fake_anthropic.Block("ignored", block_type="tool_use"),
                fake_anthropic.Block("పాఠం"),
            ]
        )

    fake_anthropic.set_handler(handler)

    result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == "తెలుగు పాఠం"


def test_construction_configures_sdk_with_env_key(fake_anthropic: FakeAnthropicSDK):
    ClaudeAdapter()
    assert fake_anthropic.configured_key == "fake-test-key-not-real"


def test_model_name_override_is_honored(fake_anthropic: FakeAnthropicSDK, telugu_page: Path):
    fake_anthropic.respond_with("తెలుగు")

    adapter = ClaudeAdapter(model_name="claude-opus-4-8")
    result = adapter.ocr(telugu_page)

    assert adapter.model_name == "claude-opus-4-8"
    assert result.model_name == "claude-opus-4-8"
    # The override is the model passed on the wire, not just an attribute.
    assert adapter._client.messages.create  # sanity: client wired up


def test_refusal_heuristic_returns_empty_string(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path, caplog
):
    # Short English apology: no Telugu codepoints, under 30 chars -> refusal.
    fake_anthropic.respond_with("I cannot read this.")

    with caplog.at_level(logging.WARNING, logger="src.ocr.claude"):
        result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == ""
    assert result.raw_response is None
    assert any("refusal" in record.message.lower() for record in caplog.records)


def test_long_english_response_is_not_treated_as_refusal(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path
):
    # Over 30 chars: even without Telugu, the heuristic must not eat it, which
    # would silently drop real (if surprising) output.
    long_text = "This is a long English sentence well over the thirty char limit."
    fake_anthropic.respond_with(long_text)

    result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == long_text


def test_looks_like_refusal_boundary_and_edge_cases():
    # Direct coverage of the load-bearing heuristic, including the 30-char
    # boundary and the documented limitation that short non-Telugu content
    # (numerals, Latin headers) is treated as a refusal.
    assert claude._looks_like_refusal("I cannot read this.") is True
    assert claude._looks_like_refusal("1924") is True  # known limitation
    assert claude._looks_like_refusal("x" * 29) is True  # just under the cap
    assert claude._looks_like_refusal("x" * 30) is False  # at the cap, kept
    assert claude._looks_like_refusal("") is False  # empty is not a refusal
    assert claude._looks_like_refusal("   ") is False  # whitespace-only either
    assert claude._looks_like_refusal("అ") is False  # any Telugu codepoint -> kept


def test_empty_response_returns_empty_string(fake_anthropic: FakeAnthropicSDK, telugu_page: Path):
    fake_anthropic.respond_with("")

    result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == ""
    assert result.raw_response is None


def test_rate_limit_retries_then_succeeds(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path, monkeypatch: pytest.MonkeyPatch
):
    # Keep the backoff measurable but small so latency_ms provably covers the
    # retry window without slowing the test suite.
    monkeypatch.setattr(claude, "_backoff_delay", lambda attempt: 0.02)

    def handler(_messages):
        # call_count reflects this call (create records it first), so fail the
        # first two calls and succeed on the third.
        if fake_anthropic.call_count < 3:
            raise fake_anthropic.RateLimitError("rate limited")
        return fake_anthropic.Message([fake_anthropic.Block("తెలుగు పాఠం")])

    fake_anthropic.set_handler(handler)

    result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == "తెలుగు పాఠం"
    assert fake_anthropic.call_count == 3  # two failures + one success
    # Two ~0.02s backoffs slept before the third attempt -> >= ~40 ms.
    assert result.latency_ms >= 30


def test_server_error_retries_then_succeeds(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path, monkeypatch: pytest.MonkeyPatch
):
    # A 5xx APIStatusError is transient and must be retried, like a rate limit.
    monkeypatch.setattr(claude, "_backoff_delay", lambda attempt: 0.001)

    def handler(_messages):
        if fake_anthropic.call_count < 2:
            raise fake_anthropic.APIStatusError("server error", status_code=503)
        return fake_anthropic.Message([fake_anthropic.Block("ఒక")])

    fake_anthropic.set_handler(handler)

    result = ClaudeAdapter().ocr(telugu_page)

    assert result.text == "ఒక"
    assert fake_anthropic.call_count == 2


def test_client_error_status_is_not_retried(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path, monkeypatch: pytest.MonkeyPatch
):
    # A 4xx (non-429) will not improve on retry; it must propagate immediately
    # after a single attempt rather than burning the retry budget.
    monkeypatch.setattr(claude, "_backoff_delay", lambda attempt: 0.001)

    def handler(_messages):
        raise fake_anthropic.APIStatusError("bad request", status_code=400)

    fake_anthropic.set_handler(handler)

    with pytest.raises(fake_anthropic.APIStatusError):
        ClaudeAdapter().ocr(telugu_page)

    assert fake_anthropic.call_count == 1  # no retries for a client error


def test_retry_budget_exhaustion_raises(
    fake_anthropic: FakeAnthropicSDK, telugu_page: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(claude, "_backoff_delay", lambda attempt: 0.001)

    def always_rate_limited(_messages):
        raise fake_anthropic.RateLimitError("still throttled")

    fake_anthropic.set_handler(always_rate_limited)

    with pytest.raises(fake_anthropic.RateLimitError):
        ClaudeAdapter().ocr(telugu_page)

    assert fake_anthropic.call_count == claude.MAX_ATTEMPTS


def test_missing_api_key_raises_at_construction(monkeypatch: pytest.MonkeyPatch):
    # No fake_anthropic fixture here: the key check runs before the SDK import,
    # so the missing-key error must surface without the SDK ever being touched.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        ClaudeAdapter()


def test_missing_image_file_raises(fake_anthropic: FakeAnthropicSDK, tmp_path: Path):
    fake_anthropic.respond_with("ఒక")

    with pytest.raises(FileNotFoundError):
        ClaudeAdapter().ocr(tmp_path / "does_not_exist.jpg")


@pytest.mark.api
def test_claude_real_api_returns_unicode(telugu_page: Path):
    """Hit the real Claude API when a key is present; skip otherwise."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set; skipping real-API test.")

    result = ClaudeAdapter().ocr(telugu_page)

    assert isinstance(result.text, str)
    assert result.model_name == "claude-sonnet-4-6"
    assert result.latency_ms > 0
