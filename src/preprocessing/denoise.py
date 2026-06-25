"""Denoise stage: reduce salt-and-pepper / sensor noise while preserving edges.

Historical Telugu scans carry scanner-sensor noise, dust speckles, and
mild salt-and-pepper artifacts that degrade OCR. This stage applies
OpenCV's **fast non-local means denoising** for grayscale images, which
preserves character-stroke edges much better than a Gaussian blur — a
Gaussian would smear the small Telugu vowel marks (matras) along with the
noise.

Color images are converted to BGR-3-channel non-local means; grayscale
inputs stay grayscale. Default tuning targets light-to-moderate noise; the
``h`` parameter controls filter strength.

Importantly, denoise PRESERVES the grayscale gradient (unlike adaptive
binarization). This is what the Phase 5 ablation study tests: whether
grayscale-preserving preprocessing stages help downstream OCR, in contrast
to the binarize stage which the matrix data showed to be net-negative.

Part of the ``src/preprocessing`` pipeline; see
``docs/development/phase_2_preprocessing.md`` Task 3.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Filter strength for the luminance channel. Higher values remove more
# noise but also more detail. 7-10 is the documented sweet-spot range for
# document scans (OpenCV docs); we use the lower end to preserve thin
# Telugu strokes.
DEFAULT_H = 7

# Template-window size; the larger this is, the more aggressively the
# filter searches for similar patches to average against.
DEFAULT_TEMPLATE_WINDOW = 7

# Search-window size; the area in which to search for similar patches. 21
# is OpenCV's recommended default and the value used in the canonical
# document-OCR preprocessing recipes.
DEFAULT_SEARCH_WINDOW = 21


def denoise(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Denoise a document image using fast non-local means.

    Args:
        image: Input image as a 2-D grayscale or 3-D BGR ``uint8`` array.

    Returns:
        The denoised image, same shape and dtype as the input. Edges
        (character strokes, page boundaries) are preserved more faithfully
        than they would be under a Gaussian blur.
    """
    if image.ndim == 2:
        # Grayscale path — the workhorse for document images.
        result = cv2.fastNlMeansDenoising(
            image,
            None,
            h=DEFAULT_H,
            templateWindowSize=DEFAULT_TEMPLATE_WINDOW,
            searchWindowSize=DEFAULT_SEARCH_WINDOW,
        )
    else:
        # BGR 3-channel path; same algorithm but applied to luminance and
        # chrominance separately.
        result = cv2.fastNlMeansDenoisingColored(
            image,
            None,
            h=DEFAULT_H,
            hColor=DEFAULT_H,
            templateWindowSize=DEFAULT_TEMPLATE_WINDOW,
            searchWindowSize=DEFAULT_SEARCH_WINDOW,
        )

    logger.debug("Denoised image of shape %s with h=%d.", image.shape, DEFAULT_H)
    return result
