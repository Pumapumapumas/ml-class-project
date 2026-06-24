# `src.ocr`

OCR adapter layer for the Telugu OCR project. Every backend satisfies one small contract — input is a page-image `Path`, output is NFC-normalized Unicode text — so the batch runner and the Phase 4 validation code call any model with identical code. Empty pages and model refusals come back as `OCRResult(text="", ...)` (logged, not raised); only genuine failures (missing file, missing API key, exhausted retry budget) raise. **This PR ships the interface and the Gemini 1.5 Flash adapter.** The Tesseract baseline and the optional Surya adapter conform to the same contract but are implemented elsewhere (see [`docs/development/phase_3_ocr_pipeline.md`](../../docs/development/phase_3_ocr_pipeline.md), Tasks 4 and 3).

## Public surface

```python
@dataclass(frozen=True)
class OCRResult:
    text: str                  # NFC-normalized Unicode ("" for empty/refusal)
    model_name: str            # e.g. "gemini-1.5-flash"
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
    model_name: str = "gemini-1.5-flash"
    def __init__(self, model_name: str = "gemini-1.5-flash") -> None: ...
    def ocr(self, image_path: Path) -> OCRResult: ...
```
Gemini 1.5 Flash backend via `google-generativeai`. Reads `GEMINI_API_KEY` from the environment and raises at construction if it is missing. Applies the project's Telugu OCR system prompt, NFC-normalizes the output, retries transient rate-limit / unavailable errors with exponential backoff (5 attempts), and detects short non-Telugu refusals — returning an empty string rather than letting an apology pollute the corpus.

## CLI

`scripts/run_ocr.py` batch-runs an adapter over a directory of `.jpg` images, writing one `.txt` per page (mirroring the input layout) plus a `manifest.jsonl` carrying per-page `latency_ms`, `text_length`, and any `error`. Idempotent (skips existing outputs unless `--overwrite`); a single page failure is logged and recorded but does not abort the batch. See `python scripts/run_ocr.py --help`.

```bash
python scripts/run_ocr.py --model gemini --input data/external/eval_subset --output data/processed/eval_subset/gemini_raw
```
