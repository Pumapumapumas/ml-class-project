"""Image preprocessing pipeline for the Telugu OCR project.

Public surface:

- :func:`~src.preprocessing.deskew.deskew` — correct scan skew.
- :func:`~src.preprocessing.binarize.binarize` — adaptive-threshold to binary.
- :class:`~src.preprocessing.pipeline.Pipeline` — compose togglable stages.
- :class:`~src.preprocessing.base.PreprocessingStage` — the stage contract.

The package convention is BGR ``uint8`` images on input; see
:mod:`src.preprocessing.base`. Phase 2 ships deskew and binarize; denoise and
contrast are deferred (see ``docs/development/phase_2_preprocessing.md``).
"""

from __future__ import annotations

from src.preprocessing.base import PreprocessingStage
from src.preprocessing.binarize import binarize
from src.preprocessing.deskew import deskew
from src.preprocessing.pipeline import Pipeline

__all__ = ["Pipeline", "PreprocessingStage", "binarize", "deskew"]
