"""Unit tests for ``src.validation.agreement``.

Covers the documented contract: identical strings return 1.0, fully-
disjoint strings return ~0.0, partial overlap returns a graded value,
NFC normalization is applied, two empty strings score as 1.0 (vacuously
identical, matching SequenceMatcher's behaviour), and mean_pairwise_agreement
requires at least two inputs.
"""

from __future__ import annotations

import unicodedata

import pytest

from src.validation.agreement import agreement_score, mean_pairwise_agreement

NFC_E_ACUTE = "é"
NFD_E_ACUTE = "é"


class TestAgreementScore:
    def test_identical_strings_return_one(self):
        assert agreement_score("hello", "hello") == 1.0

    def test_fully_disjoint_strings_return_zero(self):
        # No shared characters at all.
        assert agreement_score("abc", "xyz") == 0.0

    def test_partial_overlap_returns_graded_value(self):
        # The two strings share most of the prefix; some similarity expected.
        score = agreement_score("the quick brown fox", "the quick brown dog")
        assert 0.0 < score < 1.0

    def test_higher_overlap_yields_higher_score(self):
        # A two-character substitution should be more similar than a wholesale
        # replacement.
        small_edit = agreement_score("hello world", "hella world")
        big_edit = agreement_score("hello world", "alpha beta")
        assert small_edit > big_edit

    def test_empty_inputs_return_one(self):
        # SequenceMatcher's documented behaviour: two empty inputs are
        # vacuously identical. We accept this so callers do not need a
        # special case for the both-empty edge.
        assert agreement_score("", "") == 1.0

    def test_one_empty_input_returns_zero(self):
        # One empty + one non-empty => no overlap possible.
        assert agreement_score("", "hello") == 0.0
        assert agreement_score("hello", "") == 0.0

    def test_nfc_normalization_handled(self):
        # Same character, two Unicode forms => score as identical.
        assert agreement_score(NFC_E_ACUTE, NFD_E_ACUTE) == 1.0

    def test_telugu_identical_returns_one(self):
        telugu = unicodedata.normalize("NFC", "తెలుగు")
        assert agreement_score(telugu, telugu) == 1.0

    def test_returns_float_type(self):
        # Be explicit so == comparisons in callers are reliable.
        assert isinstance(agreement_score("a", "a"), float)


class TestMeanPairwiseAgreement:
    def test_two_identical_inputs(self):
        assert mean_pairwise_agreement(["hello", "hello"]) == 1.0

    def test_collapses_to_agreement_on_two_inputs(self):
        a, b = "the quick brown fox", "the quick brown dog"
        single = agreement_score(a, b)
        pairwise = mean_pairwise_agreement([a, b])
        assert pairwise == single

    def test_three_inputs_averages_three_pairs(self):
        # Three identical inputs => all three pairs score 1.0 => mean 1.0.
        assert mean_pairwise_agreement(["same", "same", "same"]) == 1.0

    def test_one_outlier_lowers_mean(self):
        # Two identical readings plus one outlier should produce a mean
        # below 1.0 but above 0.0.
        score = mean_pairwise_agreement(["hello world", "hello world", "alpha beta"])
        assert 0.0 < score < 1.0

    def test_raises_on_single_input(self):
        with pytest.raises(ValueError, match="at least 2"):
            mean_pairwise_agreement(["hello"])

    def test_raises_on_empty_list(self):
        with pytest.raises(ValueError, match="at least 2"):
            mean_pairwise_agreement([])

    def test_returns_float_type(self):
        assert isinstance(mean_pairwise_agreement(["a", "a"]), float)
