"""Shared pytest fixtures for ``src/preprocessing/`` tests.

Fixtures generate tiny real images with Pillow/NumPy at test time and hand them
to the stages as BGR ``uint8`` arrays (the package convention; see
``src/preprocessing/base.py``). No mocking of OpenCV or Pillow — the tests
exercise the same code paths production hits.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image, ImageDraw

# Angle, in degrees, by which the skewed fixture is deliberately rotated. The
# deskew tests assert the stage flattens the image back to near zero.
SKEW_ANGLE_DEG = 5.0


def _pil_to_bgr(image: Image.Image) -> NDArray[np.uint8]:
    """Convert a Pillow image to a BGR ``uint8`` NumPy array (OpenCV layout)."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


@pytest.fixture
def blank_image() -> NDArray[np.uint8]:
    """A 200x300 (HxW) solid-white BGR image."""
    return _pil_to_bgr(Image.new("RGB", (300, 200), color=(255, 255, 255)))


@pytest.fixture
def skewed_image() -> NDArray[np.uint8]:
    """A white page with horizontal black bars, rotated by ``SKEW_ANGLE_DEG``.

    Several evenly-spaced horizontal bars stand in for text lines so the
    Hough-based skew detector has strong, consistent edges to lock onto. The
    page is rotated counter-clockwise by ``SKEW_ANGLE_DEG`` with white fill, so
    a correctly working deskew stage should return it to near-horizontal.
    """
    width, height = 400, 400
    page = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(page)
    for y in range(60, height - 40, 50):
        draw.rectangle([40, y, width - 40, y + 10], fill=(0, 0, 0))
    rotated = page.rotate(SKEW_ANGLE_DEG, expand=False, fillcolor=(255, 255, 255))
    return _pil_to_bgr(rotated)


@pytest.fixture
def gradient_image() -> NDArray[np.uint8]:
    """Dark bars over a left-to-right brightness gradient (200x256 HxW).

    The background ramps 60..255 across the width and dark horizontal bars sit
    on top. A single global threshold cannot separate the bars from the
    background across the whole gradient (the bright-side background is darker
    than nothing, the dark-side background rivals the bars), so this is the
    case adaptive thresholding exists to handle: it should recover the bars as
    black against white everywhere, yielding a balanced binary output.
    """
    ramp = np.linspace(60, 255, num=256, dtype=np.uint8)
    gray = np.tile(ramp, (200, 1))
    page = Image.fromarray(gray).convert("RGB")
    draw = ImageDraw.Draw(page)
    for y in range(30, 200 - 20, 40):
        draw.rectangle([10, y, 256 - 10, y + 8], fill=(0, 0, 0))
    return _pil_to_bgr(page)
