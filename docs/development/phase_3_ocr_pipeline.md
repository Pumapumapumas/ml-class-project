# Phase 3 — OCR Pipeline and Model Comparison

**Status:** Queued. Starts in parallel with Phase 2 (one teammate per phase initially; both converge on this once Phase 2 wraps).
**Time estimate:** 3-4 days. Highest engineering investment in the project.
**Rubric dimension:** Dimension 3 — OCR Pipeline Implementation and Model Comparison (25 pts). Highest single weight.

---

## Goal

Build a clean, robust OCR adapter layer under `src/ocr/` that lets us run any of N OCR models against any set of pages with the same calling code. Implement three adapters (Gemini Flash, Surya OCR, Tesseract baseline), run them across the Phase 1 evaluation subset (both raw and preprocessed), and produce per-page output ready for Phase 4 validation.

The 25-pt rubric distinguishes the 18-22 band ("two models, reasonable results, CER/WER reported") from 23-25 ("deliberate prompt engineering, robust batching, full-corpus scale, statistical context"). Our scope targets 23-25 explicitly.

---

## Dependencies

- Phase 1 evaluation subset frozen at `data/external/eval_subset/`.
- Phase 2 preprocessing pipeline ready (or at least the deskew + binarize stages — denoising and contrast can land in parallel).
- API keys configured per [`../standards/credential_handling_standard.md`](../standards/credential_handling_standard.md): `GEMINI_API_KEY` at minimum. No paid keys (no GPT-4o, no Claude) unless the team explicitly decides to spend.
- `surya-ocr` and `pytesseract` (+ `tesseract-ocr-tel` system package) installed.

---

## Scope note (post-time-pressure trim)

This phase is 25 rubric points — the largest single dimension. We want to do it well, but with four working days we cut where we can:

- **Tasks 1, 2, 5 (interface + Gemini + batch runner)** → autonomous engineer dispatch. Eric reviews the PR.
- **Task 3 (Surya adapter)** → DEFERRED to stretch. Surya weights are 2-5 GB and the install can fight us. We only attempt it if Phase 4 and Phase 5 are on schedule by Tuesday evening.
- **Task 4 (Tesseract adapter)** → Rauf. Already proven (Docker image is built and verified); just needs the Python wrapper.
- **Task 6 (matrix execution)** → Eric and Rauf together once adapters exist.
- **Task 7 (submission sample)** → Eric (running Gemini against 500+ pages).
- **Task 8 (tests + standards)** → Eric.

The submission deliverable still requires "at least two models compared." Gemini + Tesseract satisfies that with margin. Surya would be the third model if we get it.

---

## Tasks

### 1. Define the OCR adapter interface [Engineer dispatch — Eric reviews]

**What this task accomplishes.** Establish a single Python protocol every OCR model implementation conforms to. Without an interface, the batch runner has to know about Gemini, Tesseract, and Surya specifically; with one, the batch runner takes a `model_name` argument and dispatches polymorphically, and adding a new model is a single file change. This task is small in line count but high in leverage — every downstream task in this phase consumes it.

**Data flow / how it works.**

```
data/external/eval_subset/<book>/<page>.jpg
  │
  │   adapter.ocr(image_path)
  ▼
OCRResult(text, model_name, latency_ms, raw_response)
  │
  ▼
batch runner writes <output-dir>/<book>/<page>.txt
                    plus a row to manifest.jsonl
```

`OCRResult` is the polymorphic boundary: each model adapter is responsible for converting its model-specific response into this dataclass, including Unicode NFC normalization on the text field. Callers (the batch runner, downstream Phase 4 scoring) never touch model-specific code.

**Sub-tasks**:

- [x] `src/ocr/base.py` with an `OCRAdapter` protocol/ABC: `ocr(image_path: Path) -> OCRResult` where `OCRResult` carries `text: str`, `model_name: str`, `latency_ms: float`, optional `raw_response: dict`
- [x] Document the contract in a module docstring: input is a file path (not bytes — keeps callers honest about disk I/O), output is NFC-normalized Unicode
- [ ] Sketch the interface in `notebooks/03_ocr_design.ipynb` as a thinking artifact (optional — not done; the contract is documented in `src/ocr/base.py` and pinned by `src/ocr/tests/test_base.py`)

**Completion criterion:** Interface defined; `OCRResult` dataclass exists; unit-test of contract passes (mock adapter returning fixed text).

**Implementation.** `src/ocr/base.py` (Protocol via `typing.Protocol` with `@runtime_checkable`, `OCRResult` as a `@dataclass(frozen=True)`). Mirrors the pattern established in `src/preprocessing/base.py` from PR #1.

**How to verify when complete.**

```bash
pytest src/ocr/tests/test_base.py             # protocol conformance + OCRResult tests
.venv/bin/python -c "from src.ocr import OCRAdapter, OCRResult; print('OK')"
```

### 2. Implement the Gemini adapter [Engineer dispatch — Eric reviews]

**What this task accomplishes.** Build the production OCR adapter that does the heavy lifting on the corpus. Gemini 1.5 Flash is a vision-capable LLM that reads scanned Telugu pages natively (no preprocessing required by the model itself, though our Phase 2 pipeline still helps on the harder buckets). The model carries the rubric weight on Dimension 3 (OCR pipeline and model comparison): the Gemini-vs-Tesseract delta is the central comparison story.

**Data flow / how it works.**

```
image_path
  │
  │   GeminiAdapter.ocr(image_path)
  │     ├── load image bytes
  │     ├── construct request: system prompt + image part
  │     ├── send via google.generativeai.GenerativeModel
  │     │     └── retry on ResourceExhausted (rate limit) with backoff
  │     ├── parse response.text
  │     ├── unicodedata.normalize("NFC", text)
  │     └── refusal heuristic: short + no Telugu codepoints -> empty string
  ▼
OCRResult(text="...", model_name="gemini-1.5-flash", latency_ms=...)
```

The retry logic and the refusal heuristic are the two pieces of nontrivial logic; everything else is straight SDK plumbing. Both are unit-testable with a mocked SDK so we do not burn API quota during test runs.

**Sub-tasks**:

- [x] `src/ocr/gemini.py` using `google-generativeai` SDK with Gemini 1.5 Flash (free tier) — NOT Gemini 1.5 Pro unless the team decides to pay for the quota
- [x] System prompt from the project spec (Telugu OCR rules, Unicode output, no translation, no commentary)
- [x] Exponential-backoff retry wrapper for rate limits (per the spec's `ocr_with_retry` pattern)
- [x] Unicode NFC normalization in the adapter, not the caller
- [x] Detect and flag short/empty responses (model refusal signal)
- [x] Tests in `src/ocr/tests/test_gemini.py`: mocked-response unit tests; one `@pytest.mark.api` integration test against the real API

**Completion criterion:** Adapter runs on a single eval page and returns plausible Telugu Unicode text; integration test passes when `.env` is loaded.

**Implementation.** `src/ocr/gemini.py` containing `GeminiAdapter` class. API key from `os.environ["GEMINI_API_KEY"]` (raise at construction if missing). Adds `google-generativeai` to `requirements.txt` if not present.

**How to verify when complete.**

```bash
pytest src/ocr/tests/test_gemini.py -m "not api"          # mocked unit tests
pytest src/ocr/tests/test_gemini.py -m api                # hits the real API
.venv/bin/python -c "
from pathlib import Path
from src.ocr.gemini import GeminiAdapter
result = GeminiAdapter().ocr(Path('data/external/eval_subset/2015.328360.Andhra-Mahaniyulu/page_0086.jpg'))
print(f'len={len(result.text)} latency={result.latency_ms:.0f}ms')
print(result.text[:200])
"
```

**Cost / quota check.** Gemini 1.5 Flash free tier is 15 requests/minute and 1500 requests/day. The 30-page eval subset × 2 preprocessing variants × 1 model = 60 API calls per full eval-matrix run. Well inside the free tier. The submission-sample run in Task 7 will use ~500 calls; also within the daily limit.

### 3. Implement the Surya adapter [STRETCH — only if on schedule by Tuesday evening]

- [ ] `src/ocr/surya.py` wrapping the `surya-ocr` package
- [ ] First-run model download caching (Surya pulls weights on first call) — document expected disk usage
- [ ] Unicode NFC normalization on output
- [ ] Tests: a single-page integration test (slow-marker, no API key needed)

**Completion criterion:** Adapter runs on a single eval page; integration test passes.

**Status:** Deferred. The Surya install pulls 2-5 GB of model weights and has been known to fight pip resolvers. With Gemini + Tesseract we already satisfy the rubric requirement for "at least two models compared." Treat as stretch.

### 4. Implement the Tesseract baseline adapter [Teammate]

**What this task accomplishes.** Provide the classical-OCR baseline. Without a baseline, claims about Gemini's quality are unanchored — we can say "Gemini produced this output" but not "Gemini is better than X." Tesseract with the Telugu language pack is the canonical non-LLM baseline for South-Asian-language OCR; its weaknesses on Telugu (especially on conjuncts and diacritics) ARE the comparison story we want to tell.

**Data flow / how it works.**

```
image_path
  │
  │   TesseractAdapter.ocr(image_path)
  │     ├── shell out via scripts/run_tesseract.sh (handles Docker mount)
  │     ├── read the .txt output file
  │     └── unicodedata.normalize("NFC", text)
  ▼
OCRResult(text="...", model_name="tesseract-5-tel", latency_ms=...)
```

The Tesseract binary itself lives inside our Docker image (`ml-class-project/tesseract`, built by `setup_env.sh`), so the host stays clean of system-level Tesseract installs. The wrapper script at `scripts/run_tesseract.sh` already handles the volume mount.

**Sub-tasks**:

- [ ] `src/ocr/tesseract.py` using the Docker wrapper (NOT the host `pytesseract` package — the host has no Tesseract installed by design)
- [ ] Tests: single-page integration test marked `@pytest.mark.slow` (the Docker invocation is slow relative to a unit test)
- [ ] Update `src/ocr/README.md` to note Tesseract adapter exists; no separate doc update needed (the install lives in `setup_env.sh` already)

**Completion criterion:** Adapter runs on a single eval page; produces *some* Unicode Telugu output (quality will be visibly worse than Gemini's — expected, that is the baseline).

**Implementation.** `src/ocr/tesseract.py` containing `TesseractAdapter` class conforming to the `OCRAdapter` protocol that Task 1's engineer dispatch defines. Uses `subprocess.run([WRAPPER_PATH, ...])` rather than the `pytesseract` Python wrapper because the binary is in Docker not on the host PATH.

**How to verify when complete.**

```bash
pytest src/ocr/tests/test_tesseract.py        # the slow-marked integration test
.venv/bin/python -c "
from pathlib import Path
from src.ocr.tesseract import TesseractAdapter
result = TesseractAdapter().ocr(Path('data/external/eval_subset/2015.328360.Andhra-Mahaniyulu/page_0086.jpg'))
print(f'len={len(result.text)} latency={result.latency_ms:.0f}ms')
print(result.text[:200])
"
```

The output text will likely look garbled to a non-Telugu reader. That is correct — Tesseract on Telugu produces weak output, which is the entire reason we use it as the baseline.

#### Walk-through for Rauf

**Why this task matters.** Every comparison study needs a baseline. Without one, we cannot honestly say "Gemini is good" — we can only say "Gemini did this." Tesseract is the classical, non-LLM OCR baseline. It will probably perform poorly on Telugu (it always does), but that is the point — it shows what a pre-LLM tool looks like and quantifies how much modern vision models actually buy us.

**What you will produce.** A single Python file at `src/ocr/tesseract.py` that conforms to the OCR adapter interface (Eric and the engineer will define this in Task 1). Plus one unit/integration test.

**When you can start.** Right after the engineer dispatch for Task 1 (interface) merges. You need to know the shape of the `OCRAdapter` protocol and the `OCRResult` dataclass before you write a class that conforms to them. Eric will ping you.

**The mechanics — what Tesseract actually is.** Tesseract is a Linux command-line tool that does OCR. We already have it inside a Docker image (`ml-class-project/tesseract`, built by `scripts/setup_env.sh`). There is also a Python wrapper called `pytesseract` that lets you call it from Python. The trick: `pytesseract` by default looks for `tesseract` on the system PATH — but we have it in Docker, not on the host. So we either:

1. Shell out to `docker run ml-class-project/tesseract tesseract ...` ourselves, or
2. Use the wrapper script we already built: `scripts/run_tesseract.sh`.

Option 2 is cleaner because the wrapper already handles the volume mount.

**Starter skeleton** (the engineer's PR will refine the exact interface — adapt to whatever it defines):

```python
"""Tesseract OCR adapter.

Wraps the Tesseract 5 + Telugu language pack we ship as a Docker image.
Useful as a non-LLM baseline for model comparison; not expected to
produce high-quality output on dense Telugu script.
"""

from __future__ import annotations

import subprocess
import time
import unicodedata
from pathlib import Path

from src.ocr.base import OCRAdapter, OCRResult   # exact import per engineer PR

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "run_tesseract.sh"


class TesseractAdapter(OCRAdapter):
    model_name = "tesseract-5-tel"

    def ocr(self, image_path: Path) -> OCRResult:
        # Run the wrapper script that calls into the Docker image.
        # Output goes next to the input with a .txt extension, which
        # we then read and clean up.
        out_base = image_path.with_suffix("")  # strip .jpg
        start = time.time()
        subprocess.run(
            [str(WRAPPER), str(image_path.relative_to(REPO_ROOT)),
                          str(out_base.relative_to(REPO_ROOT)),
                          "-l", "tel", "--psm", "6"],
            check=True,
            cwd=REPO_ROOT,
        )
        latency_ms = (time.time() - start) * 1000

        raw_text = out_base.with_suffix(".txt").read_text(encoding="utf-8")
        normalized = unicodedata.normalize("NFC", raw_text)

        return OCRResult(
            text=normalized,
            model_name=self.model_name,
            latency_ms=latency_ms,
            raw_response={},
        )
```

**A small test.** Pattern after the corpus inventory tests:

```python
import pytest
from pathlib import Path
from src.ocr.tesseract import TesseractAdapter

@pytest.mark.integration
@pytest.mark.slow
def test_tesseract_runs_on_sample_page():
    sample = Path("data/raw/telugu-ocr/2015.328360.Andhra-Mahaniyulu/page_0010.jpg")
    result = TesseractAdapter().ocr(sample)
    assert result.text                          # not empty
    assert result.model_name == "tesseract-5-tel"
    assert result.latency_ms > 0
```

**What good looks like.**
- Adapter runs end to end on at least one real eval-subset page without throwing.
- Output is Unicode-NFC normalized.
- One integration test passes when run.
- Output text quality is genuinely bad. Telugu glyphs may be mostly missing or garbled. **That is expected and correct** — Tesseract on a complex script is a weak baseline. Do not "fix" this.

**Common pitfalls.**
- **Path handling.** The wrapper script expects paths relative to repo root. Use `image_path.relative_to(REPO_ROOT)` rather than passing absolute paths.
- **Docker permissions.** Make sure your user is in the `docker` group (`groups` should list `docker`). If not, your scripts will fail with "permission denied" on the docker socket. If this happens, ping Eric.
- **Tesseract page-segmentation mode.** `--psm 6` (single uniform block of text) is the right default for book pages. Other values can produce wildly different results; do not tune this in this PR.
- **Encoding.** Tesseract outputs UTF-8; always `unicodedata.normalize("NFC", ...)` on the read side to match the rest of the pipeline.

**Open a draft PR early.** Once your adapter runs on a single page without error, open a draft PR even if the test is not yet written. Eric can sanity-check the interface conformance early.

### 5. Build the batch runner [Engineer dispatch — Eric reviews]

**What this task accomplishes.** Turn the per-page adapter API into something Eric can run across the whole eval subset (or the larger submission sample) with a single CLI invocation. The runner is idempotent — if a page's output already exists it is skipped — so a partial run can be resumed by re-running the same command. It is also fault-tolerant: a single page failure does not abort the batch, and the manifest's `error` field records what failed.

**Data flow / how it works.**

```
--input <dir> (default: data/external/eval_subset/)
  │
  │   scripts/run_ocr.py --model <name>
  │     for each .jpg under --input:
  │       if output already exists and not --overwrite: skip
  │       adapter.ocr(image_path)
  │       write text to output dir mirroring input layout
  │       append a row to manifest.jsonl
  ▼
--output <dir> (default: data/processed/eval_subset/<model>_raw/)
  ├── <book_id>/<page_id>.txt   # one OCR'd text file per page
  └── manifest.jsonl             # per-page latency / error / text length
```

**Sub-tasks**:

- [x] `scripts/run_ocr.py` exposing `python scripts/run_ocr.py --model <name> --input <dir> --output <dir>` (shipped in `scripts/` to match the established CLI pattern — `build_corpus_inventory.py`, `run_preprocessing.py`)
- [x] Reads page paths, runs the adapter, writes one `.txt` per input image to the output directory, writes a `manifest.jsonl` carrying latency + model + page IDs
- [x] Idempotent: skip pages already in the output directory unless `--overwrite`
- [x] Structured logging per [`../standards/logging_standard.md`](../standards/logging_standard.md): one JSON line per page in `manifest.jsonl`, not every retry
- [x] Graceful failure handling: a single page failure does NOT kill the batch; log + continue

**Completion criterion:** Runner processes all 30 eval-subset pages for each adapter; manifests written; no silent failures.

**Implementation.** `scripts/run_ocr.py` following the same shape as `scripts/build_corpus_inventory.py` and `scripts/run_preprocessing.py` (logger setup, `sys.path.insert`, idempotent skip pattern, per-book INFO / per-page DEBUG). Dispatches to the adapter via `--model` (string → adapter class via a small registry).

**How to verify when complete.**

```bash
# Dry-run on a 2-page fixture
pytest tests/integration/test_ocr_e2e.py

# Real run on the eval subset (Eric does this once adapters are merged)
python scripts/run_ocr.py --model gemini --input data/external/eval_subset/ --output data/processed/eval_subset/gemini_raw/
ls data/processed/eval_subset/gemini_raw/*/*.txt | wc -l    # → 30
wc -l data/processed/eval_subset/gemini_raw/manifest.jsonl  # → 30 (one per page)
```

### 6. Run the comparison matrix [Eric + Teammate]

**What this task accomplishes.** Produce every OCR output Phase 4 (CER/WER scoring) and Phase 5 (analysis) need. The matrix is `{Gemini, Tesseract} × {raw, preprocessed}` = 4 cells × 30 eval pages = 120 OCR calls after the Surya cut (Surya is stretch). Each cell goes into its own output directory so Phase 4's scoring CLI can iterate cleanly.

**Data flow / how it works.**

```
For each cell (model, preprocessing):
  if preprocessing == "preprocessed":
    python scripts/run_preprocessing.py
      --input data/external/eval_subset/
      --output data/interim/eval_subset_preprocessed/
    INPUT_DIR := data/interim/eval_subset_preprocessed/
  else:
    INPUT_DIR := data/external/eval_subset/

  python scripts/run_ocr.py
    --model <name>
    --input $INPUT_DIR
    --output data/processed/eval_subset/<model>_<preprocessing>/
```

**Sub-tasks**:

- [ ] Execute: `{Gemini, Tesseract} × {raw, preprocessed}` on the 30-page eval subset = 4 runs × 30 pages = 120 OCR calls (Surya cut per scope note above)
- [ ] Output to `data/processed/eval_subset/<model>_<preprocessing>/`
- [ ] Capture latency, retry count, and any failures in the manifests
- [ ] Spot-check 3 outputs per cell visually for sanity (any all-English output is a red flag)

**Completion criterion:** Four output directories populated; manifests carry latency stats; no unhandled exceptions.

**Implementation.** Pure execution — no new code, just running `scripts/run_preprocessing.py` once and `scripts/run_ocr.py` four times. Eric drives. Rauf can spot-check outputs visually.

**How to verify when complete.**

```bash
for cell in gemini_raw gemini_preprocessed tesseract_raw tesseract_preprocessed; do
  echo "=== $cell ==="
  ls data/processed/eval_subset/$cell/*/*.txt | wc -l   # → 30 each
done
```

### 7. Run the submission sample [Eric]

**What this task accomplishes.** Satisfy the project spec's deliverable requirement of 500+ pages of OCR'd text from our best (model, preprocessing) configuration. The eval subset is too small to count as the deliverable — it is for measuring quality. The submission sample is the actual "here is what our pipeline produces" artifact.

**Data flow / how it works.**

```
1. Phase 4 produces CER results for each (model, preprocessing) cell.
2. Eric picks the cell with the lowest mean CER on the eval subset.
3. Run that cell against ~500 more pages (sampled across books for diversity).
4. Output goes to data/processed/submission_sample/ and is committed.
```

**Sub-tasks**:

- [ ] Pick the best (model, preprocessing) cell from the 30-page eval based on Phase 4 CER results
- [ ] Run that cell against 500+ additional pages (sampled across books) for the required submission deliverable
- [ ] Output to `data/processed/submission_sample/`
- [ ] Budget check: Gemini Flash free tier is 15 RPM / 1500 RPD. 500 pages at 15 RPM = ~35 minutes; well within free tier.

**Completion criterion:** 500+ pages of OCR'd Unicode text on disk, ready for Phase 5 packaging.

**Implementation.** Pure execution — no new code. Eric runs `python scripts/run_ocr.py` against a 500-page random sample drawn from the inventory CSV (we already have 415 pages downloaded; may need to bump `--subset 7` in `download_dataset.py` to reach 500+).

**How to verify when complete.**

```bash
find data/processed/submission_sample/ -name "*.txt" | wc -l    # → 500+
```

### 8. Tests + standards check [Eric]

**What this task accomplishes.** Phase-close hygiene. Before declaring Phase 3 done, confirm that the test suite is fully green at every marker level, that linting is clean, and that no credentials have leaked into source code or logs. Two of the most common ways to lose points on Dimension 6 (code quality) are: leaking secrets, and shipping a failing test suite.

**Sub-tasks**:

- [ ] `pytest -m "not slow and not api"` — clean
- [ ] `pytest -m api` with `.env` loaded — clean (gates on real API quota)
- [ ] `ruff check src/ocr/` — clean
- [ ] Confirm no API keys in logs, no keys in source code per [`../standards/credential_handling_standard.md`](../standards/credential_handling_standard.md)
- [ ] `git log -p -S GEMINI_API_KEY -- src/ scripts/` returns nothing (no literal key strings in the history)

**Completion criterion:** All checks green.

**Implementation.** Pure verification. No code.

**How to verify when complete.** The checks above ARE the verification. If they all pass, Phase 3 is done.

---

## Stretch (only if all required work finishes early)

- **Qwen2-VL adapter** (open-source VLM via `transformers`). Adds a 4th model for stronger comparison. Risk: GPU requirement; ~10 GB weights; slow without GPU.
- **AI4Bharat IndicOCR adapter.** Spec recommends this explicitly. Lower risk than Qwen but install path is more involved.
- **Prompt-variant study for Gemini.** Run 2-3 prompts and compare. Easy win if time allows; pads the "deliberate prompt engineering" claim on the rubric.
- **GPT-4o or Claude adapter.** Paid. Out of scope unless the team explicitly decides to spend ~$20 for a stronger comparison.

---

## Open questions / decisions needed

1. **Gemini Pro or Gemini Flash?** Pro is more accurate but quota is tighter on free tier. Recommendation: Flash for the full eval matrix; if time and quota allow, run Pro on the eval subset as a third cloud-model data point.
2. **Surya's segmentation: line-level or page-level output?** Surya defaults to line detection then OCR. Confirm it produces a single text blob, not a JSON of regions, before claiming parity with Gemini output.
3. **Submission-sample selection: best-model output, or multi-model?** Spec says "representative sample of the final OCR output." Recommendation: single best-cell output (cleaner story, easier to package). Document the choice in the report.
4. **Do we re-run Gemini if rate-limited mid-batch?** Yes, the exponential-backoff wrapper handles it. But document expected wall-clock for the matrix run so the team knows it's not stuck.

---

## Outputs / deliverables

- `src/ocr/` — `base.py`, `gemini.py`, `surya.py`, `tesseract.py`, `cli.py`, plus tests.
- `data/processed/eval_subset/<model>_<preprocessing>/` — 6 cells of OCR output, with manifests.
- `data/processed/submission_sample/` — 500+ page processed corpus sample.
- `logs/ocr_<timestamp>.jsonl` — structured run logs.

---

## Risks

- **Gemini free-tier quota exhaustion.** 1500 requests/day. The matrix run + submission sample + Phase 4 validation calls together could exceed it. Mitigation: spread across days; Surya is unmetered and can substitute for the submission sample if Gemini caps out.
- **Surya install / weight download fails.** Mitigation: start the Surya install on day 1 of Phase 3, parallel to Gemini work.
- **Tesseract Telugu pack quality is genuinely terrible.** This is by design — it's the baseline. The risk is that the baseline being THIS weak makes the comparison story uninteresting. Mitigation: include it anyway, frame as "this is what a non-LLM baseline looks like, and that's the point."
- **Output format drift across adapters.** Each model returns text differently (extra whitespace, headers, line-break conventions). Mitigation: normalize aggressively in each adapter, document the normalization in code.
