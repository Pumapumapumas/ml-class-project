# `src.ocr`

OCR adapter layer for the Telugu OCR project. Every backend satisfies one small contract — input is a page-image `Path`, output is NFC-normalized Unicode text — so the batch runner and the Phase 4 validation code call any model with identical code. Empty pages and model refusals come back as `OCRResult(text="", ...)` (logged, not raised); only genuine failures (missing file, missing API key, exhausted retry budget) raise. **This package ships the interface plus the Gemini 1.5 Flash and Claude Sonnet 4.6 adapters.** The Tesseract baseline and the optional Surya adapter conform to the same contract but are implemented elsewhere (see [`docs/development/phase_3_ocr_pipeline.md`](../../docs/development/phase_3_ocr_pipeline.md), Tasks 4 and 3).

## Public surface

```python
@dataclass(frozen=True)
class OCRResult:
    text: str                  # NFC-normalized Unicode ("" for empty/refusal)
    model_name: str            # e.g. "gemini-2.5-flash"
    latency_ms: float          # wall-clock incl. retries
    raw_response: dict | None  # optional provider-specific debug payload
```

```python
@runtime_checkable
class OCRAdapter(Protocol):
    model_name: str
    def ocr(self, image_path: Path) -> OCRResult: ...
```
The structural contract every adapter satisfies. Adapters do not subclass it; a class exposing `model_name` and `ocr` passes `isinstance(obj, OCRAdapter)`. That `isinstance` check (`src/ocr/tests/test_base.py`) is the contract test a new-adapter author runs to verify conformance.

```python
class GeminiAdapter:
    model_name: str = "gemini-2.5-flash"
    def __init__(self, model_name: str = "gemini-2.5-flash") -> None: ...
    def ocr(self, image_path: Path) -> OCRResult: ...
```
Gemini 1.5 Flash backend via `google-generativeai`. Reads `GEMINI_API_KEY` from the environment and raises at construction if it is missing. Applies the project's Telugu OCR system prompt, NFC-normalizes the output, retries transient rate-limit / unavailable errors with exponential backoff (5 attempts; ~2, 4, 8, 16 s + jitter between attempts, so a sustained rate-limit can block a single page for ~30 s before giving up), and detects short non-Telugu refusals — returning an empty string rather than letting an apology pollute the corpus.

- **`ClaudeAdapter`** (`claude.py`) — Claude Sonnet 4.6 backend via `anthropic` (`--model claude`). Mirrors `GeminiAdapter`: same system prompt, NFC normalization, exponential-backoff retry (rate-limit / 5xx), and refusal heuristic. Reads `ANTHROPIC_API_KEY` from the environment and raises at construction if it is missing. Override the model (e.g. `claude-opus-4-8`) via `ClaudeAdapter(model_name=...)`.

## CLI

`scripts/run_ocr.py` batch-runs an adapter over a directory of `.jpg` images, writing one `.txt` per page (mirroring the input layout) plus a `manifest.jsonl`. Idempotent (skips existing outputs unless `--overwrite`); a single page failure is logged and recorded but does not abort the batch. See `python scripts/run_ocr.py --help`.

```bash
python scripts/run_ocr.py --model gemini --input data/external/eval_subset --output data/processed/eval_subset/gemini_raw
```

### `manifest.jsonl` schema (Phase 4 reads this)

One JSON object per page that has output on disk. `(book_id, page_id)` is the composite key — `page_id` alone (the filename stem) repeats across books.

| Field | Type | Notes |
|---|---|---|
| `page_id` | str | Image filename stem, e.g. `page_0001`. |
| `book_id` | str | Containing book directory, or `"."` for images at the input root. |
| `model` | str | The adapter's own identifier (e.g. `gemini-2.5-flash`) — identical on processed, skipped, and failed records. |
| `latency_ms` | float \| null | Wall-clock incl. retries on a processed page; `null` on skipped/failed. |
| `text_length` | int \| null | Char count of the output; from disk on a skipped page; `null` on a failed page (distinct from `0`, a genuinely blank page). |
| `skipped` | bool | Present and `true` only when the page was skipped (output already existed, no `--overwrite`). |
| `error` | str | Present only on failure: `"<ExceptionType>: <message>"`. |
