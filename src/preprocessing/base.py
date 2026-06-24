"""Interface contract for image-preprocessing stages.

A preprocessing *stage* is any callable that takes one image and returns one
image. Concrete stages in this package (``deskew``, ``binarize``) are plain
functions; the :class:`PreprocessingStage` protocol below documents the
structural contract they all satisfy so the :class:`~src.preprocessing.pipeline.Pipeline`
can compose them interchangeably.

The image-representation convention for the whole package is **BGR uint8**
(OpenCV's native layout), per ``docs/development/phase_2_preprocessing.md``
Task 1. Stages convert to grayscale internally where they need to and may
return a single-channel image (binarization does); the convention governs the
*input* a stage must accept, not a fixed output channel count.

See ``docs/development/phase_2_preprocessing.md`` for the role this interface
plays in the Phase 5 ablation study.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class PreprocessingStage(Protocol):
    """Structural contract for a single preprocessing stage.

    Any callable accepting a NumPy image and returning a NumPy image
    satisfies this protocol — concrete stages do not subclass it. It exists
    to give the pipeline and its callers a single named type to reference
    and to document the shared contract.

    A stage:

    - Accepts a 2-D grayscale or 3-D BGR ``uint8`` array.
    - Returns a ``uint8`` array (same channel count as the input, except
      where a stage's documented purpose is to change it — e.g. binarization
      returns single-channel).
    - Does not mutate its input array in place.
    """

    def __call__(self, image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Apply the stage to ``image`` and return the transformed image."""
        ...
