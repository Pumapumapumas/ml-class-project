"""Claude OCR adapter.

Wraps Anthropic's ``anthropic`` SDK to run Telugu OCR with **Claude Sonnet 4.6**
(validated on a real Telugu page: ~29 s latency, ~1000 char output, ~$0.018 per
call). Conforms to the :class:`~src.ocr.base.OCRAdapter` contract: input is an
image ``Path``, output is NFC-normalized Unicode text, and empty/refused
responses come back as ``OCRResult(text="", ...)`` rather than raising.

The adapter is a parallel of :mod:`src.ocr.gemini` — the team has already
validated the OCR adapter pattern there. It owns the same three responsibilities
the caller must not duplicate:

1. **NFC normalization** of the model's output (the contract; see
   :mod:`src.ocr.base`).
2. **Exponential-backoff retry** on transient rate-limit / server errors, so a
   batch run survives provider throttling.
3. **Refusal detection** — a short non-Telugu response (e.g. an English
   apology) is not OCR output; the adapter logs it at WARNING and returns an
   empty string so the refusal never pollutes the corpus.

The ``anthropic`` SDK is imported lazily inside the constructor so that
importing this module (and the ``src.ocr`` package) does not require the SDK to
be installed — unit tests fake it, and code paths that never construct a
:class:`ClaudeAdapter` never need it.
"""

from __future__ import annotations

import base64
import logging
import os
import random
import time
import unicodedata
from pathlib import Path

from src.ocr.base import OCRResult

LOG = logging.getLogger(__name__)

# Default model. Validated by the team on a real Telugu page (29 s latency,
# ~1000 char output, ~$0.018/call). Overridable via the constructor so a
# downstream study can compare Sonnet against e.g. claude-opus-4-8.
MODEL_NAME = "claude-sonnet-4-6"

# Maximum output tokens per call. Sized for our pages: validation runs produced
# ~850 output tokens, so 4096 gives comfortable headroom.
MAX_TOKENS = 4096

# JPEG is the corpus's only image format (see scripts/run_ocr.py IMAGE_EXTENSIONS).
IMAGE_MEDIA_TYPE = "image/jpeg"

# Drawn verbatim from the project spec — identical wording to
# src/ocr/gemini.py's SYSTEM_PROMPT so the two adapters apply the same
# instructions and a prompt-variant study can A/B them without divergence.
SYSTEM_PROMPT = """\
You are a Telugu OCR system. Extract all Telugu text from the provided image and return ONLY the Unicode text content. Rules:
- Output Telugu characters as Unicode (UTF-8 NFC).
- Do NOT translate to English. Do NOT transliterate.
- Do NOT add any commentary, headers, footers, or markdown.
- Preserve paragraph breaks with newlines.
- If a portion of the page is illegible, output what you can read and skip the rest silently.
- If the page is empty or contains no text, return an empty string."""

# Retry budget for transient (rate-limit / server) errors. Five total attempts;
# backoff before attempt N is 2**N + jitter seconds (~2, 4, 8, 16 s across the
# four gaps), then the error propagates.
MAX_ATTEMPTS = 5

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

# HTTP status at or above which an APIStatusError is treated as a transient
# server error worth retrying. Below this (4xx other than 429) is a client error
# that will not improve on retry, so it propagates immediately.
SERVER_ERROR_STATUS = 500


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


class ClaudeAdapter:
    """OCR adapter backed by Claude Sonnet 4.6 via the ``anthropic`` SDK.

    Reads the API key from the ``ANTHROPIC_API_KEY`` environment variable at
    construction and fails fast if it is missing. Satisfies the
    :class:`~src.ocr.base.OCRAdapter` protocol.

    Attributes:
        model_name: The Claude model identifier in use (default
            :data:`MODEL_NAME`).
    """

    model_name: str = MODEL_NAME

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        """Build the underlying Anthropic client.

        Args:
            model_name: Claude model identifier. Defaults to :data:`MODEL_NAME`.
                Callers may override it (e.g. to compare Sonnet against
                ``claude-opus-4-8`` on a sample of pages).

        Raises:
            RuntimeError: If ``ANTHROPIC_API_KEY`` is not set in the
                environment. The key is never read from a literal or defaulted
                to a placeholder (see
                ``docs/standards/credential_handling_standard.md``).
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your "
                "key (see docs/standards/credential_handling_standard.md)."
            )

        # Lazy import: keeps `import src.ocr` working without the SDK installed
        # (unit tests fake it; only real API calls need the real package).
        import anthropic

        self.model_name = model_name
        # max_retries=0 disables the SDK's own retry loop so this adapter's
        # explicit exponential backoff is the single source of retry behaviour
        # (otherwise a rate-limited call would be retried by both layers and the
        # observed retry count / latency would be unpredictable).
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=0)
        self._rate_limit_error = anthropic.RateLimitError
        self._status_error = anthropic.APIStatusError
        self._max_attempts = MAX_ATTEMPTS

    def ocr(self, image_path: Path) -> OCRResult:
        """Run Claude OCR on a single page image.

        Args:
            image_path: Path to a readable JPEG page image.

        Returns:
            An :class:`OCRResult` carrying NFC-normalized Unicode text. Empty
            string when the page is blank or the model refused.

        Raises:
            FileNotFoundError: If ``image_path`` does not exist.
            anthropic.RateLimitError: If the rate limit is still hit after
                :data:`MAX_ATTEMPTS` attempts.
            anthropic.APIStatusError: If a server error (status >= 500) is still
                returned after :data:`MAX_ATTEMPTS` attempts, or immediately for
                a non-retryable client error (4xx other than 429).
        """
        if not image_path.exists():
            raise FileNotFoundError(f"image does not exist: {image_path}")

        start = time.monotonic()
        raw_text = self._generate_with_retry(image_path)
        latency_ms = (time.monotonic() - start) * 1000.0

        normalized = unicodedata.normalize("NFC", raw_text)

        # raw_response is None on every path below, per the task spec. Unlike the
        # Gemini adapter (which stashes a small debug dict), the Claude adapter
        # surfaces the refusal-vs-empty distinction through the WARNING/DEBUG log
        # lines, not the result object — manifest.jsonl does not read
        # raw_response, so there is no downstream consumer for it here.
        if _looks_like_refusal(normalized):
            LOG.warning(
                "Claude returned a likely refusal for %s; treating as empty. preview=%r",
                image_path.name,
                normalized[:50],
            )
            return OCRResult(
                text="",
                model_name=self.model_name,
                latency_ms=latency_ms,
                raw_response=None,
            )

        if not normalized.strip():
            LOG.debug("Claude returned empty text for %s.", image_path.name)
            return OCRResult(
                text="",
                model_name=self.model_name,
                latency_ms=latency_ms,
                raw_response=None,
            )

        LOG.debug(
            "Claude OCR ok for %s: %d chars, %.0f ms.",
            image_path.name,
            len(normalized),
            latency_ms,
        )
        return OCRResult(
            text=normalized,
            model_name=self.model_name,
            latency_ms=latency_ms,
            raw_response=None,
        )

    def _generate_with_retry(self, image_path: Path) -> str:
        """Call the model, retrying transient errors with exponential backoff.

        Args:
            image_path: Path to the image to OCR.

        Returns:
            The model's raw (not yet normalized) text, or ``""`` if the response
            carried no extractable text block.

        Raises:
            anthropic.RateLimitError: After the retry budget is exhausted.
            anthropic.APIStatusError: After the retry budget is exhausted (for a
                server error), or immediately for a non-retryable client error.
        """
        # Read and encode the image once; reuse it across retries.
        image_b64 = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": IMAGE_MEDIA_TYPE,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": SYSTEM_PROMPT},
                ],
            }
        ]

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.messages.create(
                    model=self.model_name,
                    max_tokens=MAX_TOKENS,
                    messages=messages,
                )
                return self._extract_text(response)
            except self._rate_limit_error as exc:
                # RateLimitError (429) is always transient and worth retrying.
                self._sleep_or_raise(attempt, exc, image_path)
            except self._status_error as exc:
                # Only server errors (>= 500) are transient. RateLimitError is a
                # subclass of APIStatusError, so it is handled above first; any
                # APIStatusError reaching here is a non-429 status. A 4xx will
                # not improve on retry, so propagate it immediately.
                if exc.status_code is None or exc.status_code < SERVER_ERROR_STATUS:
                    raise
                self._sleep_or_raise(attempt, exc, image_path)

        # Unreachable: the loop either returns or raises on the final attempt.
        raise AssertionError("retry loop exited without returning or raising")

    def _sleep_or_raise(self, attempt: int, exc: Exception, image_path: Path) -> None:
        """Back off before the next retry, or re-raise on the final attempt.

        Args:
            attempt: The 1-based attempt that just failed.
            exc: The transient error that was caught.
            image_path: The source image, for log context.

        Raises:
            Exception: Re-raises ``exc`` when the retry budget is exhausted.
        """
        if attempt == self._max_attempts:
            LOG.warning(
                "Claude still failing after %d attempts for %s (%s); giving up.",
                attempt,
                image_path.name,
                type(exc).__name__,
            )
            raise exc
        delay = _backoff_delay(attempt)
        LOG.warning(
            "Claude transient error on attempt %d/%d for %s (%s); retrying in %.1fs.",
            attempt,
            self._max_attempts,
            image_path.name,
            type(exc).__name__,
            delay,
        )
        time.sleep(delay)

    @staticmethod
    def _extract_text(response: object) -> str:
        """Concatenate the text blocks of a Claude message response.

        Claude returns ``response.content`` as a list of content blocks; only
        blocks whose ``type`` is ``"text"`` carry OCR output. Non-text blocks
        (if any) are ignored.

        Args:
            response: The object returned by ``messages.create``.

        Returns:
            The joined text of every text block, or ``""`` if there are none.
        """
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
