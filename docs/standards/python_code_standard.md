# Python Code Standard

**Status:** Active
**Scope:** Conventions for Python code in this repo. Style, structure, and discipline.

---

## Language version

Python **3.11+**. We use modern syntax (`match`, `Self`, improved error messages). Don't write code that would only work on older Pythons.

---

## Style

**PEP 8** is the baseline. We enforce it with **`ruff`** (linter + formatter). Run before committing:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

If `ruff` complains, fix it — don't add `# noqa` to silence it without a comment explaining why.

---

## Type hints

**All public functions and methods have type hints.** Internal helpers can skip them if the signature is trivial.

```python
def normalize_unicode(text: str, form: str = "NFC") -> str:
    return unicodedata.normalize(form, text)
```

Use:
- `list[int]` not `List[int]` (Python 3.9+ generic syntax)
- `X | None` not `Optional[X]`
- `Path` from `pathlib`, not raw strings, for filesystem paths

---

## Docstrings

**Google-style docstrings on every public function, class, and module.** Public = anything imported elsewhere or part of the external API.

```python
def deskew(image: np.ndarray, angle_threshold: float = 0.5) -> np.ndarray:
    """Rotate an image to correct for skew.

    Args:
        image: Input image as a NumPy array in BGR or grayscale format.
        angle_threshold: Skew angles below this magnitude (in degrees) are
            treated as noise and not corrected.

    Returns:
        The rotated image, same shape as input.

    Raises:
        ValueError: If the input is not a 2-D or 3-D array.
    """
```

Module-level docstrings explain what the module does and its place in the pipeline.

---

## Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Module | `lower_snake` | `image_loader.py` |
| Package | `lower_snake` | `preprocessing/` |
| Class | `PascalCase` | `OcrAdapter` |
| Function / variable | `lower_snake` | `apply_threshold` |
| Constant | `UPPER_SNAKE` | `MAX_RETRIES` |
| "Private" | `_prefix` | `_internal_helper` |

Avoid:
- One-letter variable names except in math expressions and tight loops (`for i in range(...)` is fine, `d = compute()` is not)
- Type-of-thing suffixes like `data_list`, `result_dict` — let types document themselves
- Stuttering names like `auth.AuthManager.authenticate_auth_user`

---

## Module organization

A module should do one thing. If you're tempted to call it `utils.py` or `helpers.py`, you probably need to split it.

**Order within a module:**
1. Module docstring
2. Imports (stdlib → third-party → local, separated by blank lines)
3. Constants
4. Type aliases / dataclasses
5. Functions
6. Classes
7. `if __name__ == "__main__":` block (if any)

Imports are sorted by `ruff` / `isort` — don't fight it.

---

## Error handling

Per the engineering quality bar:

- **Don't wrap a problem in `try/except` to silence it.** Exceptions are diagnostic information.
- **Don't `pass` in an exception handler.** If you really want to ignore an error, log it and explain why.
- **Catch the specific exception you can handle, not bare `except:`.**
- **Validate at boundaries** (function inputs from the user, API responses, file I/O), trust internal code.

```python
# Bad
try:
    data = json.loads(response.text)
except:
    data = {}

# Good
try:
    data = json.loads(response.text)
except json.JSONDecodeError as e:
    logger.error("API returned non-JSON response: %s", response.text[:200])
    raise OcrApiError(f"Could not parse response: {e}") from e
```

---

## Imports

- **No wildcard imports.** `from x import *` is forbidden.
- **Absolute imports inside the package.** `from src.preprocessing import deskew`, not `from ..preprocessing import deskew`.
- **Local imports for circular-dep workarounds** — and add a comment explaining why.

---

## Logging

Use the `logging` module, not `print()`. See [Logging Standard](./logging_standard.md) for setup and conventions.

---

## Configuration

- **No hardcoded paths in source code.** Paths come from config or function arguments.
- **Secrets come from environment variables**, loaded via `python-dotenv` from `.env`. See [Credential Handling Standard](./credential_handling_standard.md).
- **Constants that vary between environments** (e.g., model names, retry counts) belong in a `config.py` or YAML config file, not scattered through the code.

---

## Testing

Every module has a corresponding test file. See [Testing Standard](./testing_standard.md).

---

## When in doubt

- Look at how similar code is written elsewhere in `src/`. Match the local style.
- If you're about to write a "clever" one-liner, write the boring four-line version. Readability > cleverness.
- If you need a helper, put it next to its caller first. Only promote to `src/utils/` when it's used in 3+ places.
