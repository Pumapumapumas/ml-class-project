"""LLM-based fluency scoring — Phase 4 LLM-validation Method A.

The idea: an OCR output's *fluency* (how plausibly natural it reads as
Telugu prose) is a ground-truth-free proxy for OCR quality. A vision LLM
can judge fluency by reading the OCR text directly. Phase 4 Task 5
calibrates this signal against CER on the eval subset; Phase 5 applies it
at scale where ground truth is unavailable.

Implementation choice — judge model. The Phase 4 plan originally specified
Gemini Flash as the judge. We instead use **Claude Sonnet 4.6** because the
Gemini Flash free-tier quota was saturated by the OCR matrix runs (see
``loose_ends.md`` and the iteration narrative). The judging prompt is
LLM-agnostic; swapping back to Gemini would be a constructor-arg change.
This choice is disclosed in the report's Methodology Disclosure section.

Implementation choice — prompt. The 1-5 rating template comes from the
project spec. The model is asked to respond in a strict JSON object so the
parse is deterministic; if the JSON does not parse, we raise rather than
silently default to a median score (a silent default would confound the
Phase 4 Task 5 calibration with parser noise).

See ``docs/development/phase_4_llm_validation.md`` Task 3.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass

LOG = logging.getLogger(__name__)

# Default judge model. Sonnet 4.6 was validated for vision OCR on a real
# Telugu page (29 s, ~1000 chars, ~$0.018/call); the same client class
# handles text-only judging with no extra setup. Overridable via the
# constructor.
DEFAULT_JUDGE_MODEL = "claude-sonnet-4-6"

# Output-token budget for the judge response. The JSON we ask for is
# small — a rating, a short reason, and up to ~3 error examples; 1024 is
# generous headroom.
MAX_OUTPUT_TOKENS = 1024

# Retry budget for transient errors (rate-limit, server error, network
# layer). Five attempts gives ~30 s of total backoff; the judge calls are
# faster than the OCR vision calls so a tighter budget is fine.
MAX_ATTEMPTS = 5

# Status code at/above which an APIStatusError is treated as transient.
SERVER_ERROR_STATUS = 500

# Drawn from the project spec. Asks for a single JSON object with three
# fields. Keeping it a module constant so a future prompt-variant study
# can A/B it without touching the scoring logic.
FLUENCY_PROMPT_TEMPLATE = """\
You are a Telugu language expert evaluating OCR output quality.
Read the following OCR-extracted text and rate its fluency as natural Telugu prose.

Respond with ONLY a single JSON object on a single line, no markdown fences, no commentary. Use this exact schema:

{{"rating": <integer 1 to 5>, "reason": "<one short sentence>", "error_examples": ["<up to 3 short examples of likely OCR errors>"]}}

Rating scale:
1 = Mostly gibberish; not recognizably Telugu prose.
2 = Many obvious errors; readability poor.
3 = Recognizably Telugu but with frequent errors.
4 = Mostly fluent; occasional small errors.
5 = Fluent; reads as natural Telugu prose.

OCR text to evaluate:
---
{ocr_text}
---

Respond with ONLY the JSON object."""


@dataclass(frozen=True)
class FluencyResult:
    """Structured result of one fluency-scoring call.

    Attributes:
        rating: Integer 1-5 fluency rating from the judge.
        reason: One-sentence justification from the judge.
        error_examples: Up to ~3 short OCR-error examples the judge identified.
        model_name: Identifier of the judge model that produced the rating.
        latency_ms: Wall-clock time from request start to response, including
            retries.
    """

    rating: int
    reason: str
    error_examples: list[str]
    model_name: str
    latency_ms: float


class FluencyJudgeError(RuntimeError):
    """A fluency-scoring call did not produce a valid result.

    Raised on JSON parse failure, missing required field, or out-of-range
    rating. Treated as a validation error by the caller rather than silently
    defaulting to a median score — see the module docstring's rationale.
    """


def _backoff_delay(attempt: int) -> float:
    """Seconds to wait before retrying after a failed attempt (1-based)."""
    return float(2**attempt) + random.uniform(0.0, 1.0)


def _parse_response(raw_text: str) -> tuple[int, str, list[str]]:
    """Parse the judge's text response into ``(rating, reason, error_examples)``.

    Raises :class:`FluencyJudgeError` on any deviation from the documented
    JSON schema. The errors carry enough context (the parse failure or the
    field that was missing/wrong-typed) that the caller can log them per
    page for the report.
    """
    stripped = raw_text.strip()
    # The model occasionally wraps its JSON in a markdown fence despite the
    # explicit "no markdown fences" instruction. Strip a single leading/
    # trailing fence if present so we do not fail on the easy case.
    if stripped.startswith("```"):
        # Drop the opening fence line and any trailing fence.
        lines = stripped.splitlines()
        lines = [line for line in lines if not line.startswith("```")]
        stripped = "\n".join(lines).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise FluencyJudgeError(
            f"judge response was not valid JSON: {exc.msg} (offset {exc.pos})"
        ) from exc

    if not isinstance(parsed, dict):
        raise FluencyJudgeError(
            f"judge response was JSON but not an object (got {type(parsed).__name__})"
        )

    if "rating" not in parsed:
        raise FluencyJudgeError("judge response missing 'rating' field")
    rating = parsed["rating"]
    if not isinstance(rating, int) or not (1 <= rating <= 5):
        raise FluencyJudgeError(f"judge response 'rating' must be an integer 1-5, got {rating!r}")

    reason = parsed.get("reason", "")
    if not isinstance(reason, str):
        raise FluencyJudgeError(
            f"judge response 'reason' must be a string, got {type(reason).__name__}"
        )

    error_examples_raw = parsed.get("error_examples", [])
    if not isinstance(error_examples_raw, list):
        raise FluencyJudgeError(
            f"judge response 'error_examples' must be a list, got {type(error_examples_raw).__name__}"
        )
    # Defensive: cast each example to str so a non-string sneaking through
    # the LLM does not propagate as a typing error in downstream pandas code.
    error_examples = [str(e) for e in error_examples_raw]

    return rating, reason, error_examples


class ClaudeFluencyJudge:
    """LLM-based OCR fluency judge backed by Anthropic Claude.

    Mirrors the structure of :class:`src.ocr.claude.ClaudeAdapter` but for
    text-only judging instead of image OCR. The two classes intentionally do
    not share code — the judging contract (parse strict JSON; raise on
    failure) is different enough from the OCR contract (NFC-normalize text;
    detect refusal) that abstraction would obscure intent.

    Attributes:
        model_name: The Claude model identifier in use.
    """

    def __init__(self, model_name: str = DEFAULT_JUDGE_MODEL) -> None:
        """Build the underlying Anthropic client.

        Args:
            model_name: Claude model identifier. Defaults to
                :data:`DEFAULT_JUDGE_MODEL`.

        Raises:
            RuntimeError: If ``ANTHROPIC_API_KEY`` is not set in the
                environment.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )

        # Lazy import: keeps `import src.validation.llm_fluency` working
        # without the SDK installed; unit tests fake it.
        import anthropic

        self.model_name = model_name
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=0)
        self._rate_limit_error = anthropic.RateLimitError
        self._status_error = anthropic.APIStatusError
        self._connection_error = anthropic.APIConnectionError
        self._max_attempts = MAX_ATTEMPTS

    def score(self, ocr_text: str) -> FluencyResult:
        """Score one OCR output and return a structured fluency rating.

        Args:
            ocr_text: The OCR'd Unicode text to evaluate.

        Returns:
            A :class:`FluencyResult` with the integer rating, the judge's
            one-sentence reason, up to ~3 error examples, the model name,
            and the wall-clock latency.

        Raises:
            FluencyJudgeError: If the judge response cannot be parsed as the
                documented JSON schema, after retries.
            anthropic.RateLimitError: After the retry budget is exhausted.
            anthropic.APIStatusError: After the retry budget is exhausted
                (for a transient server error).
            anthropic.APIConnectionError: After the retry budget is
                exhausted.
        """
        prompt = FLUENCY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)
        messages = [{"role": "user", "content": prompt}]

        start = time.time()
        raw_text = self._call_with_retry(messages, ocr_text)
        latency_ms = (time.time() - start) * 1000.0

        rating, reason, error_examples = _parse_response(raw_text)
        return FluencyResult(
            rating=rating,
            reason=reason,
            error_examples=error_examples,
            model_name=self.model_name,
            latency_ms=latency_ms,
        )

    def _call_with_retry(self, messages: list[dict], ocr_text: str) -> str:
        """Run the judge call with exponential-backoff retry.

        Returns the raw text response. Retry-budget-exhaustion raises the
        original SDK exception so the caller can decide how to handle it.
        """
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.messages.create(
                    model=self.model_name,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    messages=messages,
                )
                # Extract the text from all text blocks; concatenate so a
                # split response is reassembled in order.
                return "".join(block.text for block in response.content if block.type == "text")
            except self._rate_limit_error as exc:
                self._sleep_or_raise(attempt, exc, len(ocr_text))
            except self._status_error as exc:
                if exc.status_code is None or exc.status_code < SERVER_ERROR_STATUS:
                    # 4xx (client error) will not improve on retry; propagate.
                    raise
                self._sleep_or_raise(attempt, exc, len(ocr_text))
            except self._connection_error as exc:
                # Network blip — treat as transient.
                self._sleep_or_raise(attempt, exc, len(ocr_text))

        raise AssertionError("retry loop exited without returning or raising")

    def _sleep_or_raise(self, attempt: int, exc: Exception, ocr_len: int) -> None:
        """Back off before the next retry, or re-raise on the final attempt."""
        if attempt >= self._max_attempts:
            raise exc

        delay = _backoff_delay(attempt)
        LOG.warning(
            "Fluency judge transient error on attempt %d/%d (ocr_len=%d, %s); retrying in %.1fs.",
            attempt,
            self._max_attempts,
            ocr_len,
            type(exc).__name__,
            delay,
        )
        time.sleep(delay)
