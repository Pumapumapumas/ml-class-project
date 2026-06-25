# Multilingual OCR for Telugu Text Using Large Language Models

End-to-end pipeline that extracts clean Unicode text from scanned Telugu document images using vision-capable Large Language Models, with an accompanying validation framework that uses LLMs to assess OCR quality both with and without ground-truth references.

Course project for **CSCI/DASC 6020 — Machine Learning, Summer 2026**, East Carolina University.

---

## What this project does

1. Ingests scanned Telugu page images (`.jpg` / `.png`)
2. Preprocesses them: deskew + adaptive-threshold binarization
3. Runs each page through **four OCR systems** (Tesseract 5 classical baseline, Gemini Flash 2.5, Claude Sonnet 4.6, Claude Opus 4.8) and captures the Unicode text output
4. Evaluates accuracy on a 30-page stratified eval subset using Character Error Rate (CER) and Word Error Rate (WER) → a 240-row matrix at `data/processed/eval_subset/cer_wer.csv`
5. Validates OCR quality without ground truth via **LLM fluency scoring** and **cross-model agreement** — calibrated against CER on the eval subset; cross-model agreement turns out to be the stronger signal (Spearman ρ = -0.586 vs -0.445)
6. Produces a **31-page Quarto report** ([`reports/final_report.qmd`](reports/final_report.qmd)) covering methodology, three publishable findings, error analysis, iteration narrative, and limitations
7. Produces a **415-page submission sample** of Gemini OCR over the full 5-book corpus at `data/processed/submission/gemini/`

**Three headline findings from the empirical comparison:**

- **Preprocessing hurt every OCR system**, including the classical Tesseract baseline (+21pp CER), because adaptive binarization stripped grayscale gradient information all modern OCR depends on.
- **Claude Sonnet 4.6 is the cost-quality sweet spot.** Opus 4.8 is only ~1 percentage point better mean CER at 7× the cost.
- **A 30-year-old classical OCR baseline (Tesseract) beats Google's flagship vision LLM (Gemini Flash) by 18pp on Telugu** — vision LLMs are not automatically superior for low-resource scripts.

Full project specification is in [`downloads/Telugu-OCR-Project.qmd`](downloads/Telugu-OCR-Project.qmd). The instructor's submission deadline announcements are in [`downloads/announcement4.md`](downloads/announcement4.md) and [`announcement5.md`](downloads/announcement5.md).

---

## Repository structure

```
ml-class-project/
├── docs/
│   ├── standards/      ← How we work (see docs/standards/README.md)
│   ├── development/    ← Roadmap, phase plans, loose ends
│   └── guide/          ← Pointer to this README for project scope
├── downloads/          ← Project spec, instructor announcements, dataset notes
├── src/                ← Pipeline source code (Python package)
├── notebooks/          ← Jupyter exploration and analysis
├── tests/              ← Integration / e2e tests (unit tests live in src/<component>/tests/)
├── scripts/            ← Environment setup, dataset download, utilities
├── data/               ← Input corpus (gitignored, see data/README.md)
├── reports/            ← Quarto source for the final report and renderings
└── logs/               ← Pipeline run logs (gitignored)
```

Detailed layout rules: [`docs/standards/repo_layout_standard.md`](docs/standards/repo_layout_standard.md).

---

## Quickstart

### Prerequisites

- Linux or macOS (Windows via WSL2)
- Python 3.11+
- Git
- ~30 GB free disk for the corpus
- API access for at least one OCR model (Google Gemini free tier recommended)

### Setup

```bash
# 1. Clone
git clone git@github.com:Pumapumapumas/ml-class-project.git
cd ml-class-project

# 2. Bootstrap the environment (creates the venv, installs deps, builds the
#    Tesseract Docker image, sets up project-local caches)
scripts/setup_env.sh

# 3. Activate the venv
source .venv/bin/activate

# 4. Configure credentials (see "API keys" below)
cp .env.example .env
# Open .env in any editor and fill in your keys, then save.

# 5. Download the corpus subset
python scripts/download_dataset.py --subset 5
# Downloads ~5 books (~500 MB) for development. See script --help for full corpus.
```

The bootstrap script does the heavy lifting so the workstation stays clean — no `sudo apt install`, no `sudo pip install`. See [`docs/standards/environment_standard.md`](docs/standards/environment_standard.md) for the design.

### API keys

The pipeline calls vision-capable LLMs to perform OCR on Telugu page images. Each provider requires a free account and an API key. **You only need Gemini at a minimum** — the rest are optional and only needed if you want to compare additional models.

| Service | What it's used for | Required? | How to get a key | Cost |
|---------|-------------------|-----------|------------------|------|
| **Google Gemini** | OCR (Gemini Flash 2.5) + 415-page submission sample | **Yes** | https://aistudio.google.com/app/apikey | Free-tier sufficient for the eval matrix; paid recommended for the 415-page submission run (~$0.30 total) |
| **Anthropic Claude** | OCR (Sonnet 4.6 + Opus 4.8) + LLM fluency-scoring judge | **Yes** | https://console.anthropic.com/ | Pay-as-you-go; total project spend ~$9 across 120 eval calls |
| HuggingFace | Downloading the dataset | No (dataset is public) | https://huggingface.co/settings/tokens | Free |

**Get a Gemini key in 3 steps:**

1. Sign in to https://aistudio.google.com/app/apikey with a Google account
2. Click "Create API key" (no payment info required for the free tier)
3. Copy the key into your `.env` file:
   ```
   GEMINI_API_KEY=AIza...your-key-here...
   ```

**Important:** never commit `.env`. It is gitignored. The full credential policy is in [`docs/standards/credential_handling_standard.md`](docs/standards/credential_handling_standard.md). Read that doc before adding any new key or service.

### Reproduce the eval matrix

```bash
# 1. Inventory + freeze the eval subset (idempotent; reads from data/raw/)
python scripts/build_corpus_inventory.py
python scripts/select_eval_subset.py

# 2. Build the preprocessed images (deskew + binarize) — outputs to data/interim/
python scripts/run_preprocessing.py --input data/external/eval_subset --output data/interim/eval_subset_preprocessed

# 3. Run each OCR cell (idempotent; skips pages already done)
python scripts/run_ocr.py --model gemini    --input data/external/eval_subset           --output data/processed/eval_subset/gemini_raw
python scripts/run_ocr.py --model gemini    --input data/interim/eval_subset_preprocessed --output data/processed/eval_subset/gemini_preprocessed
python scripts/run_ocr.py --model claude    --input data/external/eval_subset           --output data/processed/eval_subset/claude_raw
python scripts/run_ocr.py --model claude    --input data/interim/eval_subset_preprocessed --output data/processed/eval_subset/claude_preprocessed
python scripts/run_ocr.py --model tesseract --input data/external/eval_subset           --output data/processed/eval_subset/tesseract_raw
python scripts/run_ocr.py --model tesseract --input data/interim/eval_subset_preprocessed --output data/processed/eval_subset/tesseract_preprocessed

# 4. Score CER/WER across all cells -> data/processed/eval_subset/cer_wer.csv
python scripts/score_ocr.py

# 5. Run LLM fluency scoring on the eval matrix -> fluency.csv
python scripts/run_fluency.py --ocr-root data/processed/eval_subset --out data/processed/eval_subset/fluency.csv

# 6. Calibrate fluency + cross-model agreement against CER -> reports/figures/calibration/
python notebooks/04_validation_calibration.py

# 7. Per-cell + per-bucket result figures -> reports/figures/results/
python scripts/build_report_figures.py

# 8. Error categorization -> reports/figures/errors/
python scripts/build_error_analysis.py

# 9. Render the final report (loads everything above into the PDF)
cd reports && quarto render final_report.qmd --to pdf
```

Logs are written to `logs/pipeline_<timestamp>.jsonl`. See [`docs/standards/logging_standard.md`](docs/standards/logging_standard.md) for the log format and analysis patterns.

### Run the tests

```bash
# All fast tests
pytest -m "not slow and not api"

# Everything (includes slow tests and tests that call real APIs — needs .env)
pytest

# A specific component
pytest src/preprocessing/tests/
```

See [`docs/standards/testing_standard.md`](docs/standards/testing_standard.md) for test conventions.

---

## Dataset

We use [`huggingface.co/datasets/AlbertoChestnut/telugu-ocr`](https://huggingface.co/datasets/AlbertoChestnut/telugu-ocr) — ~221 digitized Telugu books with paired page images and ground-truth Unicode text, compiled and shared by a classmate. Multiple project teams adopted this dataset in lieu of the originally planned course corpus. See [`downloads/message_from_another_team.md`](downloads/message_from_another_team.md) for context and citation.

The dataset is **not** included in the repository; download via the script above. The full corpus is ~13 GB.

---

## Project status

See [`docs/development/roadmap.md`](docs/development/roadmap.md) for the current phase and what's been completed. Per-phase plans live in `docs/development/phase_*.md`.

---

## Reproducibility

The final report at [`reports/final_report.qmd`](reports/final_report.qmd) is built from CSVs and figures generated by the pipeline scripts in `scripts/`. Anyone with this repository and the two required API keys (Gemini + Anthropic) can reproduce the published results within LLM-temperature noise:

1. Clone the repo and run `scripts/setup_env.sh` to bootstrap the venv + Tesseract Docker image
2. Run `scripts/download_dataset.py` to pull the pinned 5-book subset from HuggingFace
3. Run the 9-step pipeline above ("Reproduce the eval matrix")
4. Tesseract reproduces deterministically; LLM outputs vary within temperature noise.

The CER/WER matrix CSV at `data/processed/eval_subset/cer_wer.csv` is committed as a stable snapshot, so the report's numbers can be verified against the data without re-running the pipeline.

---

## Team

Two-person team for CSCI/DASC 6020 Summer 2026.

Branching and PR workflow follow [`docs/standards/git_workflow_standard.md`](docs/standards/git_workflow_standard.md). Teammate onboarding doc: [`docs/guide/teammate_onboarding.md`](docs/guide/teammate_onboarding.md).

---

## Methodology disclosure

Per the project's academic integrity policy, our use of AI tooling is documented in full in the final project report's methodology section. AI-assisted coding (Claude Code) was used during development; all design decisions, code review, and committed work was authored by the human team members.

---

## License

[MIT](LICENSE). Code and documentation may be reused with attribution.
