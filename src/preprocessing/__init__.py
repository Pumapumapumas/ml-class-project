"""Image preprocessing pipeline for the Telugu OCR project.

Public surface:

- :func:`~src.preprocessing.deskew.deskew` — correct scan skew.
- :func:`~src.preprocessing.binarize.binarize` — adaptive-threshold to binary.
- :func:`~src.preprocessing.denoise.denoise` — fast non-local means denoise (grayscale-preserving).
- :func:`~src.preprocessing.contrast.contrast` — CLAHE contrast enhancement (grayscale-preserving).
- :class:`~src.preprocessing.pipeline.Pipeline` — compose togglable stages.
- :class:`~src.preprocessing.base.PreprocessingStage` — the stage contract.

The package convention is BGR ``uint8`` images on input; see
:mod:`src.preprocessing.base`. Phase 2 originally shipped deskew + binarize; the
matrix data later showed binarize was net-negative for every OCR model. Denoise
and contrast were added in a Phase 5 ablation pass to test whether grayscale-
preserving stages help where binarize hurt; see the final report's Section 6.3
for the per-stage findings.
"""

from __future__ import annotations

from src.preprocessing.base import PreprocessingStage
from src.preprocessing.binarize import binarize
from src.preprocessing.contrast import contrast
from src.preprocessing.denoise import denoise
from src.preprocessing.deskew import deskew
from src.preprocessing.pipeline import Pipeline

__all__ = ["Pipeline", "PreprocessingStage", "binarize", "contrast", "denoise", "deskew"]
