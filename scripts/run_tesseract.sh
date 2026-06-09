#!/usr/bin/env bash
# Thin wrapper that runs Tesseract from the project's Docker image with
# data/ mounted into the container.
#
# Usage:
#   scripts/run_tesseract.sh <image-path-relative-to-repo> <output-base-relative-to-repo> [tesseract args...]
#
# Example:
#   scripts/run_tesseract.sh \
#       data/raw/book_001/page_001.jpg \
#       data/interim/book_001/page_001 \
#       -l tel --psm 6
#
# The wrapper rewrites the host paths into /data/* inside the container, so
# callers do not need to think about the mount.
#
# Standard: docs/standards/environment_standard.md

set -euo pipefail

if [[ $# -lt 2 ]]; then
    cat >&2 <<EOF
usage: $0 <image-path> <output-base> [tesseract args...]

  image-path:  path relative to repo root (e.g. data/raw/book_001/page_001.jpg)
  output-base: path relative to repo root, NO extension (Tesseract appends .txt)

Any additional arguments are passed through to tesseract.
EOF
    exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

INPUT_HOST="$1"
OUTPUT_HOST="$2"
shift 2

# Validate input lives under data/
case "$INPUT_HOST" in
    data/*) : ;;
    *) printf 'ERROR: image-path must be under data/ (got: %s)\n' "$INPUT_HOST" >&2; exit 64 ;;
esac
case "$OUTPUT_HOST" in
    data/*) : ;;
    *) printf 'ERROR: output-base must be under data/ (got: %s)\n' "$OUTPUT_HOST" >&2; exit 64 ;;
esac

# Make sure the input exists
[[ -f "$INPUT_HOST" ]] || { printf 'ERROR: input file does not exist: %s\n' "$INPUT_HOST" >&2; exit 66; }

# Ensure the output directory exists on the host (so the volume mount sees it)
mkdir -p "$(dirname "$OUTPUT_HOST")"

# Inside the container, data/ is mounted at /data; rewrite paths.
INPUT_CTNR="/data/${INPUT_HOST#data/}"
OUTPUT_CTNR="/data/${OUTPUT_HOST#data/}"

exec docker run --rm \
    -v "$REPO_ROOT/data:/data" \
    ml-class-project/tesseract \
    tesseract "$INPUT_CTNR" "$OUTPUT_CTNR" "$@"
