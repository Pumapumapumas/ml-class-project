#!/usr/bin/env python3
"""Generate the final report's data-derived figures.

Three figures live in ``reports/figures/results/``:

1. ``per_cell_mean_cer.png`` — bar chart of mean CER per (model, preprocessing)
   cell, color-coded by preprocessing condition.
2. ``per_bucket_cer_box.png`` — boxplot of per-page CER stratified by quality
   bucket, with one panel per model showing the four cells of that model.
3. ``cost_vs_quality.png`` — scatter of cost-per-page vs mean CER per cell, to
   make the cost-quality tradeoff visible.

All three are sourced from ``data/processed/eval_subset/cer_wer.csv`` joined
with ``data/external/eval_subset.csv`` (for the per-bucket figure).

Run from the repo root:

    python scripts/build_report_figures.py

Standards: see ``docs/standards/python_code_standard.md``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.logging_config import setup_logging  # noqa: E402

CER_CSV = REPO_ROOT / "data" / "processed" / "eval_subset" / "cer_wer.csv"
EVAL_SUBSET_CSV = REPO_ROOT / "data" / "external" / "eval_subset.csv"
OUTPUT_DIR = REPO_ROOT / "reports" / "figures" / "results"

LOG = logging.getLogger("build_report_figures")

# Per-page cost in USD. Estimated from validated smoke tests during the
# project; figures and table cells reference these constants.
COST_PER_PAGE: dict[tuple[str, str], float] = {
    ("claude", "raw"): 0.018,
    ("claude", "preprocessed"): 0.018,
    ("claude", "opus_raw"): 0.13,
    ("claude", "opus_preprocessed"): 0.13,
    ("gemini", "raw"): 0.0004,
    ("gemini", "preprocessed"): 0.0004,
    ("tesseract", "raw"): 0.0,
    ("tesseract", "preprocessed"): 0.0,
}

PREPROCESSING_COLOR = {
    "raw": "#4c72b0",
    "preprocessed": "#dd8452",
    "opus_raw": "#4c72b0",
    "opus_preprocessed": "#dd8452",
}


def cell_label(model: str, preprocessing: str) -> str:
    """Compact label used on chart axes."""
    if preprocessing == "opus_raw":
        return "Opus 4.8\nraw"
    if preprocessing == "opus_preprocessed":
        return "Opus 4.8\npreproc"
    model_short = {"claude": "Sonnet 4.6", "gemini": "Gemini Flash", "tesseract": "Tesseract 5"}
    return f"{model_short.get(model, model)}\n{preprocessing}"


def plot_per_cell_mean_cer(cer: pd.DataFrame, out_path: Path) -> None:
    """Bar chart of mean CER per (model, preprocessing) cell."""
    grouped = (
        cer.groupby(["model", "preprocessing"])["cer"]
        .agg(["mean", "median", "count"])
        .reset_index()
    )

    # Sort so paired (raw, preprocessed) bars sit next to each other and the
    # overall order is best-to-worst by mean CER.
    grouped["_sort_key"] = grouped["mean"]
    grouped = grouped.sort_values("_sort_key")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x_positions = range(len(grouped))
    colors = [PREPROCESSING_COLOR.get(row.preprocessing, "#7f7f7f") for row in grouped.itertuples()]

    bars = ax.bar(x_positions, grouped["mean"], color=colors, edgecolor="black", linewidth=0.5)

    # Median markers as black dots on each bar
    ax.scatter(
        x_positions,
        grouped["median"],
        marker="o",
        s=40,
        color="black",
        zorder=3,
        label="Median CER",
    )

    # Annotate each bar with the mean value
    for bar, mean_val in zip(bars, grouped["mean"], strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{mean_val:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(
        [cell_label(row.model, row.preprocessing) for row in grouped.itertuples()],
        rotation=0,
        fontsize=9,
    )
    ax.set_ylabel("Character Error Rate", fontsize=11)
    ax.set_title(
        "Mean CER per (model, preprocessing) cell — n=30 pages each",
        fontsize=12,
    )

    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=PREPROCESSING_COLOR["raw"], edgecolor="black", label="Raw image"),
        Patch(
            facecolor=PREPROCESSING_COLOR["preprocessed"], edgecolor="black", label="Preprocessed"
        ),
    ]
    ax.legend(
        handles=[
            *legend_handles,
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="black",
                markersize=7,
                label="Median CER",
            ),
        ],
        loc="upper left",
        fontsize=9,
    )
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_ylim(0, max(grouped["mean"]) * 1.15)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s", out_path)


def plot_per_bucket_cer(cer: pd.DataFrame, eval_subset: pd.DataFrame, out_path: Path) -> None:
    """Boxplot of CER stratified by quality bucket, one panel per model.

    Color-codes the four cells (4 models x 2 preprocessing — collapsed to model
    here for clarity; the per-cell figure already shows preprocessing impact).
    """
    # Join CER rows to their quality bucket
    joined = pd.merge(
        cer,
        eval_subset[["book_id", "page_id", "quality_bucket"]],
        on=["book_id", "page_id"],
        how="inner",
    )
    # For per-bucket display, focus on raw cells only (the cell-comparison
    # figure already shows preprocessing's effect); within raw, we have 4
    # models to compare per bucket.
    raw_only = joined[joined["preprocessing"].isin(["raw", "opus_raw"])].copy()
    raw_only["display_model"] = raw_only.apply(
        lambda r: (
            "Opus 4.8"
            if r["preprocessing"] == "opus_raw"
            else {
                "claude": "Sonnet 4.6",
                "gemini": "Gemini Flash",
                "tesseract": "Tesseract 5",
            }.get(r["model"], r["model"])
        ),
        axis=1,
    )

    bucket_order = ["Clean", "Skewed", "Complex Layout", "Faded", "Damaged"]
    model_order = ["Opus 4.8", "Sonnet 4.6", "Tesseract 5", "Gemini Flash"]

    fig, axes = plt.subplots(1, len(model_order), figsize=(15, 5), sharey=True)
    for ax, model in zip(axes, model_order, strict=True):
        sub = raw_only[raw_only["display_model"] == model]
        data_by_bucket = [
            sub[sub["quality_bucket"] == bucket]["cer"].values for bucket in bucket_order
        ]
        bp = ax.boxplot(
            data_by_bucket,
            tick_labels=[b.replace(" ", "\n") for b in bucket_order],
            patch_artist=True,
            widths=0.55,
            flierprops={"marker": "x", "markersize": 4, "alpha": 0.5},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor("#4c72b0")
            patch.set_alpha(0.6)
        ax.set_title(model, fontsize=11)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(True, axis="y", alpha=0.3)
        ax.set_ylim(0, 1.1)

    axes[0].set_ylabel("Character Error Rate", fontsize=11)
    fig.suptitle(
        "CER by quality bucket — raw images, per model (n=6 per bucket per cell)", fontsize=12
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s", out_path)


def plot_cost_vs_quality(cer: pd.DataFrame, out_path: Path) -> None:
    """Scatter of cost-per-page vs mean CER, one point per cell."""
    grouped = cer.groupby(["model", "preprocessing"])["cer"].agg(["mean"]).reset_index()
    grouped["cost_per_page_usd"] = grouped.apply(
        lambda r: COST_PER_PAGE.get((r["model"], r["preprocessing"]), 0.0), axis=1
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    for _, row in grouped.iterrows():
        # Tesseract has cost=0 which is hard to plot on log scale; render at a small floor.
        x = row["cost_per_page_usd"] if row["cost_per_page_usd"] > 0 else 1e-5
        color = (
            "#9467bd"
            if row["preprocessing"].startswith("opus")
            else {
                "claude": "#1f77b4",
                "gemini": "#d62728",
                "tesseract": "#2ca02c",
            }.get(row["model"], "#7f7f7f")
        )
        marker = "o" if row["preprocessing"] in ("raw", "opus_raw") else "s"
        ax.scatter(
            x, row["mean"], s=120, color=color, marker=marker, edgecolor="black", linewidth=0.7
        )
        ax.annotate(
            cell_label(row["model"], row["preprocessing"]).replace("\n", " "),
            xy=(x, row["mean"]),
            xytext=(8, 4),
            textcoords="offset points",
            fontsize=8,
            alpha=0.85,
        )

    ax.set_xscale("log")
    ax.set_xlabel("Cost per page (USD, log scale; Tesseract plotted at floor=$1e-5)", fontsize=10)
    ax.set_ylabel("Mean Character Error Rate", fontsize=11)
    ax.set_title("Cost vs OCR quality across the eval matrix", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Legend
    from matplotlib.lines import Line2D

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#4c72b0",
            markersize=10,
            label="Raw image",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor="#dd8452",
            markersize=10,
            label="Preprocessed",
        ),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=9)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s", out_path)


def main() -> int:
    setup_logging(name="build_report_figures", level=logging.INFO)

    if not CER_CSV.exists():
        LOG.error("CER CSV missing: %s", CER_CSV)
        return 2

    cer = pd.read_csv(CER_CSV)
    LOG.info("Loaded CER: %d rows", len(cer))

    eval_subset = None
    if EVAL_SUBSET_CSV.exists():
        eval_subset = pd.read_csv(EVAL_SUBSET_CSV)
        LOG.info("Loaded eval subset: %d rows", len(eval_subset))

    plot_per_cell_mean_cer(cer, OUTPUT_DIR / "per_cell_mean_cer.png")

    if eval_subset is not None and "quality_bucket" in eval_subset.columns:
        plot_per_bucket_cer(cer, eval_subset, OUTPUT_DIR / "per_bucket_cer_box.png")
    else:
        LOG.warning(
            "Skipping per-bucket figure — eval_subset.csv missing or has no quality_bucket column"
        )

    plot_cost_vs_quality(cer, OUTPUT_DIR / "cost_vs_quality.png")

    LOG.info("=" * 60)
    LOG.info("Done. Figures in: %s", OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
