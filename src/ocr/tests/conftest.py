"""Shared pytest fixtures for ``src/ocr/`` tests.

Provides two things the Gemini unit tests need:

1. A small **real** Pillow page image written to disk — the adapter opens a
   ``Path``, so a real file exercises the same I/O production hits.
2. A **fake** ``google.generativeai`` SDK (plus the ``google.api_core``
   exception types) injected into ``sys.modules``. Per the testing standard we
   mock only the external network API; the fake lets us drive every adapter
   code path — success, refusal, retry, exhaustion — without a key or a network
   call, and without requiring the real SDK to be installed.
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
