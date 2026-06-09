#!/usr/bin/env bash
# Bootstrap the ml-class-project environment on a fresh clone.
#
# Run from the repo root:
#   scripts/setup_env.sh
#
# What this does:
#   1. Creates ./.venv/ if it does not exist
#   2. Installs Python dependencies from requirements.txt into the venv
#   3. Builds the Tesseract Docker image (host stays clean)
#   4. Creates project-local cache directories (HuggingFace, etc.)
#   5. Verifies the environment is sane
#   6. Prints the activation hint
#
# Exits non-zero on any failure so CI / human inspection can catch problems.
# Standard: docs/standards/environment_standard.md

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log()  { printf '[setup] %s\n' "$*"; }
fail() { printf '[setup] ERROR: %s\n' "$*" >&2; exit 1; }

# -----------------------------------------------------------------------------
# 1. Required commands
# -----------------------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || fail "python3 is not installed on this host"
command -v docker  >/dev/null 2>&1 || fail "docker is not installed on this host"

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "Detected python3 ${PYTHON_VERSION}"

# Quick sanity: project requires 3.11+
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
    || fail "Python 3.11+ required (detected ${PYTHON_VERSION}). Install a newer Python and re-run."

# -----------------------------------------------------------------------------
# 2. Create the venv if missing
# -----------------------------------------------------------------------------
if [[ ! -d ".venv" ]]; then
    log "Creating venv at ./.venv/"
    python3 -m venv .venv
else
    log "Reusing existing ./.venv/"
fi

# Use venv's pip/python directly; avoid relying on the caller's activation state.
VENV_PY="$REPO_ROOT/.venv/bin/python"
VENV_PIP="$REPO_ROOT/.venv/bin/pip"

[[ -x "$VENV_PY"  ]] || fail "venv python missing at ${VENV_PY}"
[[ -x "$VENV_PIP" ]] || fail "venv pip missing at ${VENV_PIP}"

# -----------------------------------------------------------------------------
# 3. Install Python deps
# -----------------------------------------------------------------------------
log "Upgrading pip"
"$VENV_PY" -m pip install --quiet --upgrade pip

log "Installing dependencies from requirements.txt"
"$VENV_PIP" install --quiet -r requirements.txt

# -----------------------------------------------------------------------------
# 4. Build the Tesseract Docker image
# -----------------------------------------------------------------------------
log "Building Docker image ml-class-project/tesseract (host stays clean)"
docker build --quiet -t ml-class-project/tesseract docker/tesseract/ \
    || fail "docker build failed — check Docker daemon is running and you have permission"

# -----------------------------------------------------------------------------
# 5. Project-local cache directories
# -----------------------------------------------------------------------------
log "Creating project-local cache directories under data/external/"
mkdir -p data/external/hf_cache/transformers
mkdir -p data/raw data/interim data/processed
mkdir -p logs

# -----------------------------------------------------------------------------
# 6. Verify
# -----------------------------------------------------------------------------
log "Verifying Python imports"
"$VENV_PY" -c 'import pandas, numpy, cv2, huggingface_hub, jiwer; print("[setup] python imports OK")' \
    || fail "Python import sanity check failed"

log "Verifying Tesseract container"
docker run --rm ml-class-project/tesseract tesseract --list-langs | grep -q '^tel$' \
    || fail "Tesseract Telugu pack not present in the image"
log "[setup] tesseract Telugu pack OK"

# -----------------------------------------------------------------------------
# 7. Next steps for the operator
# -----------------------------------------------------------------------------
cat <<'EOF'

[setup] Environment ready.

Next steps:
  1. Copy .env.example to .env and fill in your API keys:
         cp .env.example .env
         $EDITOR .env

  2. Activate the venv for development:
         source .venv/bin/activate

  3. Verify the test suite skeleton:
         pytest -m "not slow and not api"

  4. Download a development subset of the Telugu corpus (~500 MB):
         python scripts/download_dataset.py --subset 5

EOF
