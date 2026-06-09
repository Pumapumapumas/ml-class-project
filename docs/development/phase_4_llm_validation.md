# Phase 4 — LLM-Assisted Validation Framework

**Status:** Queued. Starts when Phase 3 has output for at least one model + preprocessing cell.
**Time estimate:** 2-3 days.
**Rubric dimension:** Dimension 4 — LLM-Assisted Validation Framework (20 pts). Second-highest weight.

---

## Goal

Implement (a) the classical CER/WER scoring loop against the Phase 1 ground truth and (b) at least two LLM-based validation methods that produce a per-page quality signal WITHOUT reference text. Calibrate the LLM signals against the CER baseline on the eval subset so we can claim — with evidence — that the LLM scores meaningfully reflect OCR quality. Apply LLM validation at scale to a 100+ page stratified sample.

The 20-pt rubric distinguishes 14-17 ("at least one LLM method, partial calibration") from 18-20 ("at least two LLM methods, calibrated against ground truth, scales to full corpus"). We target 18-20.

---

## Dependencies

- Phase 3 OCR output for at least the 30-page eval subset (and ideally for the submission sample so we can validate at scale).
- Phase 1 ground truth available at `data/external/eval_subset/`.
- Gemini API access (used for both OCR and validation — quota planning matters).
- `jiwer` library installed.

---

## Tasks

### 1. Implement classical CER/WER scoring [Teammate]

- [ ] `src/validation/classical.py` exposing `compute_cer(reference: str, hypothesis: str) -> float` and `compute_wer(...)`
- [ ] Wrap `jiwer.cer` and `jiwer.wer` with NFC normalization on both inputs (defends against NFC/NFD drift between models)
- [ ] Edge cases: empty reference (return None or raise — decide and document), empty hypothesis (return 1.0)
- [ ] Unit tests in `src/validation/tests/test_classical.py`: identity returns 0.0, complete-corruption returns ~1.0, known small-edit case returns expected ratio

**Completion criterion:** Tests pass; metric matches `jiwer` directly on a hand-computed example.

### 2. Build the eval-subset scoring loop [Teammate]

- [ ] `src/validation/cli.py` exposing `python -m src.validation.cli --ocr <dir> --truth <dir> --metrics cer,wer --out <path>`
- [ ] Reads paired OCR output + ground-truth files, computes per-page CER + WER, writes a CSV with `page_id, model, preprocessing, cer, wer`
- [ ] Aggregate statistics: mean, median, p90 CER per (model, preprocessing) cell
- [ ] Integration test on a 2-page fixture

**Completion criterion:** CLI runs against the Phase 3 outputs; produces `data/processed/eval_subset/cer_wer.csv` with 180 rows (30 pages × 6 cells); summary stats printed.

### 3. Implement LLM fluency scoring (Method A) [Eric]

- [ ] `src/validation/llm_fluency.py` with `score_fluency(ocr_text: str, client) -> FluencyResult`
- [ ] Use Gemini Flash with the spec's prompt template (1-5 rating + reason + error examples)
- [ ] Parse the JSON response strictly; treat parse failure as a validation error (don't silently default to a score)
- [ ] Retry with exponential backoff on rate limits
- [ ] Unit tests with mocked responses; one `@pytest.mark.api` integration test

**Completion criterion:** Returns structured `FluencyResult` for a sample page; failures surface as exceptions, not silent zeros.

### 4. Implement cross-model agreement (Method B) [Eric]

- [ ] `src/validation/agreement.py` with `agreement_score(text_a: str, text_b: str) -> float` using `difflib.SequenceMatcher` per the spec
- [ ] Aggregate at the page level across the 3 Phase-3 models pairwise; output mean pairwise agreement per page
- [ ] No API calls (this is local) — fast and unmetered
- [ ] Unit tests: identical strings = 1.0, fully-disjoint = ~0.0, partial-overlap matches expected ratio

**Completion criterion:** Per-page agreement scores computed for the eval subset; cheap to scale to 100+ pages.

### 5. Calibrate LLM signals against CER [Eric]

- [ ] Notebook `notebooks/04_validation_calibration.ipynb`
- [ ] For each of the 30 eval-subset pages, plot (fluency score, CER) and (agreement score, CER)
- [ ] Compute Spearman + Pearson correlation; report
- [ ] Discuss: if fluency correlates with CER at r > 0.5, we can defend "LLM validation reflects true OCR quality"; if not, we discuss WHY in the report (this is honest analysis territory)

**Completion criterion:** Calibration plots saved to `reports/figures/validation/`; correlation values logged; analysis paragraph written for the final report.

### 6. Apply validation at scale [Eric]

- [ ] Run LLM fluency scoring on a 100+ page stratified sample drawn from the Phase 3 submission sample
- [ ] Run cross-model agreement on the same sample (requires both Gemini and Surya output for those pages — coordinate with Phase 3)
- [ ] Output to `data/processed/validation/scaled_validation.csv` with per-page scores
- [ ] Budget check: 100 pages × 1 Gemini fluency call each = 100 calls. Easy within free tier.

**Completion criterion:** 100+ page CSV with fluency + agreement scores; histogram of scores included in the report.

### 7. Tests + standards check [Eric]

- [ ] `pytest src/validation/tests/` — clean
- [ ] `ruff check src/validation/` — clean
- [ ] Confirm prompt designs are committed in source AND documented in the final report's methodology section

**Completion criterion:** Lint clean, tests green.

---

## Stretch (only if time allows)

- **Method C — LLM error detection and correction.** Spec's prompt template asks the LLM to flag likely OCR errors and suggest corrections. Useful, more expensive (longer prompts), and harder to evaluate quantitatively. Implement only if Methods A + B come in clean.
- **Method D — perplexity-based validation** using AI4Bharat's `indic-bert` or `MuRIL`. Strong rubric signal (the "advanced" spec method) but heavy dependency. Stretch unless someone gets excited about it.
- **Inter-rater reliability.** If teammate reads Telugu, manually score 10 pages on the same 1-5 scale and compare to the LLM. Strengthens the calibration story significantly.

---

## Open questions / decisions needed

1. **Which model for validation?** Gemini Flash is cheapest. Pro is better at language judgment but costlier. Recommendation: Flash, with a 10-page Pro spot-check to confirm Flash is good enough.
2. **What's the stratification for the 100+ page sample?** Same quality buckets from Phase 1. Recommendation: 25 pages per bucket × 4 buckets = 100 pages.
3. **How do we report the LLM scores in the report?** Per-page distributions, per-bucket means, per-model comparison. Pre-decide the plots before scaling so we don't re-run.
4. **What does "good calibration" mean for our 20-pt grade?** Suggesting: Spearman r > 0.4 between LLM fluency and CER is a defensible claim; > 0.6 is a strong claim. Below 0.4 we discuss honestly as a finding.

---

## Outputs / deliverables

- `src/validation/` — `classical.py`, `llm_fluency.py`, `agreement.py`, `cli.py`, tests.
- `data/processed/eval_subset/cer_wer.csv` — 30-page × 6-cell CER/WER table.
- `data/processed/validation/scaled_validation.csv` — 100+ page LLM scores.
- `notebooks/04_validation_calibration.ipynb` — calibration analysis.
- `reports/figures/validation/` — calibration plots and score distributions.

---

## Risks

- **LLM fluency and CER might not correlate.** This is a real research risk, not an engineering one. Mitigation: even a null result is publishable (in the report), AS LONG AS we report it honestly and discuss why. Don't fudge.
- **Gemini quota collision with Phase 3.** Phase 3 uses Gemini for OCR; Phase 4 uses Gemini for validation. Both eat the same daily 1500 RPD. Mitigation: schedule Phase 4 calls on different days, or use Surya OCR for Phase 3 submission-sample to free Gemini quota for validation.
- **JSON parse failures from Gemini.** LLMs occasionally return prose instead of JSON. Mitigation: strict parser + retry with a "respond in JSON only" reinforcement prompt; surface persistent failures as validation errors.
- **Cross-model agreement only meaningful with strong models.** Tesseract vs Gemini agreement reflects "Tesseract is bad," not "this page is hard." Mitigation: compute pairwise agreement among the strong models only (Gemini + Surya), exclude Tesseract from this metric.
