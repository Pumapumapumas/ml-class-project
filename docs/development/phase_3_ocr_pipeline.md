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

## Tasks

### 1. Define the OCR adapter interface [Eric]

- [ ] `src/ocr/base.py` with an `OCRAdapter` protocol/ABC: `ocr(image_path: Path) -> OCRResult` where `OCRResult` carries `text: str`, `model_name: str`, `latency_ms: float`, optional `raw_response: dict`
- [ ] Document the contract in a module docstring: input is a file path (not bytes — keeps callers honest about disk I/O), output is NFC-normalized Unicode
- [ ] Sketch the interface in `notebooks/03_ocr_design.ipynb` as a thinking artifact (optional)

**Completion criterion:** Interface defined; `OCRResult` dataclass exists; unit-test of contract passes (mock adapter returning fixed text).

### 2. Implement the Gemini adapter [Eric]

- [ ] `src/ocr/gemini.py` using `google-generativeai` SDK with Gemini 1.5 Flash (free tier) — NOT Gemini 1.5 Pro unless the team decides to pay for the quota
- [ ] System prompt from the project spec (Telugu OCR rules, Unicode output, no translation, no commentary)
- [ ] Exponential-backoff retry wrapper for rate limits (per the spec's `ocr_with_retry` pattern)
- [ ] Unicode NFC normalization in the adapter, not the caller
- [ ] Detect and flag short/empty responses (model refusal signal)
- [ ] Tests in `src/ocr/tests/test_gemini.py`: mocked-response unit tests; one `@pytest.mark.api` integration test against the real API

**Completion criterion:** Adapter runs on a single eval page and returns plausible Telugu Unicode text; integration test passes when `.env` is loaded.

### 3. Implement the Surya adapter [Teammate, Eric pairs]

- [ ] `src/ocr/surya.py` wrapping the `surya-ocr` package
- [ ] First-run model download caching (Surya pulls weights on first call) — document expected disk usage
- [ ] Unicode NFC normalization on output
- [ ] Tests: a single-page integration test (slow-marker, no API key needed)

**Completion criterion:** Adapter runs on a single eval page; integration test passes.

### 4. Implement the Tesseract baseline adapter [Teammate]

- [ ] `src/ocr/tesseract.py` using `pytesseract.image_to_string(lang="tel")`
- [ ] Document Tesseract install (system package `tesseract-ocr-tel`) in `docs/guide/teammate_onboarding.md`
- [ ] Tests: single-page integration test

**Completion criterion:** Adapter runs on a single eval page; expected weak quality (it's the baseline).

### 5. Build the batch runner [Eric]

- [ ] `src/ocr/cli.py` exposing `python -m src.ocr.cli --model <name> --input <dir> --output <dir>`
- [ ] Reads page paths, runs the adapter, writes one `.txt` per input image to the output directory, writes a `manifest.jsonl` carrying latency + model + page IDs
- [ ] Idempotent: skip pages already in the output directory unless `--overwrite`
- [ ] Structured logging per [`../standards/logging_standard.md`](../standards/logging_standard.md): one JSON line per page, not every retry
- [ ] Graceful failure handling: a single page failure does NOT kill the batch; log + continue

**Completion criterion:** Runner processes all 30 eval-subset pages for each adapter; manifests written; no silent failures.

### 6. Run the comparison matrix [Eric + Teammate]

- [ ] Execute: `{Gemini, Surya, Tesseract} × {raw, preprocessed}` on the 30-page eval subset = 6 runs × 30 pages = 180 OCR calls
- [ ] Output to `data/processed/eval_subset/<model>_<preprocessing-on|off>/`
- [ ] Capture latency, retry count, and any failures in the manifests
- [ ] Spot-check 3 outputs per cell visually for sanity (any all-English output is a red flag)

**Completion criterion:** Six output directories populated; manifests carry latency stats; no unhandled exceptions.

### 7. Run the submission sample [Eric]

- [ ] Pick the best (model, preprocessing) cell from the 30-page eval based on quick CER spot-check (Phase 4 will do the rigorous CER)
- [ ] Run that cell against 500+ additional pages (sampled across books) for the required submission deliverable
- [ ] Output to `data/processed/submission_sample/`
- [ ] Budget check: Gemini Flash free tier is 15 RPM / 1500 RPD. 500 pages at 15 RPM = ~35 minutes; well within free tier. Surya local has no cost.

**Completion criterion:** 500+ pages of OCR'd Unicode text on disk, ready for Phase 5 packaging.

### 8. Tests + standards check [Eric]

- [ ] `pytest -m "not slow and not api"` — clean
- [ ] `pytest -m api` with `.env` loaded — clean (gates on real API quota)
- [ ] `ruff check src/ocr/` — clean
- [ ] Confirm no API keys in logs, no keys in source code per [`../standards/credential_handling_standard.md`](../standards/credential_handling_standard.md)

**Completion criterion:** All checks green.

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
