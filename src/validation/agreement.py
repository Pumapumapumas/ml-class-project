"""Cross-model agreement scoring — Phase 4 LLM-validation Method B.

The idea behind this method: if two independent OCR models converge on the
same Unicode text for a page, that page is probably easy; if they diverge,
that page is probably hard. The agreement signal is therefore a ground-
truth-free proxy for OCR quality. Phase 4's calibration notebook tests
whether this signal correlates with the CER ground truth on the eval
subset; Phase 5 applies it at scale where ground truth is unavailable.

The signal is implemented as a ``difflib.SequenceMatcher.ratio()`` on the
two NFC-normalized texts. ``ratio()`` returns a float in ``[0.0, 1.0]``:
``1.0`` for identical strings, ``0.0`` for fully-disjoint strings, with a
useful gradient in between.

Caveat (documented in the report's Limitations section). With only Gemini
and Tesseract on the comparison, the agreement signal is weakened because
Tesseract is a known-weak baseline on Telugu — high "agreement" between a
strong and a weak model conflates "easy page" with "the strong model
agreed with a known-poor reading." With Claude added as a third strong
model, the Gemini-vs-Claude pairwise signal is more meaningfully a "two
strong models converged" signal.

See ``docs/development/phase_4_llm_validation.md`` Task 4.
"""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
from itertools import combinations


def _nfc(text: str) -> str:
    """Normalize ``text`` to Unicode NFC. Idempotent."""
    return unicodedata.normalize("NFC", text)


def agreement_score(text_a: str, text_b: str) -> float:
    """Return a ``[0.0, 1.0]`` similarity score between two OCR outputs.

    Both inputs are NFC-normalized first so equivalent Unicode forms do not
    artificially depress the score. The underlying ratio is
    ``difflib.SequenceMatcher.ratio()`` (a "gestalt pattern matching"
    similarity, character-level), which is deterministic, pure Python, and
    fast enough to scale to the full submission sample without an API call.

    Args:
        text_a: One OCR output, e.g. Gemini's reading of a page.
        text_b: A second OCR output for the SAME page, e.g. Claude's reading.

    Returns:
        Similarity ratio. ``1.0`` for identical inputs (after NFC), ``0.0``
        for fully-disjoint inputs, with a useful gradient in between.

        Two empty strings return ``1.0`` (vacuously identical) — this matches
        ``SequenceMatcher`` behavior and avoids a special case in callers.
    """
    return SequenceMatcher(None, _nfc(text_a), _nfc(text_b)).ratio()


def mean_pairwise_agreement(texts: list[str]) -> float:
    """Mean pairwise agreement across an arbitrary number of OCR readings.

    Computes ``agreement_score`` for every unordered pair of strings in
    ``texts`` and returns the arithmetic mean. The intuition: a page that
    every model converges on has high mean pairwise agreement; a page that
    the models disagree on has low mean pairwise agreement.

    Args:
        texts: A list of OCR outputs for the SAME page produced by different
            models. Must contain at least two strings.

    Returns:
        Mean pairwise similarity. With two inputs this collapses to
        :func:`agreement_score`.

    Raises:
        ValueError: If ``texts`` contains fewer than two strings — a
            single-model agreement signal is undefined.
    """
    if len(texts) < 2:
        raise ValueError(f"mean_pairwise_agreement needs at least 2 OCR outputs, got {len(texts)}")

    pairs = list(combinations(texts, 2))
    return sum(agreement_score(a, b) for a, b in pairs) / len(pairs)
