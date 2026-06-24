"""Unit tests for ``src.preprocessing.pipeline``.

Order and toggling are verified with small recording stages; the no-mutation
contract is checked against the real deskew + binarize stages.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from src.preprocessing import binarize, deskew
from src.preprocessing.pipeline import Pipeline


def _recorder(name: str, log: list[str]):
    """A stage that records that it ran and returns its input unchanged."""

    def stage(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        log.append(name)
        return image

    return stage


def test_empty_pipeline_returns_input_unchanged():
    image = np.full((20, 30, 3), 127, dtype=np.uint8)
    result = Pipeline([]).run(image)
    assert result is image


def test_two_stage_pipeline_applies_stages_in_order():
    log: list[str] = []
    pipeline = Pipeline(
        [
            ("first", _recorder("first", log), True),
            ("second", _recorder("second", log), True),
        ]
    )
    pipeline.run(np.zeros((10, 10, 3), dtype=np.uint8))
    assert log == ["first", "second"]


def test_disabling_a_stage_via_enable_skips_it():
    log: list[str] = []
    pipeline = Pipeline(
        [
            ("first", _recorder("first", log), True),
            ("second", _recorder("second", log), True),
        ]
    )
    pipeline.run(np.zeros((10, 10, 3), dtype=np.uint8), enable={"first": False})
    assert log == ["second"]


def test_default_disabled_stage_is_skipped():
    log: list[str] = []
    pipeline = Pipeline([("first", _recorder("first", log), False)])
    pipeline.run(np.zeros((10, 10, 3), dtype=np.uint8))
    assert log == []


def test_enable_can_turn_on_a_default_off_stage():
    log: list[str] = []
    pipeline = Pipeline([("first", _recorder("first", log), False)])
    pipeline.run(np.zeros((10, 10, 3), dtype=np.uint8), enable={"first": True})
    assert log == ["first"]


def test_run_does_not_mutate_input_array():
    image = np.full((120, 160, 3), 200, dtype=np.uint8)
    original = image.copy()
    pipeline = Pipeline([("deskew", deskew, True), ("binarize", binarize, True)])
    pipeline.run(image)
    assert np.array_equal(image, original)


def test_duplicate_stage_names_rejected():
    with pytest.raises(ValueError, match="unique"):
        Pipeline([("dup", deskew, True), ("dup", binarize, True)])


def test_enable_with_unknown_stage_name_rejected():
    pipeline = Pipeline([("deskew", deskew, True)])
    with pytest.raises(ValueError, match="unknown stage"):
        pipeline.run(np.zeros((10, 10, 3), dtype=np.uint8), enable={"nope": False})


def test_stage_names_reports_order():
    pipeline = Pipeline([("deskew", deskew, True), ("binarize", binarize, True)])
    assert pipeline.stage_names == ["deskew", "binarize"]
