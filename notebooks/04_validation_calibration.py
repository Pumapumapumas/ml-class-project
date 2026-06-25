#!/usr/bin/env python3
"""Phase 4 Task 5 — Calibrate LLM validation signals against ground-truth CER.

Not a notebook — a flat Python script that produces the figures and the
correlation numbers the final report references. Decided to author this as a
script rather than a ``.ipynb`` because:

1. Quarto can render a .py file as a report figure source just as well as it
   can a notebook.
2. A flat script is easier to re-run after data refreshes (no widget state,
   no out-of-order cell-execution risk that bit the corpus-stats notebook
   earlier in the project).
3. The output artifacts (CSV summary, PNG figures) are the deliverable; the
   notebook prose lives in ``reports/final_report.qmd``.

Outputs:

- ``reports/figures/calibration/fluency_vs_cer.png`` — scatter of CER vs
  fluency rating, colored by model.
- ``reports/figures/calibration/agreement_vs_cer.png`` — scatter of mean
  CER vs mean pairwise cross-model agreement, one point per page.
- ``data/processed/eval_subset/calibration_summary.csv`` — Spearman and
  Pearson correlations for each calibration relationship.

Run:

    python notebooks/04_validation_calibration.py

Standards: see ``docs/standards/python_code_standard.md``.
"""

from __future__ import annotations

import logging
import sys
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import pearsonr, spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.logging_config import setup_logging
from src.validation.agreement import agreement_score

CER_CSV = REPO_ROOT / "data" / "processed" / "eval_subset" / "cer_wer.csv"
FLUENCY_CSV = REPO_ROOT / "data" / "processed" / "eval_subset" / "fluency.csv"
OUTPUT_DIR = REPO_ROOT / "reports" / "figures" / "calibration"
SUMMARY_CSV = REPO_ROOT / "data" / "processed" / "eval_subset" / "calibration_summary.csv"

# Colors per model — keep consistent across all calibration figures.
MODEL_COLORS = {
    "claude": "#1f77b4",
    "claude_opus": "#9467bd",
    "gemini": "#d62728",
    "tesseract": "#2ca02c",
}

LOG = logging.getLogger("calibration")


def model_label(model: str, preprocessing: str) -> str:
    """Human-readable label for a (model, preprocessing) cell."""
    pp_short = {
        "raw": "raw",
        "preprocessed": "pre",
        "opus_raw": "opus-raw",
        "opus_preprocessed": "opus-pre",
    }
    return f"{model}_{pp_short.get(preprocessing, preprocessing)}"


def model_color(model: str, preprocessing: str) -> str:
    """Stable color for a (model, preprocessing) cell."""
    # Treat 'opus' as its own family
    if preprocessing.startswith("opus"):
        return MODEL_COLORS["claude_opus"]
    return MODEL_COLORS.get(model, "#7f7f7f")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load CER + fluency CSVs and return them."""
    if not CER_CSV.exists():
        raise FileNotFoundError(f"CER CSV missing — run scripts/score_ocr.py first: {CER_CSV}")
    if not FLUENCY_CSV.exists():
        raise FileNotFoundError(
            f"Fluency CSV missing — run scripts/run_fluency.py first: {FLUENCY_CSV}"
        )

    cer = pd.read_csv(CER_CSV)
    fluency = pd.read_csv(FLUENCY_CSV)

    LOG.info("Loaded CER:     %d rows  (%d unique pages)", len(cer), cer["page_id"].nunique())
    LOG.info(
        "Loaded fluency: %d rows  (%d unique pages)",
        len(fluency),
        fluency["page_id"].nunique(),
    )

    return cer, fluency


def join_cer_fluency(cer: pd.DataFrame, fluency: pd.DataFrame) -> pd.DataFrame:
    """Inner-join CER and fluency on (book_id, page_id, model, preprocessing)."""
    joined = pd.merge(
        cer,
        fluency,
        on=["book_id", "page_id", "model", "preprocessing"],
        how="inner",
        validate="one_to_one",
    )
    LOG.info("Joined: %d rows (CER+fluency for the same OCR output)", len(joined))
    return joined


def plot_fluency_vs_cer(joined: pd.DataFrame, out_path: Path) -> dict[str, float]:
    """Scatter plot + per-cell correlation table."""
    fig, ax = plt.subplots(figsize=(9, 6))

    correlations: dict[str, float] = {}
    for (model, preprocessing), group in joined.groupby(["model", "preprocessing"]):
        label = model_label(model, preprocessing)
        color = model_color(model, preprocessing)
        ax.scatter(
            group["fluency_rating"],
            group["cer"],
            alpha=0.6,
            s=50,
            color=color,
            label=label,
        )
        if len(group) >= 5:
            rho, _ = spearmanr(group["fluency_rating"], group["cer"])
            correlations[f"spearman_{label}"] = rho

    # Overall correlation across all cells
    overall_spearman, _ = spearmanr(joined["fluency_rating"], joined["cer"])
    overall_pearson, _ = pearsonr(joined["fluency_rating"], joined["cer"])
    correlations["spearman_overall"] = overall_spearman
    correlations["pearson_overall"] = overall_pearson

    ax.set_xlabel("LLM fluency rating (1-5, judged by Claude Sonnet 4.6)", fontsize=11)
    ax.set_ylabel("Character Error Rate (ground truth)", fontsize=11)
    ax.set_title(
        f"Fluency rating vs CER  —  Spearman ρ = {overall_spearman:.3f}, "  # noqa: RUF001
        f"Pearson r = {overall_pearson:.3f}",
        fontsize=12,
    )
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.invert_yaxis()  # Lower CER (better) is up; higher fluency (better) is right.

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s  (Spearman=%.3f, Pearson=%.3f)", out_path, overall_spearman, overall_pearson)

    return correlations


def compute_pairwise_agreement(cer: pd.DataFrame) -> pd.DataFrame:
    """Per-page mean pairwise agreement across model pairs.

    Iterates over the 30 unique (book_id, page_id) pages in the eval subset.
    For each page, loads each available (model, preprocessing) OCR output
    from disk, computes pairwise SequenceMatcher ratios, and returns the
    mean. Also computes the mean CER across the same cells as the
    proxy-for-ground-truth-quality column.
    """
    ocr_root = REPO_ROOT / "data" / "processed" / "eval_subset"

    pages = cer[["book_id", "page_id"]].drop_duplicates()
    rows = []
    for _, row in pages.iterrows():
        book_id = row["book_id"]
        page_id = row["page_id"]

        # Find OCR outputs for this page across all cells
        ocr_texts: dict[str, str] = {}
        for cell_dir in sorted(ocr_root.iterdir()):
            if not cell_dir.is_dir() or cell_dir.name.startswith("."):
                continue
            txt = cell_dir / book_id / f"{page_id}.txt"
            if txt.exists():
                ocr_texts[cell_dir.name] = txt.read_text(encoding="utf-8")

        if len(ocr_texts) < 2:
            continue

        # Mean pairwise agreement across all model-pair combinations
        pairs = list(combinations(ocr_texts.values(), 2))
        mean_agreement = sum(agreement_score(a, b) for a, b in pairs) / len(pairs)

        # Mean CER for this page across the cells we have CER data for
        page_cer = cer[(cer["book_id"] == book_id) & (cer["page_id"] == page_id)]["cer"].mean()

        rows.append(
            {
                "book_id": book_id,
                "page_id": page_id,
                "n_cells": len(ocr_texts),
                "mean_pairwise_agreement": mean_agreement,
                "mean_cer": page_cer,
            }
        )

    df = pd.DataFrame(rows)
    LOG.info("Computed pairwise agreement on %d pages", len(df))
    return df


def plot_agreement_vs_cer(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    """Scatter agreement vs CER across pages, with correlation in the title."""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["mean_pairwise_agreement"], df["mean_cer"], alpha=0.7, s=70, color="#1f77b4")

    rho, _ = spearmanr(df["mean_pairwise_agreement"], df["mean_cer"])
    r, _ = pearsonr(df["mean_pairwise_agreement"], df["mean_cer"])

    ax.set_xlabel(
        "Mean pairwise cross-model agreement\n(difflib SequenceMatcher ratio across all 4 models)",
        fontsize=11,
    )
    ax.set_ylabel("Mean CER across the 4 raw-image cells", fontsize=11)
    ax.set_title(
        f"Cross-model agreement vs CER  —  Spearman ρ = {rho:.3f}, Pearson r = {r:.3f}",  # noqa: RUF001
        fontsize=12,
    )
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s  (Spearman=%.3f, Pearson=%.3f)", out_path, rho, r)

    return {"agreement_spearman": rho, "agreement_pearson": r}


def main() -> int:
    setup_logging(name="calibration", level=logging.INFO)

    cer, fluency = load_data()
    joined = join_cer_fluency(cer, fluency)

    LOG.info("=" * 60)
    LOG.info("Calibration 1: Fluency rating vs CER")
    fluency_corrs = plot_fluency_vs_cer(joined, OUTPUT_DIR / "fluency_vs_cer.png")

    LOG.info("=" * 60)
    LOG.info("Calibration 2: Cross-model agreement vs mean CER")
    agreement_df = compute_pairwise_agreement(cer)
    agreement_corrs = plot_agreement_vs_cer(agreement_df, OUTPUT_DIR / "agreement_vs_cer.png")

    # Persist a summary CSV the report can reference.
    summary_rows = []
    for key, val in fluency_corrs.items():
        summary_rows.append({"metric": key, "value": val})
    for key, val in agreement_corrs.items():
        summary_rows.append({"metric": key, "value": val})
    summary_df = pd.DataFrame(summary_rows)
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(SUMMARY_CSV, index=False)
    LOG.info("Wrote summary CSV: %s", SUMMARY_CSV)

    LOG.info("=" * 60)
    LOG.info("Calibration done. Summary:")
    for _, row in summary_df.iterrows():
        LOG.info("  %-32s = %.4f", row["metric"], row["value"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
