"""Binarize stage: adaptive thresholding to clean black-on-white text.

Converts a (possibly colour, possibly unevenly lit) page into a crisp
single-channel binary image where ink is black (0) and background is white
(255). Adaptive Gaussian thresholding computes a per-pixel threshold from a
local neighbourhood, which handles the uneven illumination and page yellowing
common in scanned books far better than a single global threshold.

Part of the ``src/preprocessing`` pipeline; see
``docs/development/phase_2_preprocessing.md`` Task 3.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Output value assigned to pixels above the local threshold (background).
_MAX_VALUE = 255
# A uniform image counts as "light" (-> white) at or above this intensity.
_LIGHT_DARK_MIDPOINT = 128


def binarize(
    image: NDArray[np.uint8],
    block_size: int = 11,
    c: int = 2,
) -> NDArray[np.uint8]:
    """Binarize an image with adaptive Gaussian thresholding.

    Colour input is converted to grayscale first. The threshold for each pixel
    is a Gaussian-weighted mean of its ``block_size`` x ``block_size``
    neighbourhood, minus ``c``. Pixels above their local threshold become white
    (255); the rest become black (0).

    A perfectly uniform image is a degenerate input for adaptive thresholding:
    with zero local variance every pixel equals its neighbourhood mean, so the
    ``mean - c`` threshold makes the comparison constant and the result no
    longer reflects intensity. Such an image is instead mapped to the nearer
    binary extreme — dark uniform fields to black, light ones to white — which
    is both well-defined and matches the intuitive contract that a blank black
    page binarizes to black and a blank white page to white.

    Args:
        image: Input image as a 2-D grayscale or 3-D BGR ``uint8`` array.
        block_size: Side length of the neighbourhood used to compute each
            pixel's threshold. Must be an odd integer greater than 1, per
            OpenCV's ``adaptiveThreshold`` requirement.
        c: Constant subtracted from the local mean. Larger values bias the
            output toward white (less ink retained).

    Returns:
        A single-channel ``uint8`` array the same height and width as the
        input, containing only the values 0 and 255.

    Raises:
        ValueError: If ``image`` is not a 2-D or 3-D array, or if ``block_size``
            is not an odd integer greater than 1.
    """
    if image.ndim not in (2, 3):
        raise ValueError(f"image must be 2-D or 3-D, got {image.ndim}-D array")
    if block_size <= 1 or block_size % 2 == 0:
        raise ValueError(f"block_size must be an odd integer > 1, got {block_size}")

    grayscale = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if grayscale.min() == grayscale.max():
        # Zero-variance image: adaptive thresholding is undefined here (see the
        # docstring). Map the uniform field to its nearest binary extreme.
        fill = _MAX_VALUE if grayscale.flat[0] >= _LIGHT_DARK_MIDPOINT else 0
        logger.debug("Uniform image (value=%d); mapping to %d.", grayscale.flat[0], fill)
        return np.full(grayscale.shape, fill, dtype=np.uint8)

    return cv2.adaptiveThreshold(
        grayscale,
        _MAX_VALUE,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c,
    )
