"""Shared pytest fixtures for ``src/ocr/`` tests.

Provides what the adapter unit tests need:

1. A small **real** Pillow page image written to disk (``telugu_page``) — the
   adapters open a ``Path``, so a real file exercises the same I/O production
   hits.
2. A **fake** ``google.generativeai`` SDK (``fake_gemini``) plus a **fake**
   ``anthropic`` SDK (``fake_anthropic``), each injected into ``sys.modules``.
   Per the testing standard we mock only the external network API; the fakes let
   us drive every adapter code path — success, refusal, retry, exhaustion —
   without a key or a network call, and without requiring the real SDKs to be
   installed.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def telugu_page(tmp_path: Path) -> Path:
    """A tiny real JPG page with a few dark bars standing in for text.

    The content is irrelevant to the unit tests (the SDK is faked), but using a
    real, openable image means the adapter's ``Image.open(...).load()`` path is
    genuinely exercised rather than mocked.
    """
    path = tmp_path / "page_0001.jpg"
    page = Image.new("RGB", (200, 280), color=(255, 255, 255))
    draw = ImageDraw.Draw(page)
    for y in range(40, 240, 30):
        draw.rectangle([20, y, 180, y + 10], fill=(0, 0, 0))
    page.save(path, format="JPEG")
    return path


class _FakeResponse:
    """Stand-in for a ``GenerativeModel.generate_content`` response.

    Either yields ``text`` or, if ``blocked`` is set, raises ``ValueError`` from
    the ``.text`` accessor — mirroring how the real SDK signals a safety-blocked
    candidate.
    """

    def __init__(self, text: str = "", *, blocked: bool = False) -> None:
        self._text = text
        self._blocked = blocked

    @property
    def text(self) -> str:
        if self._blocked:
            raise ValueError("response has no text (blocked by safety filter)")
        return self._text


@dataclass
class _FakeState:
    """Mutable behaviour shared between the fake module and the test."""

    handler: Callable[[object], _FakeResponse] | None = None
    configured_key: str | None = None
    generate_calls: list[object] = field(default_factory=list)


class FakeGeminiSDK:
    """Controller a test uses to script the faked Gemini SDK.

    Attributes:
        ResourceExhausted: The fake rate-limit exception class (same object the
            adapter will catch, since both resolve it through ``sys.modules``).
        ServiceUnavailable: The fake service-unavailable exception class.
        Response: The response factory (:class:`_FakeResponse`).
    """

    def __init__(self, state: _FakeState, exceptions_module: types.ModuleType) -> None:
        self._state = state
        self.ResourceExhausted = exceptions_module.ResourceExhausted
        self.ServiceUnavailable = exceptions_module.ServiceUnavailable
        self.Response = _FakeResponse

    def set_handler(self, handler: Callable[[object], _FakeResponse]) -> None:
        """Set the function invoked on each ``generate_content`` call.

        The handler receives the content argument and must return a
        :class:`_FakeResponse` or raise (e.g. a rate-limit exception).
        """
        self._state.handler = handler

    def respond_with(self, text: str = "", *, blocked: bool = False) -> None:
        """Convenience: always return a single fixed response."""
        self._state.handler = lambda _content: _FakeResponse(text, blocked=blocked)

    @property
    def configured_key(self) -> str | None:
        """The API key the adapter passed to ``genai.configure``."""
        return self._state.configured_key

    @property
    def call_count(self) -> int:
        """Number of ``generate_content`` calls made so far."""
        return len(self._state.generate_calls)


@pytest.fixture
def fake_gemini(monkeypatch: pytest.MonkeyPatch) -> FakeGeminiSDK:
    """Inject a fake ``google.generativeai`` SDK and yield a controller.

    Also sets a dummy ``GEMINI_API_KEY`` so the adapter constructs cleanly.
    Tests that need the missing-key path delete it via ``monkeypatch.delenv``.
    """
    state = _FakeState()

    # --- fake google.api_core.exceptions ---
    exceptions_module = types.ModuleType("google.api_core.exceptions")

    class ResourceExhausted(Exception):
        """Fake of google.api_core.exceptions.ResourceExhausted."""

    class ServiceUnavailable(Exception):
        """Fake of google.api_core.exceptions.ServiceUnavailable."""

    exceptions_module.ResourceExhausted = ResourceExhausted
    exceptions_module.ServiceUnavailable = ServiceUnavailable

    api_core_module = types.ModuleType("google.api_core")
    api_core_module.exceptions = exceptions_module

    # --- fake google.generativeai ---
    genai_module = types.ModuleType("google.generativeai")

    def configure(api_key: str | None = None, **_kwargs: object) -> None:
        state.configured_key = api_key

    class GenerativeModel:
        def __init__(
            self,
            model_name: str | None = None,
            system_instruction: str | None = None,
            **_kwargs: object,
        ) -> None:
            self.model_name = model_name
            self.system_instruction = system_instruction

        def generate_content(self, content: object, **_kwargs: object) -> _FakeResponse:
            state.generate_calls.append(content)
            if state.handler is None:
                raise AssertionError("test did not set a fake Gemini handler")
            return state.handler(content)

    genai_module.configure = configure
    genai_module.GenerativeModel = GenerativeModel

    # Inject the top-level "google" namespace too, so the fake is self-contained
    # even in an environment where the real google-generativeai package (and its
    # google namespace) is not installed — which is the whole point of faking it.
    google_module = types.ModuleType("google")
    google_module.api_core = api_core_module
    google_module.generativeai = genai_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core_module)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions_module)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai_module)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key-not-real")

    return FakeGeminiSDK(state, exceptions_module)


class _FakeBlock:
    """Stand-in for a single content block on a Claude message response."""

    def __init__(self, text: str, *, block_type: str = "text") -> None:
        self.type = block_type
        self.text = text


class _FakeMessage:
    """Stand-in for the object returned by ``messages.create``.

    Carries a ``content`` list of blocks, mirroring the real SDK's message
    shape that the adapter walks to concatenate text blocks.
    """

    def __init__(self, content: list[_FakeBlock]) -> None:
        self.content = content


@dataclass
class _FakeAnthropicState:
    """Mutable behaviour shared between the fake module and the test."""

    handler: Callable[[object], _FakeMessage] | None = None
    configured_key: str | None = None
    create_calls: list[object] = field(default_factory=list)
    create_models: list[str | None] = field(default_factory=list)


class FakeAnthropicSDK:
    """Controller a test uses to script the faked ``anthropic`` SDK.

    Attributes:
        RateLimitError: The fake rate-limit exception class (the same object the
            adapter catches, since both resolve it through ``sys.modules``).
        APIStatusError: The fake API-status exception class; its ``status_code``
            drives the adapter's "retry only on >= 500" branch.
        Message: The response factory (:class:`_FakeMessage`).
        Block: The content-block factory (:class:`_FakeBlock`).
    """

    def __init__(self, state: _FakeAnthropicState, anthropic_module: types.ModuleType) -> None:
        self._state = state
        self.RateLimitError = anthropic_module.RateLimitError
        self.APIStatusError = anthropic_module.APIStatusError
        self.Message = _FakeMessage
        self.Block = _FakeBlock

    def set_handler(self, handler: Callable[[object], _FakeMessage]) -> None:
        """Set the function invoked on each ``messages.create`` call.

        The handler receives the ``messages`` argument and must return a
        :class:`_FakeMessage` or raise (e.g. a rate-limit exception).
        """
        self._state.handler = handler

    def respond_with(self, text: str = "") -> None:
        """Convenience: always return a single-text-block response."""
        self._state.handler = lambda _messages: _FakeMessage([_FakeBlock(text)])

    @property
    def configured_key(self) -> str | None:
        """The API key the adapter passed to ``anthropic.Anthropic``."""
        return self._state.configured_key

    @property
    def call_count(self) -> int:
        """Number of ``messages.create`` calls made so far."""
        return len(self._state.create_calls)

    @property
    def last_model(self) -> str | None:
        """The ``model`` passed to the most recent ``messages.create`` call."""
        return self._state.create_models[-1] if self._state.create_models else None


@pytest.fixture
def fake_anthropic(monkeypatch: pytest.MonkeyPatch) -> FakeAnthropicSDK:
    """Inject a fake ``anthropic`` SDK and yield a controller.

    Also sets a dummy ``ANTHROPIC_API_KEY`` so the adapter constructs cleanly.
    Tests that need the missing-key path delete it via ``monkeypatch.delenv``.
    """
    state = _FakeAnthropicState()

    anthropic_module = types.ModuleType("anthropic")

    class APIStatusError(Exception):
        """Fake of anthropic.APIStatusError, carrying an HTTP ``status_code``."""

        def __init__(self, message: str = "", *, status_code: int | None = None) -> None:
            super().__init__(message)
            self.status_code = status_code

    class RateLimitError(APIStatusError):
        """Fake of anthropic.RateLimitError (a 429 APIStatusError subclass)."""

        def __init__(self, message: str = "") -> None:
            super().__init__(message, status_code=429)

    class APIConnectionError(Exception):
        """Fake of anthropic.APIConnectionError (network-layer transient)."""

        def __init__(self, message: str = "connection failed") -> None:
            super().__init__(message)

    class Messages:
        def create(
            self,
            *,
            model: str | None = None,
            max_tokens: int | None = None,
            messages: object = None,
            **_kwargs: object,
        ) -> _FakeMessage:
            state.create_calls.append(messages)
            state.create_models.append(model)
            if state.handler is None:
                raise AssertionError("test did not set a fake Anthropic handler")
            return state.handler(messages)

    class Anthropic:
        def __init__(
            self,
            api_key: str | None = None,
            max_retries: int | None = None,
            **_kwargs: object,
        ) -> None:
            state.configured_key = api_key
            self.max_retries = max_retries
            self.messages = Messages()

    anthropic_module.APIStatusError = APIStatusError
    anthropic_module.RateLimitError = RateLimitError
    anthropic_module.APIConnectionError = APIConnectionError
    anthropic_module.Anthropic = Anthropic

    monkeypatch.setitem(sys.modules, "anthropic", anthropic_module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key-not-real")

    return FakeAnthropicSDK(state, anthropic_module)
