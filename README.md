# Multilingual OCR for Telugu Text Using Large Language Models

End-to-end pipeline that extracts clean Unicode text from scanned Telugu document images using vision-capable Large Language Models, with an accompanying validation framework that uses LLMs to assess OCR quality both with and without ground-truth references.

Course project for **CSCI/DASC 6020 — Machine Learning, Summer 2026**, East Carolina University.

---

## What this project does

1. Ingests scanned Telugu page images (`.jpg` / `.png`)
2. Preprocesses them: format standardization, deskew, binarization, denoising, contrast enhancement, layout segmentation
3. Runs each page through at least two vision-capable OCR models (Gemini, Surya OCR, plus optionally Tesseract / GPT-4o / Claude / Qwen2-VL) and captures the Unicode text output
4. Evaluates accuracy on a paired ground-truth sample using Character Error Rate (CER) and Word Error Rate (WER)
5. Independently validates OCR quality at scale via LLM-based methods (fluency scoring, cross-model agreement, linguistic error detection) — the novel component, designed to scale validation beyond hand-annotated ground truth
6. Produces an analysis report with model comparison, error categorization, and scalability/cost estimates

Full project specification is in [`downloads/Telugu-OCR-Project.qmd`](downloads/Telugu-OCR-Project.qmd).

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

| Service | What it's used for | Required? | How to get a key | Free tier? |
|---------|-------------------|-----------|------------------|-----------|
| **Google Gemini** | Primary OCR model + LLM-based validation | **Yes** | https://aistudio.google.com/app/apikey | Yes — 15 requests/minute, 1500/day |
| HuggingFace | Downloading the dataset | Yes if pulling private datasets; ours is public | https://huggingface.co/settings/tokens | Yes — no cost |
| OpenAI (GPT-4o) | Stretch comparison only | No | https://platform.openai.com/api-keys | No — paid |
| Anthropic (Claude) | Stretch comparison only | No | https://console.anthropic.com/ | No — paid |

**Get a Gemini key in 3 steps:**

1. Sign in to https://aistudio.google.com/app/apikey with a Google account
2. Click "Create API key" (no payment info required for the free tier)
3. Copy the key into your `.env` file:
   ```
   GEMINI_API_KEY=AIza...your-key-here...
   ```

**Important:** never commit `.env`. It is gitignored. The full credential policy is in [`docs/standards/credential_handling_standard.md`](docs/standards/credential_handling_standard.md). Read that doc before adding any new key or service.

### Run the pipeline

```bash
# Preprocess a single book (development cycle)
python -m src.preprocessing.cli --input data/raw/book_001 --output data/interim/book_001

# Run OCR with Gemini on the preprocessed pages
python -m src.ocr.cli --model gemini --input data/interim/book_001 --output data/processed/book_001

# Score against ground truth
python -m src.validation.cli --ocr data/processed/book_001 --truth data/raw/book_001 --metrics cer,wer

# Full pipeline (all-in-one orchestration script — to be added)
python scripts/run_full_pipeline.py --book book_001 --models gemini,surya
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

The full final report (Phase 5 deliverable) is built from `reports/final_report.qmd` and committed alongside the source. Anyone with this repository and a Gemini API key should be able to:

1. Clone the repo
2. Run `scripts/download_dataset.py`
3. Run `scripts/run_full_pipeline.py`
4. Render the report with `quarto render reports/final_report.qmd`

…and reproduce the published results within run-to-run variance (LLM API outputs are not bit-deterministic but should be substantially similar).

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
