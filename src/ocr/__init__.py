"""OCR adapter layer for the Telugu OCR project.

Public surface:

- :class:`~src.ocr.base.OCRAdapter` — the structural contract every backend
  satisfies.
- :class:`~src.ocr.base.OCRResult` — the per-page result type.
- :class:`~src.ocr.gemini.GeminiAdapter` — Gemini 2.5 Flash backend.
- :class:`~src.ocr.claude.ClaudeAdapter` — Claude Sonnet 4.6 backend.
- :class:`~src.ocr.tesseract.TesseractAdapter` — Tesseract 5 baseline via the
  pinned ``ml-class-project/tesseract`` Docker image.

The batch runner that drives any adapter over a directory of pages lives at
``scripts/run_ocr.py``.
"""

from __future__ import annotations

from src.ocr.base import OCRAdapter, OCRResult
from src.ocr.claude import ClaudeAdapter
from src.ocr.gemini import GeminiAdapter
from src.ocr.tesseract import TesseractAdapter

__all__ = ["ClaudeAdapter", "GeminiAdapter", "OCRAdapter", "OCRResult", "TesseractAdapter"]
