# Phase 2 — Image Preprocessing Pipeline

**Status:** Queued. Starts when Phase 1 evaluation subset is frozen.
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

## Tasks

### 1. Define the preprocessing interface [Eric]

- [ ] Create `src/preprocessing/pipeline.py` with a `PreprocessingStage` protocol or ABC: each stage takes a `numpy.ndarray` (image) and returns a `numpy.ndarray`
- [ ] Create a `Pipeline` class that composes stages and can be toggled (each stage on/off independently) — critical for the Phase 5 ablation
- [ ] Decide image representation convention: BGR uint8 (OpenCV) or RGB (PIL). Recommendation: BGR uint8 throughout, convert at I/O boundaries only.

**Completion criterion:** Interface defined; `pytest` import succeeds; one example test composing zero stages (identity pipeline) passes.

### 2. Implement deskew [Teammate]

- [ ] `src/preprocessing/deskew.py` with `deskew(image: np.ndarray) -> np.ndarray`
- [ ] Use the `deskew` library or Hough-line approach; fall back to identity if detected angle is below threshold (e.g., |angle| < 0.5°)
- [ ] Unit tests in `src/preprocessing/tests/test_deskew.py`: zero-skew identity, known-rotation correction within ±0.2°, all-white image safety

**Completion criterion:** Tests pass; deskew runs on all 30 eval pages without error; before/after visual spot-check on 3 known-skewed pages.

### 3. Implement binarization [Teammate]

- [ ] `src/preprocessing/binarize.py` with adaptive Gaussian thresholding (per the spec's `cv2.adaptiveThreshold` example)
- [ ] Expose block size and constant as parameters with sensible defaults
- [ ] Unit tests: pure-white returns white, pure-black returns black, gradient image binarizes to a balanced output

**Completion criterion:** Tests pass; binarized output is visibly clean on the eval subset.

### 4. Implement denoising and contrast enhancement [Eric]

- [ ] `src/preprocessing/denoise.py` using `cv2.fastNlMeansDenoising`
- [ ] `src/preprocessing/contrast.py` using `PIL.ImageEnhance.Contrast` or histogram equalization
- [ ] Unit tests for each: identity-preservation on already-clean input, no-crash on edge cases

**Completion criterion:** Tests pass; visual spot-check shows improvement on at least the "noisy" quality-bucket pages.

### 5. Wire up the composable pipeline [Eric]

- [ ] Default pipeline = deskew → binarize → denoise → contrast
- [ ] CLI entry point per [`../../README.md`](../../README.md): `python -m src.preprocessing.cli --input <dir> --output <dir>`
- [ ] Each stage independently toggleable via flag (e.g., `--no-denoise`) for the Phase 5 ablation
- [ ] Integration test at `tests/integration/test_preprocessing_pipeline.py` running the full pipeline on a fixture page

**Completion criterion:** CLI runs end-to-end on the eval subset; integration test passes.

### 6. Generate before/after visualizations [Teammate]

- [ ] Notebook `notebooks/02_preprocessing_visualizations.ipynb` producing side-by-side before/after images for 10 sample pages (pulled from the eval subset across quality buckets)
- [ ] Export PNGs to `reports/figures/preprocessing/` for the final report

**Completion criterion:** 10 before/after image pairs saved; notebook runs cleanly start-to-finish.

### 7. Tests + standards check [Eric]

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
