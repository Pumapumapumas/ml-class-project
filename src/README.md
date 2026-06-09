# Source code

The OCR pipeline implementation, organized as a Python package.

Anticipated layout (each subdirectory has its own `__init__.py` and `tests/`):

```
src/
├── preprocessing/      ← Image preprocessing pipeline (deskew, binarize, denoise, layout)
├── ocr/                ← OCR adapters (Gemini, Surya, Tesseract, etc.) behind a common interface
├── validation/         ← CER/WER computation + LLM-based validation methods
├── analysis/           ← Error categorization, plotting, summary statistics
└── utils/              ← Cross-cutting helpers: config loading, logging setup, path handling
```

Each subpackage's `__init__.py` exports its public surface only. Internal helpers stay internal.

Conventions for code style, error handling, type hints, and naming are in [`docs/standards/python_code_standard.md`](../docs/standards/python_code_standard.md).

Test conventions and placement are in [`docs/standards/testing_standard.md`](../docs/standards/testing_standard.md).
