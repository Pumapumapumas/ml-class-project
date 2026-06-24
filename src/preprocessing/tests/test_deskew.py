"""Unit tests for ``src.preprocessing.deskew``.

Tests use real Pillow/NumPy-generated images (see ``conftest.py``) and the
real ``deskew`` library — no mocking. Skew is verified by re-running the
detector on the output rather than by asserting on internal calls, so the
tests survive a swap of the underlying rotation implementation.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from deskew import determine_skew
from numpy.typing import NDArray

from src.preprocessing.deskew import deskew
from src.preprocessing.tests.conftest import SKEW_ANGLE_DEG


def _residual_skew(image: NDArray[np.uint8]) -> float:
    """Detected skew magnitude of an image, in degrees (0.0 if undetectable)."""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    angle = determine_skew(gray)
    return 0.0 if angle is None else abs(float(angle))


def test_zero_skew_input_returns_identity(blank_image: NDArray[np.uint8]):
    # A blank page has no detectable skew, so the input is returned as-is.
    result = deskew(blank_image)
    assert result is blank_image


def test_five_degree_skew_corrected_to_within_half_degree(skewed_image: NDArray[np.uint8]):
    # Sanity: the fixture really is skewed by ~5 degrees before correction.
    assert _residual_skew(skewed_image) == pytest.approx(SKEW_ANGLE_DEG, abs=0.5)
    corrected = deskew(skewed_image)
    assert _residual_skew(corrected) <= 0.5


def test_corrected_image_keeps_input_shape(skewed_image: NDArray[np.uint8]):
    corrected = deskew(skewed_image)
    assert corrected.shape == skewed_image.shape
    assert corrected.dtype == np.uint8


def test_all_white_image_returns_without_error():
    white = np.full((120, 160, 3), 255, dtype=np.uint8)
    result = deskew(white)
    # No edges to detect -> no rotation -> input returned unchanged.
    assert result is white


def test_skew_below_threshold_returns_identity(skewed_image: NDArray[np.uint8]):
    # The fixture is skewed ~5 deg; a threshold above that suppresses correction.
    result = deskew(skewed_image, angle_threshold_deg=10.0)
    assert result is skewed_image


def test_grayscale_input_is_accepted():
    gray = np.full((100, 100), 200, dtype=np.uint8)
    result = deskew(gray)
    assert result.ndim == 2


def test_rejects_non_2d_or_3d_input():
    with pytest.raises(ValueError, match="2-D or 3-D"):
        deskew(np.zeros((2, 2, 2, 2), dtype=np.uint8))


def test_rejects_negative_threshold(blank_image: NDArray[np.uint8]):
    with pytest.raises(ValueError, match="non-negative"):
        deskew(blank_image, angle_threshold_deg=-1.0)
