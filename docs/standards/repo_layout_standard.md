# Repository Layout Standard

**Status:** Active
**Scope:** Canonical directory structure for this monorepo. Where things go and what they hold.

---

## Top-level layout

```
ml-class-project/
├── CLAUDE.md                   # Operating instructions for Claude in this repo
├── README.md                   # Project overview, quick-start
├── LICENSE                     # MIT
├── .gitignore                  # Python + Jupyter + data + secrets
├── .env.example                # Template; real .env is gitignored
├── docs/
│   ├── standards/              # Standards docs (this kind of doc)
│   ├── development/            # Roadmap, phase tracking, loose ends
│   └── guide/                  # User-facing reproduction guides
├── downloads/                  # Raw external materials (announcements, project spec)
├── scripts/                    # Setup, deployment, utility scripts
├── src/                        # Source code (Python modules)
├── notebooks/                  # Jupyter notebooks for exploration / analysis
├── tests/                      # Test suite (see Testing Standard)
├── data/                       # Input data (gitignored, see below)
├── reports/                    # Generated reports, Quarto outputs
└── logs/                       # Pipeline logs (gitignored)
```

---

## Directory responsibilities

### `docs/`

Documentation only. No code. See [Documentation Standard](./documentation_standard.md).

### `downloads/`

Raw external artifacts received from the instructor, dataset providers, or other teams. Treat as immutable inputs — never edit a file in here directly.

### `scripts/`

Standalone scripts: environment setup, dataset download, deployment helpers. Each script has a top-of-file docstring explaining what it does and how to run it.

### `src/`

The actual project code, organized as a Python package. Subdivide by concern:

```
src/
├── preprocessing/      # Image preprocessing pipeline
├── ocr/                # OCR adapters (Gemini, Tesseract, Surya, etc.)
├── validation/         # CER/WER + LLM-based validation
├── analysis/           # Error categorization, plotting
└── utils/              # Cross-cutting helpers (config, logging, etc.)
```

Each subdirectory has an `__init__.py` and its own `tests/` directory next to it (see [Testing Standard](./testing_standard.md)).

### `notebooks/`

Jupyter notebooks for exploration, prototyping, and analysis that's intentionally narrative-driven. **Notebooks call into `src/`** for any non-trivial logic — they don't hold the core implementation.

Naming: `NN_short_topic.ipynb` (e.g., `01_corpus_characterization.ipynb`, `02_preprocessing_experiments.ipynb`).

### `tests/`

Top-level test directory holding integration and end-to-end tests that span multiple `src/` subdirectories. Per-component unit tests live in `src/<component>/tests/`. See [Testing Standard](./testing_standard.md).

### `data/`

Input datasets. Always gitignored — the Telugu corpus is ~13 GB and doesn't belong in git history.

Internal layout:
```
data/
├── raw/            # As-downloaded, never edited
├── interim/        # Partially processed (e.g., deskewed)
├── processed/      # Pipeline output ready for analysis
└── external/       # Reference data (e.g., Telugu fonts for synthetic generation)
```

A `data/README.md` (checked in even though `data/` contents are not) documents what each subdirectory should contain and how to obtain the source.

### `reports/`

Generated reports — Quarto `.qmd` source, rendered PDFs and HTMLs, slide decks. The final project report's source lives here.

### `logs/`

Pipeline logs. Gitignored. See [Logging Standard](./logging_standard.md).

---

## Cross-cutting rules

- **Source code under `src/`, never at repo root.**
- **Notebooks are for narrative analysis, not the core pipeline.** If a notebook accumulates real logic, extract it to `src/`.
- **Data is gitignored.** Always. Sample data fixtures used by tests can live in `tests/fixtures/` (small enough not to bloat the repo).
- **Secrets are gitignored.** `.env` for real values, `.env.example` checked in as a template. See [Credential Handling Standard](./credential_handling_standard.md).
- **`downloads/` is read-only.** Never edit a file there; it represents the upstream source.

---

## Why this layout

For a class project of this scope, this is the smallest layout that still scales to a multi-phase, multi-person project. It mirrors common Python data-science project conventions (cookiecutter-data-science, Kedro-lite) and aligns with the grading rubric's emphasis on "code quality, reproducibility, and documentation."

For larger projects with multiple deployable services, the layout would evolve toward separate repos per service. We're explicitly monorepo here because the deliverable is a single coherent pipeline.
