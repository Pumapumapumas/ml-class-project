"""Gemini OCR adapter.

Wraps Google's ``google-generativeai`` SDK to run Telugu OCR with **Gemini 1.5
Flash** (the free-tier model — not Pro, whose free quota is tighter). Conforms
to the :class:`~src.ocr.base.OCRAdapter` contract: input is an image
``Path``, output is NFC-normalized Unicode text, and empty/refused responses
come back as ``OCRResult(text="", ...)`` rather than raising.

The adapter owns three responsibilities the caller must not duplicate:

1. **NFC normalization** of the model's output (the contract; see
   :mod:`src.ocr.base`).
2. **Exponential-backoff retry** on transient rate-limit / unavailable errors,
   so a batch run survives the free tier's 15-requests-per-minute cap.
3. **Refusal detection** — Gemini occasionally returns a short English
   apology ("I cannot read this image") instead of text. That is not OCR
   output; the adapter logs it at WARNING and returns an empty string so the
   refusal never pollutes the corpus.

The ``google-generativeai`` SDK is imported lazily inside the constructor so
that importing this module (and the ``src.ocr`` package) does not require the
SDK to be installed — unit tests fake it, and code paths that never construct a
:class:`GeminiAdapter` never need it.
"""

from __future__ import annotations

import logging
import os
import random
import time
import unicodedata
from pathlib import Path

from PIL import Image

from src.ocr.base import OCRResult

LOG = logging.getLogger(__name__)

# Free-tier vision model. NOT gemini-2.5-pro — its free quota is tighter
# (see docs/development/phase_3_ocr_pipeline.md open question 1).
# Was gemini-1.5-flash; that model was retired by Google during this project
# (404 NOT_FOUND on first live call). gemini-2.5-flash is the documented
# successor with the same free-tier limits (15 RPM / 1500 RPD).
MODEL_NAME = "gemini-2.5-flash"

# Drawn verbatim from the project spec. Kept as a module constant so a future
# prompt-variant study (a Phase 3 stretch goal) can A/B it without touching the
# adapter logic.
SYSTEM_PROMPT = """\
You are a Telugu OCR system. Extract all Telugu text from the provided image and return ONLY the Unicode text content. Rules:
- Output Telugu characters as Unicode (UTF-8 NFC).
- Do NOT translate to English. Do NOT transliterate.
- Do NOT add any commentary, headers, footers, or markdown.
- Preserve paragraph breaks with newlines.
- If a portion of the page is illegible, output what you can read and skip the rest silently.
- If the page is empty or contains no text, return an empty string."""

# Retry budget for transient (rate-limit / unavailable) errors. Seven total
# attempts; backoff before attempt N is 2**N + jitter seconds (~2, 4, 8, 16,
# 32, 64s across the six gaps = ~126 s total). The Gemini free tier's
# rate-limit cool-down is sometimes longer than a single 1-minute window —
# tighter budgets (e.g. 5 attempts / ~30 s) caused 12-of-30 batch failures
# during the parallel matrix run on 2026-06-24. Seven attempts gives enough
# headroom that single-cell runs reliably finish within free-tier limits.
MAX_ATTEMPTS = 7

# Telugu Unicode block (U+0C00 to U+0C7F). Used by the refusal heuristic.
TELUGU_BLOCK_START = 0x0C00
TELUGU_BLOCK_END = 0x0C7F

# A response with no Telugu codepoints AND shorter than this is treated as a
# refusal/metadata line, not OCR output. The threshold comes from the project
# spec; it is a deliberate heuristic, not a tuned value. Known limitation: a
# short *legitimate* response containing no Telugu — e.g. a page whose only
# content is a numeral ("1924") or a Latin-script header — is also treated as a
# refusal and dropped. That is an accepted trade-off for a Telugu-only corpus;
# such pages are rare and an empty result is safer than a refusal string leaking
# into the OCR output. Revisit if the corpus turns out to contain such pages.
REFUSAL_MAX_CHARS = 30


def _backoff_delay(attempt: int) -> float:
    """Seconds to wait before retrying, for a 1-based ``attempt`` number.

    Exponential backoff with jitter: ``2**attempt`` seconds plus a random
    fraction of a second to decorrelate concurrent retriers. Pulled out as a
    module-level function so tests can monkeypatch it to keep retries fast.

    Args:
        attempt: The 1-based attempt that just failed (the next attempt is
            ``attempt + 1``).

    Returns:
        Delay in seconds before the next attempt.
    """
    return float(2**attempt) + random.uniform(0.0, 1.0)


def _has_telugu(text: str) -> bool:
    """Return ``True`` if ``text`` contains at least one Telugu codepoint."""
    return any(TELUGU_BLOCK_START <= ord(ch) <= TELUGU_BLOCK_END for ch in text)


def _looks_like_refusal(text: str) -> bool:
    """Heuristically detect a model refusal masquerading as OCR output.

    A refusal is a short response with no Telugu in it — e.g. "I cannot read
    this image." A genuinely empty response (empty/whitespace string) is *not* a
    refusal; the caller handles that separately so the two cases log at
    different levels.

    Args:
        text: The model's (already NFC-normalized) output.

    Returns:
        ``True`` if the text is non-empty, under :data:`REFUSAL_MAX_CHARS`
        characters, and contains no Telugu codepoints.
    """
    stripped = text.strip()
    return bool(stripped) and len(stripped) < REFUSAL_MAX_CHARS and not _has_telugu(stripped)


class GeminiAdapter:
    """OCR adapter backed by Gemini 1.5 Flash via ``google-generativeai``.

    Reads the API key from the ``GEMINI_API_KEY`` environment variable at
    construction and fails fast if it is missing. Satisfies the
    :class:`~src.ocr.base.OCRAdapter` protocol.

    Attributes:
        model_name: The Gemini model identifier in use (default
            :data:`MODEL_NAME`).
    """

    model_name: str = MODEL_NAME

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        """Configure the SDK and build the underlying model client.

        Args:
            model_name: Gemini model identifier. Defaults to the free-tier
                :data:`MODEL_NAME`.

        Raises:
            RuntimeError: If ``GEMINI_API_KEY`` is not set in the environment.
                The key is never read from a literal or defaulted to a
                placeholder (see
                ``docs/standards/credential_handling_standard.md``).
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your "
                "key (see docs/standards/credential_handling_standard.md)."
            )

        # Lazy import: keeps `import src.ocr` working without the SDK installed
        # (unit tests fake it; only real API calls need the real package).
        import google.generativeai as genai
        from google.api_core import exceptions as google_exceptions

        genai.configure(api_key=api_key)
        self.model_name = model_name
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
        )
        # Transient errors worth retrying. Anything else propagates immediately.
        self._retryable: tuple[type[Exception], ...] = (
            google_exceptions.ResourceExhausted,
            google_exceptions.ServiceUnavailable,
        )
        self._max_attempts = MAX_ATTEMPTS

    def ocr(self, image_path: Path) -> OCRResult:
        """Run Gemini OCR on a single page image.

        Args:
            image_path: Path to a readable page image.

        Returns:
            An :class:`OCRResult` carrying NFC-normalized Unicode text. Empty
            string when the page is blank or the model refused.

        Raises:
            FileNotFoundError: If ``image_path`` does not exist.
            OSError: If the image exists but cannot be decoded (corrupt or
                truncated). ``PIL.UnidentifiedImageError`` is a subclass of
                ``OSError`` and surfaces here too. The batch runner records
                this as a per-page failure and continues.
            google.api_core.exceptions.ResourceExhausted: If the rate limit is
                still hit after :data:`MAX_ATTEMPTS` attempts.
            google.api_core.exceptions.ServiceUnavailable: If the service is
                still unavailable after :data:`MAX_ATTEMPTS` attempts.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"image does not exist: {image_path}")

        start = time.monotonic()
        raw_text = self._generate_with_retry(image_path)
        latency_ms = (time.monotonic() - start) * 1000.0

        normalized = unicodedata.normalize("NFC", raw_text)

        if _looks_like_refusal(normalized):
            LOG.warning(
                "Gemini returned a likely refusal for %s; treating as empty. preview=%r",
                image_path.name,
                normalized[:50],
            )
            return OCRResult(
                text="",
                model_name=self.model_name,
                latency_ms=latency_ms,
                raw_response={"refusal": True, "raw_text": normalized},
            )

        if not normalized.strip():
            LOG.debug("Gemini returned empty text for %s.", image_path.name)
            return OCRResult(
                text="",
                model_name=self.model_name,
                latency_ms=latency_ms,
                raw_response={"empty": True},
            )

        LOG.debug(
            "Gemini OCR ok for %s: %d chars, %.0f ms.",
            image_path.name,
            len(normalized),
            latency_ms,
        )
        return OCRResult(
            text=normalized,
            model_name=self.model_name,
            latency_ms=latency_ms,
            raw_response={"char_count": len(normalized)},
        )

    def _generate_with_retry(self, image_path: Path) -> str:
        """Call the model, retrying transient errors with exponential backoff.

        Args:
            image_path: Path to the image to OCR.

        Returns:
            The model's raw (not yet normalized) text, or ``""`` if the response
            carried no extractable text.

        Raises:
            google.api_core.exceptions.ResourceExhausted: After the retry budget
                is exhausted.
            google.api_core.exceptions.ServiceUnavailable: After the retry
                budget is exhausted.
        """
        # Decode the image once; reuse it across retries.
        with Image.open(image_path) as handle:
            handle.load()
            image = handle.copy()

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._model.generate_content([image])
                return self._extract_text(response, image_path)
            except self._retryable as exc:
                if attempt == self._max_attempts:
                    LOG.warning(
                        "Gemini still failing after %d attempts for %s (%s); giving up.",
                        attempt,
                        image_path.name,
                        type(exc).__name__,
                    )
                    raise
                delay = _backoff_delay(attempt)
                LOG.warning(
                    "Gemini transient error on attempt %d/%d for %s (%s); retrying in %.1fs.",
                    attempt,
                    self._max_attempts,
                    image_path.name,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)

        # Unreachable: the loop either returns or raises on the final attempt.
        raise AssertionError("retry loop exited without returning or raising")

    @staticmethod
    def _extract_text(response: object, image_path: Path) -> str:
        """Pull the text out of a model response, tolerating a blocked response.

        The SDK's ``response.text`` accessor raises ``ValueError`` when the
        candidate was blocked (e.g. by a safety filter) and carries no text. We
        treat that as an empty page rather than a hard failure, matching the
        adapter's "empty is data, not an error" contract.

        Args:
            response: The object returned by ``GenerativeModel.generate_content``.
            image_path: The source image, for log context.

        Returns:
            The response text, or ``""`` if none could be extracted.
        """
        try:
            text = response.text
        except ValueError as exc:
            LOG.warning(
                "Gemini response for %s had no extractable text (possibly blocked): %s",
                image_path.name,
                exc,
            )
            return ""
        return text or ""
