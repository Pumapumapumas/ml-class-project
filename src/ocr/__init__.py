"""OCR adapter layer for the Telugu OCR project.

Public surface:

- :class:`~src.ocr.base.OCRAdapter` — the structural contract every backend
  satisfies.
- :class:`~src.ocr.base.OCRResult` — the per-page result type.
- :class:`~src.ocr.gemini.GeminiAdapter` — Gemini 1.5 Flash backend.

The Tesseract baseline and the optional Surya adapter conform to the same
:class:`OCRAdapter` contract but are implemented in separate tasks; see
``docs/development/phase_3_ocr_pipeline.md``. The batch runner that drives any
adapter over a directory of pages lives at ``scripts/run_ocr.py``.
"""

from __future__ import annotations

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.gemini import GeminiAdapter

__all__ = ["GeminiAdapter", "OCRAdapter", "OCRResult"]
