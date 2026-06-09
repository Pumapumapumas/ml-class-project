# Testing Standard

**Status:** Active
**Scope:** How tests are organized, run, and held to a quality bar.

---

## Principles

- **Tests accumulate.** Every meaningful piece of code ships with the tests that prove it works. Tests persist and compound into a regression suite.
- **Tests track their source.** When code changes, its tests update. When code is deleted, its tests go too. Stale tests asserting old behavior are worse than no tests — they pass green while the world has moved underneath them.
- **Tests live with their component.** Each `src/<component>/` directory owns a `tests/` subdirectory. This keeps imports clean and makes "find the tests for X" trivial.
- **Tests are discoverable.** `pytest` finds them by directory convention. No manual registration.

---

## Test runner

**`pytest`** is the runner. Install with the rest of the dev dependencies.

```bash
# All tests
pytest

# A specific component
pytest src/preprocessing/tests/

# Only fast tests (skip the integration tests)
pytest -m "not integration"

# With coverage
pytest --cov=src --cov-report=term-missing
```

---

## Test placement

### Component unit tests

Co-located with the component:

```
src/
└── preprocessing/
    ├── __init__.py
    ├── deskew.py
    ├── binarize.py
    └── tests/
        ├── __init__.py
        ├── test_deskew.py
        └── test_binarize.py
```

Each test file corresponds to a source file (`test_deskew.py` covers `deskew.py`).

### Integration tests

Cross-component or end-to-end tests live at the top level:

```
tests/
├── integration/
│   ├── test_full_preprocessing_pipeline.py
│   └── test_ocr_with_real_api.py
└── fixtures/
    ├── sample_telugu_page.png
    └── sample_ground_truth.txt
```

### Fixtures

Test data — small sample images, expected outputs, mock API responses — lives in `tests/fixtures/`. Keep fixtures small (a few KB to maybe 1 MB) so the repo stays lean. Anything larger gets generated on demand from a script in `scripts/`.

---

## Naming

| Thing | Convention |
|-------|-----------|
| Test file | `test_<module_under_test>.py` |
| Test function | `test_<behavior_being_verified>()` |
| Test class | `Test<ClassUnderTest>` (only when grouping makes sense) |

Bad: `test_1()`, `test_it_works()`, `test_function()`.
Good: `test_deskew_returns_input_unchanged_when_angle_is_zero()`.

The test name is the failure message. When something breaks, you should be able to read the name and know what was being checked.

---

## Test categories (markers)

We use pytest markers to categorize tests. Marker definitions live in `pyproject.toml` (or `pytest.ini`).

| Marker | Meaning |
|--------|---------|
| (none) | Fast unit test. Runs in <1s. No network, no disk except temp. |
| `@pytest.mark.integration` | Crosses component boundaries; may touch disk. |
| `@pytest.mark.slow` | Takes >5s. Don't run on every change. |
| `@pytest.mark.api` | Calls a real external API. Requires `.env` credentials. Skipped in CI by default. |

```python
@pytest.mark.api
def test_gemini_ocr_returns_telugu_unicode():
    ...
```

---

## What to test

**Test the contract, not the implementation.**

Good test:
> "When I pass a skewed image with a 5-degree rotation, `deskew()` returns an image with the text horizontal."

Bad test:
> "`deskew()` calls `cv2.getRotationMatrix2D` exactly once with these specific arguments."

The first survives refactoring. The second breaks the moment you swap OpenCV for scikit-image.

**Always test:**
- The happy path
- Edge cases (empty input, single-pixel image, all-white image, etc.)
- Error cases (does it raise `ValueError` for invalid input?)
- Known-tricky cases (the Telugu conjunct pages that broke last week)

**Skip:**
- Tests that just exercise getters/setters
- Tests of third-party library behavior (we trust pandas to add correctly)
- Tests so flaky they get retried — diagnose the flake, don't bandaid it

---

## Discipline

- **Don't `xfail` or `skip` a failing test to make CI green** without explaining why in the marker.
- **Don't comment out a test to skip it.** Delete it or use `@pytest.mark.skip(reason="...")`.
- **If a test is flaky, find the root cause** — race condition, time dependency, network flakiness — and fix it. Retries are not a fix.
- **When a bug is reported, the first commit reproduces it as a failing test.** The second commit fixes it. This keeps the bug from coming back.

---

## Coverage

We aim for **~80% line coverage on `src/`**, measured by `pytest --cov=src`. Below 80% is a smell, not a hard fail. The goal is meaningful tests, not coverage theater (a test that runs every line without asserting anything raises coverage but proves nothing).

The CER/WER computation, the preprocessing pipeline, and the OCR adapter layer must be at 90%+ — those are the load-bearing components.

---

## Running tests before commit

Recommended local workflow:

```bash
ruff check src/ tests/        # lint
ruff format --check src/ tests/  # format check
pytest -m "not slow and not api"  # fast tests
```

Make this a pre-commit hook if you find yourself forgetting.
