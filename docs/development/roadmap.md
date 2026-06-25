# Roadmap — Telugu OCR Project

**Status (2026-06-25):** ✅ Phases 0-5 all COMPLETE. Final deliverables: 31-page report at `reports/final_report.pdf`, presentation slides + script at `reports/presentation.qmd` / `reports/presentation_script.md`, 240-row eval matrix at `data/processed/eval_subset/cer_wer.csv`, 657-page Gemini submission sample at `data/processed/submission/gemini/`. See each phase doc's status header for per-phase deliverables. Pending today: presentation recording, submission directory packaging, final Drive share.
**Deadline:** 2026-06-25, 8 PM EST (per Announcement 4). Original spec said 2026-06-23 but the instructor extended via Announcement 4.
**Time budget:** ~2.5 weeks from kickoff. The instructor's published 6-week schedule did not apply — we compressed.
**Team:** Two-person (Eric + teammate). Branching per [`../standards/git_workflow_standard.md`](../standards/git_workflow_standard.md).

This roadmap adapts the instructor's 5-phase project structure (see [`../../downloads/Telugu-OCR-Project.qmd`](../../downloads/Telugu-OCR-Project.qmd)) to our compressed timeline. Each phase doc below carries the detail. The 100-point rubric weighting drives our scope choices: OCR Pipeline + Model Comparison (25 pts) and LLM Validation Framework (20 pts) receive the most engineering time; corpus characterization is heavily abbreviated because the HuggingFace corpus is pre-annotated.

---

## Teammate's first PR (start here)

**Branch:** `<your-initials>/01-corpus-stats`
**Goal:** Build `notebooks/01_corpus_characterization.ipynb` plus the headline `data/external/corpus_stats.json` artifact (Phase 1, Task 2).
**Why this is the right first task:** self-contained, mechanical, numerical (no English-prose burden), doesn't block Eric's parallel work on the quality taxonomy, and validates your full development setup end-to-end (env + dataset + git workflow).
**How to start:**
1. Read the [teammate onboarding doc](../guide/teammate_onboarding.md).
2. Run the setup steps in the root [`README.md`](../../README.md).
3. Open [`phase_1_corpus_characterization.md`](phase_1_corpus_characterization.md), Task 2.
4. Branch, work, open a PR.

Subsequent ownership is documented inline in each phase doc with `[Eric]`, `[Teammate]`, or `[Both]` tags.

---

## Ownership at a glance

| Phase | Eric owns | Teammate owns | Shared |
|-------|-----------|---------------|--------|
| 1 | Quality taxonomy, eval-subset selection, report prose | Corpus stats notebook, plots/tables | Inventory verification |
| 2 | Pipeline (delivered via engineer dispatch in PR #1: interface + deskew + binarize + pipeline + CLI + tests). Before/after visualization script — **reassigned from Rauf to Eric/PM on 2026-06-24 to keep Rauf on critical path** | _(none — see reassignment note)_ | — |
| 3 | OCR adapter interface, Gemini adapter + prompts, batch runner, submission sample | Tesseract adapter, Surya adapter (paired w/ Eric) | Comparison matrix execution |
| 4 | LLM fluency scoring, cross-model agreement, calibration, scaled validation | Classical CER/WER scoring, eval-subset scoring CLI | — |
| 5 | Final report prose, methodology disclosure, limitations | Error categorization tables/plots, figures and numerical sections for the report, slide visual content | Repo hygiene pass, presentation (50/50 by speaking time — scripted notes mitigate language asymmetry) |

The teammate's work is contained, well-bounded, and reviewable; Eric retains the prose, prompt-engineering, judgment, and presentation surface.

---

## Phase 0 — Repo Setup and Standards (COMPLETE)

Repository structure, standards docs, README, environment scaffolding, dataset download script, credential handling, and team workflow are in place. The teammate can clone, install, and run the test suite skeleton. This phase is the foundation everything else rests on; treating it as "done" means no further structural churn from this point forward.

- [x] Repo layout per [`../standards/repo_layout_standard.md`](../standards/repo_layout_standard.md)
- [x] Standards docs authored under `docs/standards/`
- [x] README + `.env.example` + dataset download script committed
- [x] Teammate onboarding doc in place
- [x] Roadmap + phase docs drafted (this commit)

---

## Phase 1 — Corpus Characterization (~2 days, compressed)

Profile the HuggingFace corpus enough to (a) justify our preprocessing choices in the final report and (b) pick the ~30-page ground-truth subset we will score CER/WER against. Because `AlbertoChestnut/telugu-ocr` ships paired `.jpg` + `.txt` we skip manual annotation entirely — the corpus IS the ground truth. We sample for quality variance rather than annotate from scratch. Details in [`phase_1_corpus_characterization.md`](phase_1_corpus_characterization.md).

- [x] Dataset downloaded locally and inventoried (5 books, 415 paired pages, 190 MB; CSV at `data/external/corpus_inventory.csv`)
- [ ] Corpus statistics computed (book/page counts, image dimensions, file sizes)
- [ ] Quality taxonomy defined (3-5 buckets: clean / faded / skewed / noisy / multi-column)
- [ ] Stratified 30-page evaluation subset selected and frozen
- [ ] Corpus characterization report drafted in `reports/corpus_characterization.qmd`

---

## Phase 2 — Preprocessing Pipeline (~2 days, parallel with Phase 3 start)

A modular preprocessing pipeline under `src/preprocessing/` covering deskew, binarization, denoising, and contrast — enough to demonstrate measurable OCR-accuracy improvement on the evaluation subset. Layout analysis and super-resolution are descoped to stretch goals. Each stage is independently testable and composable so the ablation study in Phase 5 is mechanical. Details in [`phase_2_preprocessing.md`](phase_2_preprocessing.md).

- [ ] `src/preprocessing/` module with deskew, binarize, denoise, contrast stages
- [ ] Composable pipeline runner (raw image → preprocessed image)
- [ ] Unit tests per stage; integration test on a sample page
- [ ] Before/after visualizations for 10 sample pages
- [ ] Quantitative ablation hook (preprocessing on vs off) wired for Phase 5

---

## Phase 3 — OCR Pipeline + Model Comparison (~3-4 days, highest leverage)

Build the OCR adapter layer under `src/ocr/` with a clean interface, then implement at least three adapters: Gemini Flash (cloud, free tier), Surya OCR (local), Tesseract (baseline). Run all three across the 30-page evaluation subset with and without preprocessing. This is the 25-point dimension on the rubric and gets the most rigorous engineering. Details in [`phase_3_ocr_pipeline.md`](phase_3_ocr_pipeline.md).

- [ ] Adapter interface defined; Gemini + Surya + Tesseract implementations
- [ ] Robust batching with rate-limit handling and Unicode NFC normalization
- [ ] CER/WER computed for each (model × preprocessing-on/off) cell on the eval subset
- [ ] OCR output captured to `data/processed/` for the 500+ page submission sample
- [ ] Model comparison table + per-page results persisted as artifacts for Phase 5

---

## Phase 4 — LLM Validation Framework (~2-3 days, second-highest leverage)

Implement at least two LLM-based validation methods (fluency scoring + cross-model agreement) under `src/validation/`, calibrate them against the Phase 3 CER/WER ground truth, and scale to a 100+ page stratified sample. The calibration story — showing the LLM scores correlate with real CER — is what moves this from 14-17 pts to 18-20 pts on the rubric. Details in [`phase_4_llm_validation.md`](phase_4_llm_validation.md).

- [ ] `src/validation/` with CER/WER (jiwer wrapper) + two LLM-based methods
- [ ] Calibration analysis: LLM scores vs CER on the eval subset (correlation reported)
- [ ] LLM validation applied to 100+ page stratified sample
- [ ] Prompt designs documented in code and in the report
- [ ] Validation outputs persisted as artifacts for Phase 5

---

## Phase 5 — Analysis, Final Report, Presentation (~3 days)

Synthesize the artifacts from Phases 1-4 into the 15+ page Quarto final report at `reports/final_report.qmd`, build the 15-minute presentation, and finalize the 500+ page processed corpus sample for submission. Error categorization, preprocessing-impact quantification, and scalability cost estimates are the load-bearing content. Details in [`phase_5_analysis_report.md`](phase_5_analysis_report.md).

- [ ] Final report rendered (HTML + PDF), 15+ pages excluding code/figures
- [ ] Error categorization (substitution / diacritic / hallucination / conjunct) completed
- [ ] Preprocessing-impact quantification + scalability cost estimate included
- [ ] 15-minute slide deck and live-demo script ready
- [ ] 500+ page processed corpus sample finalized in `data/processed/`
- [ ] Submission packaged: GitHub repo + report + presentation + corpus sample
