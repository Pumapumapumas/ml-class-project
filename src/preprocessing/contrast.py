"""Contrast enhancement stage: CLAHE for low-contrast historical scans.

Many of our corpus pages are scans of aged Telugu books with faded ink or
uneven illumination from the scanner — Section 4 of the final report
documents the "Faded" quality bucket explicitly. A global histogram
stretch would over-brighten the page and saturate already-clean regions,
so we use **CLAHE** (Contrast Limited Adaptive Histogram Equalization),
which operates on small tiles and clips per-tile histograms to prevent
the noise amplification that vanilla histogram equalization causes.

CLAHE preserves the grayscale gradient (unlike adaptive binarization)
while making faded character strokes more distinguishable from the page
background. Whether this helps downstream OCR is exactly the question the
Phase 5 ablation answers.

Operates on grayscale; for 3-channel BGR input we convert to LAB, apply
CLAHE to the L channel, then convert back. This standard pattern avoids
the color-shift artifacts that come from applying CLAHE to each BGR
channel independently.

Part of the ``src/preprocessing`` pipeline; see
``docs/development/phase_2_preprocessing.md`` Task 3.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Clip limit caps per-tile histogram amplification. 2.0 is OpenCV's
# documented default and the value used in published document-OCR
# pipelines (e.g., Tesseract preprocessing recipes). Higher values make
# the contrast lift more aggressive at the cost of noise amplification.
DEFAULT_CLIP_LIMIT = 2.0

# Per-tile grid for the adaptive operation. 8x8 is standard for document
# pages of ~1500 px width — each tile is roughly the size of a
# paragraph block, large enough that the local histogram is well-defined
# but small enough that the adaptation tracks per-region illumination.
DEFAULT_TILE_GRID = (8, 8)


def contrast(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Enhance contrast on a document image using CLAHE.

    Args:
        image: Input image as a 2-D grayscale or 3-D BGR ``uint8`` array.

    Returns:
        The contrast-enhanced image, same shape and dtype as the input.
        Grayscale gradient is preserved; faded character strokes become
        more distinguishable from the page background.
    """
    clahe = cv2.createCLAHE(clipLimit=DEFAULT_CLIP_LIMIT, tileGridSize=DEFAULT_TILE_GRID)

    if image.ndim == 2:
        result = clahe.apply(image)
    else:
        # 3-channel BGR -> convert to LAB, CLAHE the L channel only, convert back.
        # Avoids per-channel color shift you'd get from applying CLAHE to each
        # BGR channel independently.
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_chan, a, b = cv2.split(lab)
        l_chan = clahe.apply(l_chan)
        lab = cv2.merge((l_chan, a, b))
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    logger.debug(
        "Applied CLAHE (clip=%g, tile=%s) to image of shape %s.",
        DEFAULT_CLIP_LIMIT,
        DEFAULT_TILE_GRID,
        image.shape,
    )
    return result
