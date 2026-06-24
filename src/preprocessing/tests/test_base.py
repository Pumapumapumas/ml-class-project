"""Unit tests for ``src.preprocessing.base``.

The module defines only the :class:`PreprocessingStage` structural protocol,
which has no executable behaviour of its own. These tests verify the contract
it documents: the concrete stages structurally satisfy it (so the pipeline can
treat them interchangeably) and non-conforming objects do not.
"""

from __future__ import annotations

from src.preprocessing import binarize, deskew
from src.preprocessing.base import PreprocessingStage


def test_concrete_stages_satisfy_the_protocol():
    # @runtime_checkable lets isinstance verify the structural __call__ contract.
    assert isinstance(deskew, PreprocessingStage)
    assert isinstance(binarize, PreprocessingStage)


def test_non_callable_does_not_satisfy_the_protocol():
    assert not isinstance(42, PreprocessingStage)
    assert not isinstance("not a stage", PreprocessingStage)
