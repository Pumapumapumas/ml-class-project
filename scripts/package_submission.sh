#!/usr/bin/env bash
# Package the FinalProject_Rue_Eric/ submission directory per Announcement 4.
#
# Usage: bash scripts/package_submission.sh [output_dir]
#   output_dir defaults to /tmp/FinalProject_Rue_Eric
#
# Run this AFTER final_report.qmd has been rendered to both PDF and HTML,
# and AFTER the presentation has been recorded and saved as
# reports/presentation_video.mp4.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/tmp/FinalProject_Rue_Eric}"

echo "Staging submission to: $OUT"
mkdir -p "$OUT"

# --- Top-level documents (the rubric-graded artifacts) ---
echo "Copying reports..."
cp -v "$REPO_ROOT/reports/final_report.pdf" "$OUT/"
cp -v "$REPO_ROOT/reports/final_report.html" "$OUT/"
cp -v "$REPO_ROOT/reports/corpus_characterization.pdf" "$OUT/"
cp -v "$REPO_ROOT/reports/corpus_characterization.html" "$OUT/"
cp -v "$REPO_ROOT/reports/presentation.html" "$OUT/"
# Presentation video — copy if it exists; warn otherwise.
if [ -f "$REPO_ROOT/reports/presentation_video.mp4" ]; then
    cp -v "$REPO_ROOT/reports/presentation_video.mp4" "$OUT/"
else
    echo "WARNING: reports/presentation_video.mp4 not found — record it before final submit."
fi

# --- Code subset (the engineering deliverable) ---
echo "Copying code..."
mkdir -p "$OUT/code"
cp -r "$REPO_ROOT/src" "$OUT/code/"
cp -r "$REPO_ROOT/scripts" "$OUT/code/"
cp -r "$REPO_ROOT/tests" "$OUT/code/"
cp -r "$REPO_ROOT/notebooks" "$OUT/code/"
cp -r "$REPO_ROOT/docs" "$OUT/code/"
cp -r "$REPO_ROOT/docker" "$OUT/code/"
cp "$REPO_ROOT/requirements.txt" "$OUT/code/"
cp "$REPO_ROOT/.env.example" "$OUT/code/"
cp "$REPO_ROOT/README.md" "$OUT/code/"
cp "$REPO_ROOT/LICENSE" "$OUT/code/"
cp "$REPO_ROOT/pyproject.toml" "$OUT/code/"

# --- Data artifacts (small CSVs and figures, NOT the 13 GB raw corpus) ---
echo "Copying data artifacts..."
mkdir -p "$OUT/data"
cp -r "$REPO_ROOT/data/external/eval_subset" "$OUT/data/" 2>/dev/null || true
cp "$REPO_ROOT/data/external/eval_subset.csv" "$OUT/data/" 2>/dev/null || true
cp "$REPO_ROOT/data/external/corpus_inventory.csv" "$OUT/data/" 2>/dev/null || true
cp "$REPO_ROOT/data/external/corpus_stats.json" "$OUT/data/" 2>/dev/null || true
cp "$REPO_ROOT/data/external/quality_tags.csv" "$OUT/data/" 2>/dev/null || true
cp -r "$REPO_ROOT/data/processed/eval_subset" "$OUT/data/" 2>/dev/null || true
cp -r "$REPO_ROOT/data/processed/submission" "$OUT/data/" 2>/dev/null || true

# --- Figures (referenced by the reports) ---
echo "Copying figures..."
cp -r "$REPO_ROOT/reports/figures" "$OUT/"

# --- Data subdirectory README ---
cat > "$OUT/data/README.md" <<'EOF'
# Data artifacts in this submission

This directory contains the small data artifacts the final report references.
The full 13 GB upstream corpus is NOT included — see the project README for
how to download it from HuggingFace.

## Contents

| Path | What |
|------|------|
| `eval_subset/` | The 30-page stratified evaluation subset (image + ground-truth text pairs) |
| `eval_subset.csv` | Metadata for the eval subset — book_id, page_id, quality_bucket |
| `corpus_inventory.csv` | Per-page metadata for the full 5-book + ASHOKUDU corpus (657 pages) |
| `corpus_stats.json` | Aggregate corpus statistics referenced by the Phase 1 report |
| `quality_tags.csv` | Hand-tagged quality buckets for the 97-page browsing sample |
| `processed/eval_subset/cer_wer.csv` | The 240-row + ablation CER/WER matrix referenced by the final report |
| `processed/eval_subset/fluency.csv` | LLM fluency ratings for the 240 eval-cell OCR outputs |
| `processed/eval_subset/calibration_summary.csv` | Spearman/Pearson correlations from the calibration analysis |
| `processed/eval_subset/error_categories.csv` | Programmatic error categorization counts per (model, preprocessing) cell |
| `processed/submission/gemini/` | The 415+ page Gemini submission sample (per-page .txt files) |
| `processed/submission/gemini_fluency.csv` | At-scale fluency ratings for the full submission sample |

## How to regenerate

See the project's root README — the 9-step "Reproduce the eval matrix" section.
All CSVs and figures are produced by deterministic scripts (Tesseract reproduces
byte-exact; LLM outputs vary within model temperature noise).
EOF

# --- Summary ---
echo ""
echo "=== Submission directory contents ==="
du -sh "$OUT"
echo ""
ls -la "$OUT"
echo ""
echo "Done. To finalize:"
echo "  1. Record the presentation as reports/presentation_video.mp4 and re-run this script"
echo "  2. Verify the contents above"
echo "  3. Upload $OUT to Google Drive"
echo "  4. Share with gudivadav15@ecu.edu (read access)"
echo "  5. Email confirmation to the instructor"
