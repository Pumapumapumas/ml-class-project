# Scripts

Standalone scripts: environment bootstrap, dataset acquisition, pipeline orchestration, and utility tools.

Each script has a top-of-file docstring explaining what it does, how to run it, and what side effects to expect. Scripts must be runnable as `python scripts/<name>.py` from the repo root (use absolute paths from a `PROJECT_ROOT` constant, not `os.getcwd()`).

## Anticipated scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `setup_env.sh` | Bootstrap a conda/venv environment with all dependencies | TBD |
| `setup_docker.sh` | Build a Docker image with the full toolchain (alternative to setup_env.sh) | TBD |
| `download_dataset.py` | Pull a configurable subset of the Telugu OCR corpus from HuggingFace | TBD |
| `run_full_pipeline.py` | Orchestrate preprocessing → OCR → validation for a book or batch | TBD |
| `generate_synthetic_data.py` | Render synthetic Telugu page images from Unicode text + fonts (fallback ground truth) | TBD |

This README is updated as scripts are added.

## Conventions

- Scripts are not the place for core logic — they orchestrate code that lives in `src/`. See [`docs/standards/repo_layout_standard.md`](../docs/standards/repo_layout_standard.md).
- Long-running scripts log via the project's standard logger (see [`docs/standards/logging_standard.md`](../docs/standards/logging_standard.md)).
- Scripts that consume secrets load them from `.env` via `python-dotenv` (see [`docs/standards/credential_handling_standard.md`](../docs/standards/credential_handling_standard.md)).
