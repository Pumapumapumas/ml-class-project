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

## Scope note (post-time-pressure trim)

- **Tasks 1 and 2** stay with Rauf — they are well-defined, mechanical, and a great use of his pandas skills.
- **Tasks 3-6** stay with Eric. Task 4 (cross-model agreement) is somewhat weakened by the Phase 3 Surya cut — with only Gemini and Tesseract in the comparison, "agreement" between a strong model and a weak baseline is more about page difficulty than about per-page OCR accuracy. We still implement it because the rubric rewards two LLM methods.

---

## Tasks

### 1. Implement classical CER/WER scoring [Teammate]

- [ ] `src/validation/classical.py` exposing `compute_cer(reference: str, hypothesis: str) -> float` and `compute_wer(...)`
- [ ] Wrap `jiwer.cer` and `jiwer.wer` with NFC normalization on both inputs (defends against NFC/NFD drift between models)
- [ ] Edge cases: empty reference (return None or raise — decide and document), empty hypothesis (return 1.0)
- [ ] Unit tests in `src/validation/tests/test_classical.py`: identity returns 0.0, complete-corruption returns ~1.0, known small-edit case returns expected ratio

**Completion criterion:** Tests pass; metric matches `jiwer` directly on a hand-computed example.

#### Walk-through for Rauf

**Why this task matters.** CER (Character Error Rate) and WER (Word Error Rate) are THE standard OCR accuracy metrics. They turn "the model output looks close to the truth" into a number you can compare across models and pages. Phase 4's 20 rubric points rest on having these numbers honestly and consistently computed. This task is the foundation everything else in Phase 4 builds on.

**What you will produce.** A single Python file at `src/validation/classical.py` with two pure functions plus tests. No CLI here — Task 2 is the CLI; this task is just the math.

**When you can start.** Right after the Phase 3 OCR engineer dispatch merges (you need an example OCR output to test against), OR you can start now using any pair of strings as fixtures. The functions do not depend on the OCR pipeline — they just take two strings.

**Background — what these metrics actually measure.**

- **CER** = `(substitutions + deletions + insertions) / total_reference_characters`. So 0.05 CER means "5% of characters had to change to make the OCR match the truth." Lower is better. Identity (reference == hypothesis) gives 0.0. Total corruption gives ~1.0.
- **WER** = same idea, but counting whole words. A single wrong character can make an entire word wrong, so WER is usually higher than CER. For Telugu specifically, "word" tokenization is a bit ambiguous — `jiwer` handles it for us.
- The `jiwer` library implements both, well-tested. We do NOT reimplement the math — we just wrap it with NFC normalization so the inputs do not differ in Unicode form.

**Starter skeleton.**

```python
"""Classical OCR accuracy metrics — CER and WER.

Wraps the jiwer library with Unicode NFC normalization applied to both
inputs so Unicode form mismatches do not artificially inflate error
rates. NFC normalization is a no-op when the input is already in NFC,
which is what our dataset and OCR adapters produce.
"""

from __future__ import annotations

import unicodedata

from jiwer import cer, wer


def _nfc(text: str) -> str:
    """Normalize to Unicode NFC; safe to call on already-NFC text."""
    return unicodedata.normalize("NFC", text)


def compute_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate. Empty reference raises ValueError."""
    if not reference:
        raise ValueError("reference must be non-empty to compute CER")
    if not hypothesis:
        return 1.0
    return cer(_nfc(reference), _nfc(hypothesis))


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate. Empty reference raises ValueError."""
    if not reference:
        raise ValueError("reference must be non-empty to compute WER")
    if not hypothesis:
        return 1.0
    return wer(_nfc(reference), _nfc(hypothesis))
```

**Tests** — follow the corpus inventory test pattern. Each test is a few lines:

```python
import pytest
from src.validation.classical import compute_cer, compute_wer


class TestComputeCER:
    def test_identity_returns_zero(self):
        assert compute_cer("hello", "hello") == 0.0

    def test_complete_corruption(self):
        assert compute_cer("hello", "xyzqr") == 1.0

    def test_single_substitution(self):
        # 1 char out of 5 changed
        assert compute_cer("hello", "hellp") == pytest.approx(0.2)

    def test_empty_hypothesis_returns_one(self):
        assert compute_cer("hello", "") == 1.0

    def test_empty_reference_raises(self):
        with pytest.raises(ValueError):
            compute_cer("", "hello")

    def test_nfc_normalization_handled(self):
        # Same string, different Unicode form — should score as identity
        nfc = "café"             # NFC: 4 codepoints
        nfd = "café"        # NFD: 5 codepoints
        assert compute_cer(nfc, nfd) == 0.0
```

Add similar tests for `compute_wer`.

**What good looks like.**
- Two public functions, fully type-hinted, with Google-style docstrings.
- A test file with at least 5-6 tests covering identity, total corruption, single substitution, empty inputs, and NFC normalization.
- `ruff check src/validation/` clean.
- `pytest src/validation/tests/` green.

**Common pitfalls.**
- **Empty-reference division by zero.** `jiwer` raises on this — we wrap with `ValueError` and a clear message rather than letting `jiwer`'s error propagate. Document the choice in the docstring.
- **Whitespace differences.** Some OCR outputs have trailing newlines. `jiwer` handles whitespace OK by default but if you see weird scores on an obvious match, check for trailing `\n`.
- **Type hints on jiwer.** `jiwer.cer` returns `float` but old versions returned `np.float64` — both are fine to return, but if your test does `== 0.0` exactly, prefer `pytest.approx`.

**Open a draft PR early.** Once the two functions exist and ONE test passes, open it as draft. Eric can sanity-check the API before you grind through all the test cases.

### 2. Build the eval-subset scoring loop [Teammate]

- [ ] `src/validation/cli.py` exposing `python -m src.validation.cli --ocr <dir> --truth <dir> --metrics cer,wer --out <path>`
- [ ] Reads paired OCR output + ground-truth files, computes per-page CER + WER, writes a CSV with `page_id, model, preprocessing, cer, wer`
- [ ] Aggregate statistics: mean, median, p90 CER per (model, preprocessing) cell
- [ ] Integration test on a 2-page fixture

**Completion criterion:** CLI runs against the Phase 3 outputs; produces `data/processed/eval_subset/cer_wer.csv` with 120 rows (30 pages × 4 cells, after the Surya cut: 2 models × 2 preprocessing); summary stats printed.

#### Walk-through for Rauf

**Why this task matters.** Task 1 gave us the CER/WER math for one pair of strings. Task 2 makes it useful: it walks through every OCR output we have, pairs it with the ground truth, computes the metrics, and writes one row per (page, model, preprocessing). That CSV is what feeds Phase 5's analysis and the figures in the final report.

**What you will produce.** A CLI at `scripts/score_ocr.py` (or `src/validation/cli.py`, follow whatever pattern the engineer establishes in Task 5 of Phase 3 — same as `scripts/build_corpus_inventory.py` was for Phase 1).

**When you can start.** After the Phase 3 batch runner has produced output for at least one (model, preprocessing) cell. Eric will tell you when.

**Background — the input.** The Phase 3 batch runner writes:

```
data/processed/eval_subset/
├── gemini_raw/
│   ├── 2015.328360.Andhra-Mahaniyulu/page_0010.txt
│   ├── 2015.328360.Andhra-Mahaniyulu/page_0011.txt
│   └── ... (one OCR output per page)
├── gemini_preprocessed/
├── tesseract_raw/
└── tesseract_preprocessed/
```

And the ground truth is at `data/raw/telugu-ocr/<book_id>/<page>.txt`. Your job: for each OCR output file, find the matching ground-truth file, compute CER and WER, write a row to the CSV.

**Starter skeleton.**

```python
"""Score OCR outputs against ground truth.

Walks data/processed/eval_subset/<model>_<preprocessing>/ and pairs each
OCR output with its matching ground-truth file under data/raw/telugu-ocr/.
Computes CER and WER per page; writes a long-format CSV that downstream
analysis can pivot or filter.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.validation.classical import compute_cer, compute_wer

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("score_ocr")


def score_cell(ocr_dir: Path, truth_root: Path) -> list[dict]:
    """Score every OCR output in ocr_dir against its truth pair."""
    model, preprocessing = ocr_dir.name.split("_", 1)
    rows = []
    for ocr_txt in sorted(ocr_dir.rglob("*.txt")):
        book_id = ocr_txt.parent.name
        page_id = ocr_txt.stem
        truth_txt = truth_root / book_id / f"{page_id}.txt"
        if not truth_txt.exists():
            LOG.warning("No truth for %s/%s", book_id, page_id)
            continue
        try:
            cer_val = compute_cer(truth_txt.read_text(encoding="utf-8"),
                                  ocr_txt.read_text(encoding="utf-8"))
            wer_val = compute_wer(truth_txt.read_text(encoding="utf-8"),
                                  ocr_txt.read_text(encoding="utf-8"))
        except ValueError as exc:
            LOG.error("Score failed on %s/%s: %s", book_id, page_id, exc)
            continue
        rows.append({
            "book_id": book_id,
            "page_id": page_id,
            "model": model,
            "preprocessing": preprocessing,
            "cer": cer_val,
            "wer": wer_val,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr-root", type=Path,
                        default=REPO_ROOT / "data" / "processed" / "eval_subset")
    parser.add_argument("--truth-root", type=Path,
                        default=REPO_ROOT / "data" / "raw" / "telugu-ocr")
    parser.add_argument("--out", type=Path,
                        default=REPO_ROOT / "data" / "processed" / "eval_subset" / "cer_wer.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

    all_rows = []
    for cell_dir in sorted(args.ocr_root.iterdir()):
        if not cell_dir.is_dir():
            continue
        LOG.info("Scoring %s", cell_dir.name)
        all_rows.extend(score_cell(cell_dir, args.truth_root))

    df = pd.DataFrame(all_rows)
    df.to_csv(args.out, index=False)
    LOG.info("Wrote %d rows to %s", len(df), args.out)

    # Aggregate summary
    summary = df.groupby(["model", "preprocessing"])["cer"].agg(["mean", "median",
                                                                   lambda s: s.quantile(0.9)])
    summary.columns = ["mean", "median", "p90"]
    LOG.info("\n%s", summary.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**What good looks like.**
- CLI runs end-to-end and produces a CSV with columns `book_id, page_id, model, preprocessing, cer, wer`.
- Per-(model, preprocessing) summary printed at the end (mean, median, p90 CER).
- A small integration test under `tests/integration/` that builds a 2-page fixture and asserts the output CSV has 2 rows with sensible values.
- `ruff check` clean.

**Common pitfalls.**
- **Path mismatch.** OCR outputs may not exactly mirror `data/raw/` layout — be defensive about missing truth files. Log + skip, don't crash.
- **Encoding.** Read files with `encoding="utf-8"`. Telugu in any other encoding will silently corrupt.
- **Empty pages.** A truly blank page will have empty `.txt` truth — `compute_cer` will raise `ValueError`. Catch + log + skip per the starter code.

**Open a draft PR early.** Once the CLI prints summary numbers for ONE model cell, draft-PR it. The aggregation logic is the easy part; getting the file pairing right is the load-bearing piece Eric should sanity-check first.

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
