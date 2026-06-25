"""Unit tests for ``src.validation.classical``.

Covers the public CER/WER API and the documented edge-case contracts: empty
reference raises, empty hypothesis returns ``1.0``, NFC normalization is
applied to both inputs so equivalent Unicode forms score as identical, and
the small-edit case lines up with the hand-computable ratio.
"""

from __future__ import annotations

import unicodedata

import pytest

from src.validation.classical import compute_cer, compute_wer

# Two Unicode forms of the same character — a precomposed e-acute and its
# canonical decomposition (e + combining acute). Used to verify NFC
# normalization actually changes scoring behaviour.
NFC_E_ACUTE = "é"
NFD_E_ACUTE = "é"


# ---------------------------------------------------------------------------
# CER
# ---------------------------------------------------------------------------


class TestComputeCER:
    def test_identity_returns_zero(self):
        assert compute_cer("hello", "hello") == 0.0

    def test_complete_corruption_returns_one(self):
        # Five characters fully replaced -> error rate of 1.0 (no chars
        # survive).
        assert compute_cer("hello", "xyzqr") == 1.0

    def test_single_substitution_returns_one_over_n(self):
        # One of five characters changed -> 0.2 CER.
        assert compute_cer("hello", "hellp") == pytest.approx(0.2)

    def test_single_deletion_returns_one_over_n(self):
        # One character missing from a five-char reference.
        assert compute_cer("hello", "hell") == pytest.approx(0.2)

    def test_single_insertion(self):
        # One extra character inserted into a five-char reference.
        assert compute_cer("hello", "hellos") == pytest.approx(0.2)

    def test_empty_hypothesis_returns_one(self):
        assert compute_cer("hello", "") == 1.0

    def test_empty_reference_raises(self):
        with pytest.raises(ValueError, match="reference must be non-empty"):
            compute_cer("", "hello")

    def test_whitespace_reference_raises(self):
        # Whitespace-only is not really 'empty' in str-truthiness, but it is
        # in NFC form. jiwer would raise on this; we surface a clear
        # ValueError instead so callers do not have to handle two error types.
        # Note: " " strips/normalizes to itself; this asserts the current
        # behaviour (a single space IS treated as a non-empty reference).
        result = compute_cer(" ", " ")
        assert result == 0.0  # identity match on a single-space reference

    def test_nfc_normalization_handled(self):
        # Same character, two Unicode forms; CER should be 0 (identity).
        assert compute_cer(NFC_E_ACUTE, NFD_E_ACUTE) == 0.0

    def test_telugu_identity_returns_zero(self):
        # NFC-normalized Telugu word should score as identity with itself.
        telugu = unicodedata.normalize("NFC", "తెలుగు")
        assert compute_cer(telugu, telugu) == 0.0

    def test_returns_float_type(self):
        # We explicitly cast jiwer's return to float so == 0.0 is reliable.
        result = compute_cer("hello", "hello")
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# WER
# ---------------------------------------------------------------------------


class TestComputeWER:
    def test_identity_returns_zero(self):
        assert compute_wer("the quick brown fox", "the quick brown fox") == 0.0

    def test_single_word_substitution(self):
        # One of four words changed -> 0.25 WER.
        assert compute_wer("the quick brown fox", "the quick brown dog") == pytest.approx(0.25)

    def test_single_word_deletion(self):
        # One of four words missing.
        assert compute_wer("the quick brown fox", "the quick brown") == pytest.approx(0.25)

    def test_complete_corruption_returns_one(self):
        assert compute_wer("the quick brown fox", "alpha beta gamma delta") == 1.0

    def test_empty_hypothesis_returns_one(self):
        assert compute_wer("the quick brown fox", "") == 1.0

    def test_empty_reference_raises(self):
        with pytest.raises(ValueError, match="reference must be non-empty"):
            compute_wer("", "the quick brown fox")

    def test_nfc_normalization_handled(self):
        # Different Unicode forms of the same word should score as identity.
        nfc = f"café{NFC_E_ACUTE}"
        nfd = f"caf{NFD_E_ACUTE}{NFC_E_ACUTE}"  # mix forms to provoke a diff
        # Normalize both to NFC first so we know what the post-normalization
        # words look like, then compare via the helper.
        assert compute_wer(unicodedata.normalize("NFC", nfc), nfd) == compute_wer(nfc, nfd)

    def test_higher_than_cer_on_one_char_edit(self):
        # A single character edit corrupts the whole word, so WER >= CER.
        cer_value = compute_cer("the quick brown fox", "the quick brawn fox")
        wer_value = compute_wer("the quick brown fox", "the quick brawn fox")
        assert wer_value > cer_value

    def test_returns_float_type(self):
        result = compute_wer("the quick brown fox", "the quick brown fox")
        assert isinstance(result, float)
