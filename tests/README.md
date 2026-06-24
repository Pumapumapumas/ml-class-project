# Tests

Top-level integration and end-to-end tests that span multiple `src/` subpackages.

Per-component unit tests are co-located with their source (e.g., `src/preprocessing/tests/`). See [`docs/standards/testing_standard.md`](../docs/standards/testing_standard.md) for full conventions.

## Layout

```
tests/
├── integration/        ← Cross-component tests (preprocessing → OCR, OCR → validation, etc.)
├── e2e/                ← Full-pipeline tests on small fixtures
└── fixtures/           ← Sample images, ground-truth files, mock API responses
```

Fixtures stay small (a few KB to ~1 MB each). Anything larger is generated on demand by a script in `scripts/`.

## Running

```bash
# All fast tests
pytest -m "not slow and not api"

# All tests including API-calling ones (requires .env)
pytest

# Just integration tests
pytest tests/integration/

# A specific test file
pytest tests/integration/test_preprocessing_e2e.py -v
```
