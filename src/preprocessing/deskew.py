"""Deskew stage: detect and correct page rotation.

Scanned pages are often fed through a scanner at a slight angle. A few
degrees of skew is invisible to a human but degrades downstream OCR, which
expects roughly horizontal text lines. This stage estimates the dominant
skew angle with the ``deskew`` library (a Hough-transform-based detector)
and rotates the page to flatten it.

Below a configurable magnitude the detected angle is treated as noise and
the image is returned unchanged — a sub-degree rotation smears edges through
interpolation without buying any real alignment.

Part of the ``src/preprocessing`` pipeline; see
``docs/development/phase_2_preprocessing.md`` Task 2.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from deskew import determine_skew
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Fill colour for pixels exposed by the rotation. Document scans are
# light-on-dark inverted only after binarization; the raw input is dark text
# on a light background, so white corners are the least-surprising fill.
_BORDER_WHITE = 255


def deskew(
    image: NDArray[np.uint8],
    angle_threshold_deg: float = 0.5,
) -> NDArray[np.uint8]:
    """Rotate an image to correct for scan skew.

    The skew angle is estimated on a grayscale view of the image. If no angle
    can be determined (the detector returns nothing) or the magnitude is below
    ``angle_threshold_deg``, the input is returned unchanged. Otherwise the
    image is rotated about its centre by the detected angle, preserving the
    original height and width; corners exposed by the rotation are filled with
    white.

    Args:
        image: Input image as a 2-D grayscale or 3-D BGR ``uint8`` array.
        angle_threshold_deg: Skew magnitudes (in degrees) below this value are
            treated as noise and left uncorrected. Must be non-negative.

    Returns:
        The deskewed image, same shape and channel count as the input. When the
        skew is below threshold or undetectable, the original array is returned
        unchanged (a new array is never allocated in that case).

    Raises:
        ValueError: If ``image`` is not a 2-D or 3-D array, or if
            ``angle_threshold_deg`` is negative.
    """
    if image.ndim not in (2, 3):
        raise ValueError(f"image must be 2-D or 3-D, got {image.ndim}-D array")
    if angle_threshold_deg < 0:
        raise ValueError(f"angle_threshold_deg must be non-negative, got {angle_threshold_deg}")

    grayscale = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    angle = determine_skew(grayscale)
    if angle is None:
        logger.debug("No skew angle detected; returning input unchanged.")
        return image

    angle = float(angle)
    if abs(angle) < angle_threshold_deg:
        logger.debug(
            "Detected skew %.3f deg below threshold %.3f deg; returning input unchanged.",
            angle,
            angle_threshold_deg,
        )
        return image

    logger.debug("Correcting skew of %.3f deg.", angle)
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        rotation_matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=_BORDER_WHITE,
    )
