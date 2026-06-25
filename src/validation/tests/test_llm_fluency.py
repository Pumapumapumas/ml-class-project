"""Unit tests for ``src.validation.llm_fluency``.

Uses a fake ``anthropic`` SDK injected into ``sys.modules`` so tests do not
hit the real API. Mirrors the fixture pattern in ``src/ocr/tests/conftest.py``.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Fake anthropic SDK (per-test, scoped to this module)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_llm_fluency_imports():
    """Ensure each test re-imports llm_fluency with the current fake anthropic."""
    sys.modules.pop("src.validation.llm_fluency", None)
    yield
    sys.modules.pop("src.validation.llm_fluency", None)


@pytest.fixture
def fake_anthropic(monkeypatch: pytest.MonkeyPatch):
    """Inject a minimal fake anthropic SDK into sys.modules for the test."""
    anthropic_module = types.ModuleType("anthropic")

    class APIStatusError(Exception):
        def __init__(self, message: str = "", *, status_code: int | None = None) -> None:
            super().__init__(message)
            self.status_code = status_code

    class RateLimitError(APIStatusError):
        def __init__(self, message: str = "") -> None:
            super().__init__(message, status_code=429)

    class APIConnectionError(Exception):
        def __init__(self, message: str = "connection failed") -> None:
            super().__init__(message)

    state: dict = {
        "next_response_text": '{"rating": 3, "reason": "ok", "error_examples": []}',
        "call_count": 0,
        "exception_sequence": [],  # list of exceptions to raise on consecutive calls
        "configured_key": None,
        "max_retries": None,
        "models_used": [],
    }

    class _Block:
        def __init__(self, text: str) -> None:
            self.text = text
            self.type = "text"

    class _Response:
        def __init__(self, text: str) -> None:
            self.content = [_Block(text)]

    class Messages:
        def create(self, *, model=None, max_tokens=None, messages=None, **_kw):
            state["call_count"] += 1
            state["models_used"].append(model)
            if state["exception_sequence"]:
                exc = state["exception_sequence"].pop(0)
                if exc is not None:
                    raise exc
            return _Response(state["next_response_text"])

    class Anthropic:
        def __init__(self, api_key=None, max_retries=None, **_kw):
            state["configured_key"] = api_key
            state["max_retries"] = max_retries
            self.messages = Messages()

    anthropic_module.APIStatusError = APIStatusError
    anthropic_module.RateLimitError = RateLimitError
    anthropic_module.APIConnectionError = APIConnectionError
    anthropic_module.Anthropic = Anthropic

    monkeypatch.setitem(sys.modules, "anthropic", anthropic_module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")

    # Speed up retries in tests so they don't burn wall clock time.
    import src.validation.llm_fluency as fluency_mod  # imported AFTER the fake is registered

    monkeypatch.setattr(fluency_mod, "_backoff_delay", lambda attempt: 0.0)

    return state


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_score_returns_structured_result(self, fake_anthropic):
        fake_anthropic["next_response_text"] = json.dumps(
            {
                "rating": 4,
                "reason": "Mostly fluent with a few small slips.",
                "error_examples": ["X for Y", "Z for W"],
            }
        )
        from src.validation.llm_fluency import ClaudeFluencyJudge

        result = ClaudeFluencyJudge().score("some Telugu OCR text")

        assert result.rating == 4
        assert "fluent" in result.reason.lower()
        assert result.error_examples == ["X for Y", "Z for W"]
        assert result.model_name == "claude-sonnet-4-6"
        assert result.latency_ms > 0

    def test_model_override_honored(self, fake_anthropic):
        from src.validation.llm_fluency import ClaudeFluencyJudge

        judge = ClaudeFluencyJudge(model_name="claude-opus-4-8")
        judge.score("text")

        assert fake_anthropic["models_used"][-1] == "claude-opus-4-8"
        assert judge.model_name == "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestParsing:
    def test_strips_markdown_fence_if_present(self, fake_anthropic):
        fake_anthropic["next_response_text"] = (
            "```json\n"
            + json.dumps({"rating": 5, "reason": "fluent", "error_examples": []})
            + "\n```"
        )
        from src.validation.llm_fluency import ClaudeFluencyJudge

        result = ClaudeFluencyJudge().score("text")
        assert result.rating == 5

    def test_missing_rating_raises(self, fake_anthropic):
        fake_anthropic["next_response_text"] = json.dumps(
            {"reason": "no rating field", "error_examples": []}
        )
        from src.validation.llm_fluency import ClaudeFluencyJudge, FluencyJudgeError

        with pytest.raises(FluencyJudgeError, match="missing 'rating'"):
            ClaudeFluencyJudge().score("text")

    def test_out_of_range_rating_raises(self, fake_anthropic):
        fake_anthropic["next_response_text"] = json.dumps(
            {"rating": 7, "reason": "high", "error_examples": []}
        )
        from src.validation.llm_fluency import ClaudeFluencyJudge, FluencyJudgeError

        with pytest.raises(FluencyJudgeError, match="rating.*1-5"):
            ClaudeFluencyJudge().score("text")

    def test_non_integer_rating_raises(self, fake_anthropic):
        fake_anthropic["next_response_text"] = json.dumps(
            {"rating": 3.5, "reason": "half", "error_examples": []}
        )
        from src.validation.llm_fluency import ClaudeFluencyJudge, FluencyJudgeError

        with pytest.raises(FluencyJudgeError, match="rating"):
            ClaudeFluencyJudge().score("text")

    def test_unparseable_json_raises(self, fake_anthropic):
        fake_anthropic["next_response_text"] = "this is not JSON, it is prose"
        from src.validation.llm_fluency import ClaudeFluencyJudge, FluencyJudgeError

        with pytest.raises(FluencyJudgeError, match="not valid JSON"):
            ClaudeFluencyJudge().score("text")

    def test_non_object_json_raises(self, fake_anthropic):
        fake_anthropic["next_response_text"] = json.dumps([1, 2, 3])
        from src.validation.llm_fluency import ClaudeFluencyJudge, FluencyJudgeError

        with pytest.raises(FluencyJudgeError, match="not an object"):
            ClaudeFluencyJudge().score("text")


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


class TestRetry:
    def test_rate_limit_retries_then_succeeds(self, fake_anthropic):
        import anthropic

        fake_anthropic["exception_sequence"] = [
            anthropic.RateLimitError("rate limit hit"),
            anthropic.RateLimitError("still rate limited"),
            None,  # third attempt succeeds
        ]
        from src.validation.llm_fluency import ClaudeFluencyJudge

        result = ClaudeFluencyJudge().score("text")
        assert result.rating == 3  # default response
        # 2 failures + 1 success = 3 calls
        assert fake_anthropic["call_count"] == 3

    def test_4xx_client_error_does_not_retry(self, fake_anthropic):
        import anthropic

        fake_anthropic["exception_sequence"] = [
            anthropic.APIStatusError("bad request", status_code=400),
        ]
        from src.validation.llm_fluency import ClaudeFluencyJudge

        with pytest.raises(anthropic.APIStatusError):
            ClaudeFluencyJudge().score("text")
        # Only 1 call attempted before the 4xx propagated.
        assert fake_anthropic["call_count"] == 1

    def test_5xx_server_error_retries(self, fake_anthropic):
        import anthropic

        fake_anthropic["exception_sequence"] = [
            anthropic.APIStatusError("internal error", status_code=500),
            None,
        ]
        from src.validation.llm_fluency import ClaudeFluencyJudge

        result = ClaudeFluencyJudge().score("text")
        assert result.rating == 3
        assert fake_anthropic["call_count"] == 2

    def test_connection_error_retries(self, fake_anthropic):
        import anthropic

        fake_anthropic["exception_sequence"] = [
            anthropic.APIConnectionError("dns blip"),
            None,
        ]
        from src.validation.llm_fluency import ClaudeFluencyJudge

        result = ClaudeFluencyJudge().score("text")
        assert result.rating == 3
        assert fake_anthropic["call_count"] == 2

    def test_retry_budget_exhaustion_raises(self, fake_anthropic):
        import anthropic

        # Five failures in a row exhausts the 5-attempt budget.
        fake_anthropic["exception_sequence"] = [anthropic.RateLimitError("hit") for _ in range(5)]
        from src.validation.llm_fluency import ClaudeFluencyJudge

        with pytest.raises(anthropic.RateLimitError):
            ClaudeFluencyJudge().score("text")
        assert fake_anthropic["call_count"] == 5


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_missing_api_key_raises_at_construction(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from src.validation.llm_fluency import ClaudeFluencyJudge

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ClaudeFluencyJudge()
