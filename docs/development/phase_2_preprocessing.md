# Phase 2 — Image Preprocessing Pipeline

**Status (2026-06-25): ✅ COMPLETE (all 4 originally-planned stages shipped).** Deliverables: `src/preprocessing/pipeline.py` (composable per-stage enable/disable), all four stages — deskew, adaptive-binarize, NL-means denoise, CLAHE contrast — at `src/preprocessing/{deskew,binarize,denoise,contrast}.py`, `scripts/run_preprocessing.py` CLI with per-stage flags, 32+ unit/integration tests, before/after visualization PNGs at `reports/figures/preprocessing/`, ablation figure at `reports/figures/results/preprocessing_ablation.png`. **Empirical finding documented in final report Section 6.3:** binarize is universally destructive across all 4 OCR systems tested (Tesseract hurt MOST, +21pp CER); the other three stages are model-dependent — Sonnet + Tesseract benefit from grayscale-soft (deskew+denoise+contrast); Gemini Flash does not. **History:** stages 1-2 shipped in the original Phase 2 (commit 9e8f5e2); stages 3-4 were originally deferred for time and added in Phase 5 (commit c4853f8) to support the per-stage ablation when the eval matrix data made it worth running.
**Time estimate:** 2 days. Overlaps with the first day of Phase 3 (one teammate per phase).
**Rubric dimension:** Dimension 2 — Preprocessing Pipeline (15 pts).

---

## Goal

Build a modular, testable preprocessing pipeline under `src/preprocessing/` that demonstrably improves OCR accuracy on the Phase 1 evaluation subset. Each stage (deskew, binarize, denoise, contrast) is an independent function; the pipeline composes them. The composability is what makes the Phase 5 ablation study mechanical rather than ad-hoc.

The instructor's spec lists six preprocessing stages including super-resolution and layout analysis. We implement four (deskew + binarize + denoise + contrast). Super-resolution and full layout analysis are stretch goals — covered below.

---

## Dependencies

- Phase 1 evaluation subset frozen at `data/external/eval_subset/` (30 paired images + ground truth).
- Python environment with `opencv-python`, `Pillow`, `scikit-image`, `deskew`, `numpy` installed (per `requirements.txt`).

---

## Scope note (post-time-pressure trim)

The spec asks for four preprocessing stages (deskew + binarize + denoise + contrast). With four working days to ship the whole project, we cut Phase 2 to **deskew + binarize only**. Denoise + contrast become stretch goals if Phase 3/4 finish ahead of schedule.

We also dispatch an autonomous build workflow ("the Phase 2 engineer") to implement Tasks 1, 2, 3, and 5 (interface, deskew, binarize, pipeline + CLI) in one PR. Eric reviews the PR; Rauf reviews to learn the codebase pattern. Task 6 (before/after visualization notebook) stays with Rauf as a hands-on deliverable. Tasks 4 and 7 are reframed accordingly below.

---

## Tasks

### 1. Define the preprocessing interface [Engineer dispatch — Eric reviews]

- [ ] Create `src/preprocessing/pipeline.py` with a `PreprocessingStage` protocol or ABC: each stage takes a `numpy.ndarray` (image) and returns a `numpy.ndarray`
- [ ] Create a `Pipeline` class that composes stages and can be toggled (each stage on/off independently) — critical for the Phase 5 ablation
- [ ] Decide image representation convention: BGR uint8 (OpenCV) or RGB (PIL). Recommendation: BGR uint8 throughout, convert at I/O boundaries only.

**Completion criterion:** Interface defined; `pytest` import succeeds; one example test composing zero stages (identity pipeline) passes.

### 2. Implement deskew [Engineer dispatch — Eric reviews, Rauf reviews to learn]

- [ ] `src/preprocessing/deskew.py` with `deskew(image: np.ndarray) -> np.ndarray`
- [ ] Use the `deskew` library or Hough-line approach; fall back to identity if detected angle is below threshold (e.g., |angle| < 0.5°)
- [ ] Unit tests in `src/preprocessing/tests/test_deskew.py`: zero-skew identity, known-rotation correction within ±0.2°, all-white image safety

**Completion criterion:** Tests pass; deskew runs on all 30 eval pages without error; before/after visual spot-check on 3 known-skewed pages.

### 3. Implement binarization [Engineer dispatch — Eric reviews, Rauf reviews to learn]

- [ ] `src/preprocessing/binarize.py` with adaptive Gaussian thresholding (per the spec's `cv2.adaptiveThreshold` example)
- [ ] Expose block size and constant as parameters with sensible defaults
- [ ] Unit tests: pure-white returns white, pure-black returns black, gradient image binarizes to a balanced output

**Completion criterion:** Tests pass; binarized output is visibly clean on the eval subset.

### 4. Implement denoising and contrast enhancement [Stretch — only if Phase 3 finishes ahead of schedule]

- [ ] `src/preprocessing/denoise.py` using `cv2.fastNlMeansDenoising`
- [ ] `src/preprocessing/contrast.py` using `PIL.ImageEnhance.Contrast` or histogram equalization
- [ ] Unit tests for each: identity-preservation on already-clean input, no-crash on edge cases

**Completion criterion:** Tests pass; visual spot-check shows improvement on at least the "noisy" quality-bucket pages.

**Status:** Deferred to stretch per the scope note above. Only attempt if we are on or ahead of schedule by Wednesday.

### 5. Wire up the composable pipeline [Engineer dispatch — Eric reviews]

- [ ] Default pipeline = deskew → binarize → denoise → contrast
- [ ] CLI entry point per [`../../README.md`](../../README.md): `python -m src.preprocessing.cli --input <dir> --output <dir>`
- [ ] Each stage independently toggleable via flag (e.g., `--no-denoise`) for the Phase 5 ablation
- [ ] Integration test at `tests/integration/test_preprocessing_pipeline.py` running the full pipeline on a fixture page

**Completion criterion:** CLI runs end-to-end on the eval subset; integration test passes.

### 6. Generate before/after visualizations [Eric/PM — REASSIGNED from Rauf]

**Reassignment note (2026-06-24):** Originally Rauf's task. Reassigned to keep Rauf focused on the critical path (Phase 1 Task 2 → Phase 4 Tasks 1+2 → Phase 5 Task 1). With limited working time remaining, the visualization was the lowest-leverage item on his plate. Replaced with a smaller, scripted version below.

- [x] Script (or quick notebook): pick 3-5 pages from the eval subset spanning the most-affected buckets (Clean baseline, Skewed → deskew-helps, Faded → binarize-helps), run them through `Pipeline([("deskew", deskew, True), ("binarize", binarize, True)])`, save side-by-side PNGs
- [x] Export PNGs to `reports/figures/preprocessing/` for embedding in the final report (4 PNGs: Clean, Skewed, Faded, Damaged buckets)

**Completion criterion:** 3-5 before/after PNGs at `reports/figures/preprocessing/`. Each shows raw vs preprocessed at 150 DPI with a title.

**Scope trim from the original spec:** dropped from 10 visualizations to 3-5 to fit the timeline; dropped the full Jupyter notebook in favor of a script because we are not using the task as a teaching artifact anymore. The qualitative visuals complement (not substitute for) the quantitative CER deltas that Phase 4 produces, which carry the bulk of the Dimension 2 rubric points.

**When to do this:** Just before drafting the final report's Preprocessing Methods section in Phase 5. No reason to land it earlier — the pipeline is merged on `main`, and the eval subset is frozen.

#### Walk-through for Rauf

**Why this task matters.** The 15 points for Phase 2 (Preprocessing) on the rubric are partly about "did you build the pipeline" and partly about "did you demonstrate it improves things." Quantitative proof comes in Phase 5 (CER drops by X% with preprocessing on). Visual proof — the side-by-side images you produce here — is what convinces a human reader at a glance that the pipeline is doing something useful. These images go directly into the final report.

**What you will produce.**
- One Jupyter notebook at `notebooks/02_preprocessing_visualizations.ipynb`.
- Ten PNG files under `reports/figures/preprocessing/`, named like `book_alpha_page_0001.png`, each showing the raw image and the preprocessed image side-by-side with a title.

**When you can start.** This task needs three things to be done first:
1. The engineer's Phase 2 PR is merged (deskew + binarize + pipeline are in `src/preprocessing/`).
2. Eric's Phase 1 Task 3 (quality taxonomy) defines the buckets you sample from.
3. Eric's Phase 1 Task 4 (eval subset) gives you the 30 specific pages.

Until then, do not start. Eric will ping you when it is your turn.

**How to start.** First cell — imports and pick which pages to visualize:

```python
import pandas as pd
import matplotlib.pyplot as plt
import cv2
from pathlib import Path

from src.preprocessing import Pipeline, binarize, deskew

REPO_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
FIG_DIR = REPO_ROOT / "reports" / "figures" / "preprocessing"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Eric will tell you which page IDs to use, ideally 2 from each of the
# 4-5 quality buckets so the report covers the full quality range.
sample_page_ids = [
    # Eric fills these in once the taxonomy and eval subset are ready
]

eval_subset = pd.read_csv(REPO_ROOT / "data" / "external" / "eval_subset.csv")
to_show = eval_subset[eval_subset["page_id"].isin(sample_page_ids)]
```

**Render side-by-side, save, repeat.** A small helper makes this clean:

```python
def render_before_after(image_path: Path, pipeline: Pipeline, title: str, out_path: Path):
    raw = cv2.imread(str(image_path))               # OpenCV reads BGR uint8
    preprocessed = pipeline.run(raw)

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    axes[0].imshow(cv2.cvtColor(raw, cv2.COLOR_BGR2RGB))
    axes[0].set_title("Raw scan")
    axes[0].axis("off")
    axes[1].imshow(preprocessed, cmap="gray")        # binarize output is single-channel
    axes[1].set_title("After preprocessing")
    axes[1].axis("off")
    fig.suptitle(title)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.show()

pipeline = Pipeline([("deskew", deskew, True), ("binarize", binarize, True)])

for _, row in to_show.iterrows():
    image_path = REPO_ROOT / row["image_path"]
    out_path = FIG_DIR / f"{row['book_id']}_{row['page_id']}.png"
    render_before_after(image_path, pipeline, f"{row['book_id']} / {row['page_id']}", out_path)
```

**What good looks like.**
- 10 PNGs under `reports/figures/preprocessing/`, one per sampled page.
- Each PNG is a clean side-by-side with "Raw scan" and "After preprocessing" titles.
- The "after" side visibly shows deskew (text lines are horizontal) and binarization (clean black-on-white).
- Notebook runs top-to-bottom without errors after a kernel restart.
- A short markdown cell at the end summarises what you observed across the 10 pages — for example, *"Deskew is most visible on book_alpha pages, which were scanned at a slight tilt. Binarization removes the slight cream color from the older scans."*

**Common pitfalls.**
- **OpenCV color order:** `cv2.imread` returns BGR; matplotlib expects RGB. Use `cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)` for display.
- **Binary images are single-channel:** matplotlib will refuse to show them in colour. Pass `cmap="gray"` when calling `imshow` on the binarized output.
- **Cell ordering:** restart the kernel and run all cells top-to-bottom before committing.
- **Don't tune the pipeline here:** if a result looks bad, do NOT change pipeline parameters in this notebook. Open a draft PR and ping Eric — pipeline tuning belongs in `src/preprocessing/`, not in a notebook.

**Open a draft PR early.** Open it as soon as one before/after pair renders. Eric can spot-check that the pipeline output looks right before you grind through all ten.

### 7. Tests + standards check [Eric + Engineer dispatch]

- [ ] Run `pytest -m "not slow and not api"` — all green
- [ ] Run `ruff check src/preprocessing/` — clean
- [ ] Confirm test placement matches [`../standards/testing_standard.md`](../standards/testing_standard.md)

**Completion criterion:** Lint clean, tests green.

---

## Stretch (only if Phase 3 finishes ahead of schedule)

- **Layout analysis** with LayoutParser or pytesseract `image_to_data`. Adds rubric points on Dimension 2 if multi-column pages are common in the eval subset. Risk: heavy dependency, may not generalize.
- **Super-resolution** for low-DPI scans via OpenCV `INTER_CUBIC` (lightweight) or RealESRGAN (heavy). Lightweight version is ~30 min of work; only worth doing if Phase 1 finds many low-resolution pages.
- **Border crop / margin removal.** Useful if the corpus has scanner-edge artifacts.

---

## Open questions / decisions needed

1. **Default parameter values.** Adaptive threshold block size (11), denoising strength (h=10) — defaults from the spec. Do we tune per quality bucket or leave global? Recommendation: global defaults for v1, tune in Phase 5 only if results justify it.
2. **What order do stages run?** Spec order is deskew → binarize → denoise → contrast. But contrast on binarized output is a no-op. Consider contrast → deskew → binarize → denoise. Decision needed before task 5.
3. **Do we cache preprocessed images to disk?** Reprocessing 30 pages is fast; reprocessing 500+ is not. Recommendation: cache to `data/interim/<book_id>/preprocessed/` keyed by pipeline config hash.

---

## Outputs / deliverables

- `src/preprocessing/` — module with deskew, binarize, denoise, contrast, pipeline, CLI.
- `src/preprocessing/tests/` — unit tests.
- `tests/integration/test_preprocessing_pipeline.py` — integration test.
- `data/interim/<book_id>/preprocessed/` — preprocessed eval-subset pages.
- `notebooks/02_preprocessing_visualizations.ipynb` — narrative notebook.
- `reports/figures/preprocessing/` — before/after PNGs for the report.

---

## Risks

- **Binarization tanks Gemini accuracy.** Vision LLMs are sometimes trained on grayscale or color and degrade on hard binary. Mitigation: keep an unbinarized branch in the pipeline; Phase 5 ablation will tell us which is better per model.
- **Deskew library produces wrong angles on dense Telugu text.** Telugu lines are visually denser than Latin and the `deskew` library may miscalibrate. Mitigation: spot-check 5 pages after first deskew run; switch to Hough-based if needed.
- **Stretch creep.** Spec lists six stages; we promise four. If a teammate over-implements, time bleeds from Phase 3 (higher leverage). Mitigation: enforce phase doc as the scope contract.
