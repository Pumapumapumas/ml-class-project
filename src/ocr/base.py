"""OCR adapter interface and result type.

Defines the single contract every OCR backend in this package satisfies so the
batch runner (``scripts/run_ocr.py``) and the Phase 4 validation code can call
any model with identical code. Concrete adapters live alongside this module:
:class:`~src.ocr.gemini.GeminiAdapter` (this PR), and — implemented elsewhere
against this same contract — the Tesseract baseline (Rauf) and the optional
Surya adapter (deferred stretch; see
``docs/development/phase_3_ocr_pipeline.md``).

The contract:

- **Input is a file** ``Path`` **, not bytes.** Adapters open the image
  themselves. Passing a path (rather than a decoded buffer) keeps callers honest
  about disk I/O and lets each backend choose how to load the image (PIL,
  OpenCV, or shelling out to a binary).
- **Output is NFC-normalized Unicode text.** Each adapter applies
  ``unicodedata.normalize("NFC", ...)`` to the model's raw output *inside the
  adapter*, never in the caller. NFC is the canonical form the rest of the
  pipeline (corpus inventory, CER/WER) assumes.
- **Empty and refused responses are data, not errors.** When a model returns
  nothing usable — an empty page, or a short non-Telugu refusal like "I cannot
  read this image" — the adapter returns ``OCRResult(text="", ...)`` and logs
  it (DEBUG for a genuinely empty response, WARNING for a detected refusal). It
  does **not** raise. The batch runner decides what an empty page means; raising
  here would abort a 4,000-page run on the first blank scan.

Adapters still raise for genuine failures the caller cannot paper over: a
missing image file, a missing API key at construction time, or an upstream
error that survives the retry budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OCRResult:
    """The result of running one OCR adapter on one page image.

    Attributes:
        text: The NFC-normalized Unicode text the model returned. Empty string
            for an empty page or a detected refusal (see the module docstring).
        model_name: Identifier of the model that produced the text, e.g.
            ``"gemini-2.5-flash"``. Mirrors the adapter's ``model_name``.
        latency_ms: Wall-clock time, in milliseconds, from the start of the
            ``ocr`` call to the response — *including* any retry/backoff waits.
        raw_response: Optional provider-specific debug payload. ``None`` when an
            adapter has nothing extra to surface; otherwise a small dict useful
            for diagnosing normalization or refusal issues. Never contains
            secrets.
    """

    text: str
    model_name: str
    latency_ms: float
    raw_response: dict | None = None


@runtime_checkable
class OCRAdapter(Protocol):
    """Structural contract for an OCR backend.

    Any object exposing a ``model_name`` string and an ``ocr`` method with the
    signature below satisfies this protocol — adapters do not need to subclass
    it. ``@runtime_checkable`` lets tests assert conformance with ``isinstance``
    (a structural check on attribute presence, not behaviour), which is how the
    Tesseract adapter author verifies their class against the same contract this
    PR's Gemini adapter is tested against.

    Attributes:
        model_name: Class-level identifier for the backing model, used to label
            output (manifests, logs). Stable across instances of the same
            adapter.
    """

    model_name: str

    def ocr(self, image_path: Path) -> OCRResult:
        """Run OCR on the image at ``image_path``.

        Args:
            image_path: Path to a readable page image.

        Returns:
            An :class:`OCRResult` whose ``text`` is NFC-normalized Unicode
            (empty string for an empty page or detected refusal).
        """
        ...
