# Notebooks

Jupyter notebooks for exploration, prototyping, and analysis that benefits from narrative + inline outputs.

**Notebooks call into `src/`** for any non-trivial logic — they do not hold the core pipeline implementation. When a notebook accumulates real reusable logic, extract it to `src/` and have the notebook import it.

## Naming

`NN_short_topic.ipynb` — two-digit prefix for ordering, snake_case description.

Examples:
- `01_corpus_characterization.ipynb` — initial exploration of the Telugu dataset (Phase 1)
- `02_preprocessing_experiments.ipynb` — visual before/after comparisons of preprocessing stages
- `03_ocr_model_comparison.ipynb` — side-by-side OCR outputs from each model
- `04_cer_wer_analysis.ipynb` — distribution of error rates across pages and models
- `05_llm_validation_calibration.ipynb` — comparing LLM quality scores against CER/WER

## Discipline

- Commit clean notebooks. Clear outputs of cells that print large datasets or that include API responses with sensitive content before commit. `nbstripout` is one option.
- Notebooks are reviewed in PRs like code. The rendered output should still tell a coherent story without re-running.
- If a notebook starts feeling like an application, it belongs in `src/` with a thin notebook on top for narration.
