"""Unit tests for ``src.preprocessing.binarize``.

Tests use real NumPy/Pillow-generated images (see ``conftest.py``) and the
real OpenCV thresholding routine — no mocking.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from src.preprocessing.binarize import binarize


def test_pure_white_returns_white():
    white = np.full((50, 50, 3), 255, dtype=np.uint8)
    result = binarize(white)
    assert np.array_equal(np.unique(result), np.array([255], dtype=np.uint8))


def test_pure_black_returns_black():
    black = np.full((50, 50, 3), 0, dtype=np.uint8)
    result = binarize(black)
    assert np.array_equal(np.unique(result), np.array([0], dtype=np.uint8))


def test_gradient_produces_balanced_binary_output(gradient_image: NDArray[np.uint8]):
    result = binarize(gradient_image)
    # Output contains only the two binary extremes...
    assert set(np.unique(result).tolist()) <= {0, 255}
    # ...and both are actually present (not a degenerate all-one-colour image).
    assert (result == 0).any()
    assert (result == 255).any()


def test_output_is_single_channel(gradient_image: NDArray[np.uint8]):
    result = binarize(gradient_image)
    assert result.ndim == 2
    assert result.dtype == np.uint8
    assert result.shape == gradient_image.shape[:2]


def test_grayscale_input_is_accepted():
    gray = np.tile(np.linspace(0, 255, 100, dtype=np.uint8), (100, 1))
    result = binarize(gray)
    assert result.ndim == 2
    assert set(np.unique(result).tolist()) <= {0, 255}


def test_rejects_even_block_size():
    with pytest.raises(ValueError, match="odd integer > 1"):
        binarize(np.zeros((10, 10, 3), dtype=np.uint8), block_size=10)


def test_rejects_block_size_of_one():
    with pytest.raises(ValueError, match="odd integer > 1"):
        binarize(np.zeros((10, 10, 3), dtype=np.uint8), block_size=1)


def test_rejects_non_2d_or_3d_input():
    with pytest.raises(ValueError, match="2-D or 3-D"):
        binarize(np.zeros((2, 2, 2, 2), dtype=np.uint8))
