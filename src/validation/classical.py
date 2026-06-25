"""Classical OCR accuracy metrics — Character Error Rate and Word Error Rate.

Wraps the ``jiwer`` library with Unicode NFC normalization applied to both
inputs so Unicode form mismatches do not artificially inflate error rates.
NFC normalization is a no-op when the input is already in NFC, which is what
our dataset and OCR adapters produce.

Two public functions:

- :func:`compute_cer` — Character Error Rate, the primary OCR metric used in
  the Phase 4 evaluation matrix and Phase 5 report.
- :func:`compute_wer` — Word Error Rate. For a Telugu corpus the "word"
  boundary is a bit fuzzy; ``jiwer`` handles whitespace tokenization for us.

Both metrics return a float in the closed interval ``[0.0, ~1.0]``, where 0
means the hypothesis matches the reference exactly and ~1 means the
hypothesis is completely wrong. ``jiwer`` can return slightly above 1.0 when
the hypothesis is much longer than the reference (extra insertions); that
behaviour is preserved here.

Edge-case contract:

- **Empty reference** raises ``ValueError``. CER and WER are mathematically
  undefined when the reference has no characters/words to compare against.
- **Empty hypothesis with non-empty reference** returns ``1.0``. Every
  reference character/word counts as a deletion; the error rate is total.
- **Reference == hypothesis** (after NFC normalization) returns ``0.0``.

See ``docs/development/phase_4_llm_validation.md`` Task 1 for the role this
module plays in the project.
"""

from __future__ import annotations

import unicodedata

from jiwer import cer, wer


def _nfc(text: str) -> str:
    """Normalize ``text`` to Unicode NFC form.

    Idempotent: calling this on already-NFC text returns the same string. We
    apply NFC consistently on every CER/WER call so that two equivalent
    representations of the same Unicode character (e.g. precomposed vs.
    decomposed Telugu vowel signs) do not artificially inflate the error
    rate.

    Args:
        text: Any Unicode string.

    Returns:
        The NFC-normalized form of ``text``.
    """
    return unicodedata.normalize("NFC", text)


def compute_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate between ``reference`` and ``hypothesis``.

    Computed as ``(substitutions + deletions + insertions) /
    total_reference_characters`` after both inputs are NFC-normalized.

    Args:
        reference: The ground-truth text (must be non-empty).
        hypothesis: The OCR output text.

    Returns:
        Character error rate. ``0.0`` for an exact match, ``1.0`` when the
        hypothesis is empty (or fully replaces the reference), can exceed
        ``1.0`` when the hypothesis is much longer than the reference.

    Raises:
        ValueError: If ``reference`` is empty after NFC normalization.
            CER is undefined with no reference characters to score against.
    """
    normalized_reference = _nfc(reference)
    if not normalized_reference:
        raise ValueError("reference must be non-empty to compute CER")
    normalized_hypothesis = _nfc(hypothesis)
    if not normalized_hypothesis:
        return 1.0
    return float(cer(normalized_reference, normalized_hypothesis))


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate between ``reference`` and ``hypothesis``.

    Computed as ``(substitutions + deletions + insertions) /
    total_reference_words`` after both inputs are NFC-normalized. Words are
    delimited by whitespace per ``jiwer``'s default tokenization, which is
    workable for Telugu prose where word boundaries are whitespace-marked.

    A single wrong character can corrupt an entire word, so WER is usually
    higher than CER on the same OCR output.

    Args:
        reference: The ground-truth text (must be non-empty).
        hypothesis: The OCR output text.

    Returns:
        Word error rate. ``0.0`` for an exact match, ``1.0`` when the
        hypothesis is empty (or every reference word is wrong), can exceed
        ``1.0`` when the hypothesis has many extra inserted words.

    Raises:
        ValueError: If ``reference`` is empty after NFC normalization. WER is
            undefined with no reference words to score against.
    """
    normalized_reference = _nfc(reference)
    if not normalized_reference:
        raise ValueError("reference must be non-empty to compute WER")
    normalized_hypothesis = _nfc(hypothesis)
    if not normalized_hypothesis:
        return 1.0
    return float(wer(normalized_reference, normalized_hypothesis))
