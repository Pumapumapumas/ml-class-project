#!/usr/bin/env python3
"""Generate the per-stage preprocessing ablation figure for the final report.

Shows mean and median CER for the 5 preprocessing variants of each of the
3 models for which we have all 5 cells (Claude Sonnet, Tesseract, Gemini
Flash — Opus only has raw + preprocessed, so it's omitted from this
specific comparison).

Output: ``reports/figures/results/preprocessing_ablation.png``

Variants in pipeline-order (left to right on the chart):
- raw           — no preprocessing
- deskew_only   — deskew alone (no binarize)
- grayscale_soft — deskew + denoise + contrast (no binarize, all grayscale-preserving)
- all_4_stages  — deskew + denoise + contrast + binarize (the spec-implied full pipeline)
- preprocessed  — deskew + binarize (what we originally shipped in Phase 2)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.logging_config import setup_logging  # noqa: E402

CER_CSV = REPO_ROOT / "data" / "processed" / "eval_subset" / "cer_wer.csv"
OUTPUT = REPO_ROOT / "reports" / "figures" / "results" / "preprocessing_ablation.png"

# Variant order, left-to-right on the chart. Ordered roughly by
# "amount of preprocessing applied"; the destructive binarize-containing
# variants (preprocessed and all_4_stages) are placed to the right so
# the visual narrative reads "more preprocessing → up to a point, then
# falls off when binarize kicks in."
VARIANT_ORDER = ["raw", "deskew_only", "grayscale_soft", "all_4_stages", "preprocessed"]

VARIANT_LABEL = {
    "raw": "Raw\n(no preprocessing)",
    "deskew_only": "Deskew only\n(no binarize)",
    "grayscale_soft": "Deskew + Denoise\n+ Contrast\n(grayscale-soft)",
    "all_4_stages": "All 4 stages\n(includes binarize)",
    "preprocessed": "Deskew + Binarize\n(original Phase 2)",
}

# Variant colors — group by whether they include binarize, so the visual
# reads "this side = grayscale-preserving, that side = binarize-containing".
VARIANT_COLOR = {
    "raw": "#7f7f7f",
    "deskew_only": "#1f77b4",
    "grayscale_soft": "#2ca02c",
    "all_4_stages": "#d62728",
    "preprocessed": "#ff7f0e",
}

MODELS_TO_PLOT = [
    ("claude", "Claude Sonnet 4.6"),
    ("tesseract", "Tesseract 5"),
    ("gemini", "Gemini Flash 2.5"),
]

LOG = logging.getLogger("ablation")


def main() -> int:
    setup_logging(name="ablation", level=logging.INFO)
    df = pd.read_csv(CER_CSV)
    LOG.info("Loaded %d rows from cer_wer.csv", len(df))

    # We only want the 3 models that have all 5 variants
    df = df[df["model"].isin([m for m, _ in MODELS_TO_PLOT])]
    df = df[df["preprocessing"].isin(VARIANT_ORDER)]
    LOG.info("Filtered to %d rows across 3 models x 5 variants", len(df))

    summary = (
        df.groupby(["model", "preprocessing"])["cer"].agg(["mean", "median", "count"]).reset_index()
    )

    fig, axes = plt.subplots(1, len(MODELS_TO_PLOT), figsize=(15, 5.5), sharey=False)

    for ax, (model_id, model_label) in zip(axes, MODELS_TO_PLOT, strict=True):
        sub = summary[summary["model"] == model_id]
        sub = sub.set_index("preprocessing").reindex(VARIANT_ORDER).reset_index()

        x = np.arange(len(VARIANT_ORDER))
        means = sub["mean"].values
        medians = sub["median"].values
        colors = [VARIANT_COLOR[v] for v in VARIANT_ORDER]

        bars = ax.bar(
            x,
            means,
            color=colors,
            edgecolor="black",
            linewidth=0.6,
            alpha=0.85,
        )
        # Median markers as black dots
        ax.scatter(x, medians, marker="o", s=42, color="black", zorder=3, label="Median CER")

        # Annotate bar tops
        for xi, m, med in zip(x, means, medians, strict=True):
            ax.text(
                xi,
                m + 0.01,
                f"{m:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        ax.set_xticks(x)
        ax.set_xticklabels([VARIANT_LABEL[v] for v in VARIANT_ORDER], fontsize=7.5)
        ax.set_title(model_label, fontsize=12)
        ax.grid(True, axis="y", alpha=0.3)

        # y-scale: clip to reasonable max; if Gemini has the outlier-blown
        # mean (~3.5), clip so the chart is readable and annotate the outlier.
        if model_id == "gemini":
            ax.set_ylim(0, 1.0)
            # Mark all_4_stages with a special annotation indicating mean is
            # outlier-blown
            all_4_idx = VARIANT_ORDER.index("all_4_stages")
            if means[all_4_idx] > 1.0:
                ax.annotate(
                    f"mean clipped\n(actual {means[all_4_idx]:.2f},\nmedian {medians[all_4_idx]:.2f})",
                    xy=(all_4_idx, 0.95),
                    xytext=(all_4_idx, 0.80),
                    fontsize=7,
                    ha="center",
                    va="top",
                    color="red",
                    arrowprops=dict(arrowstyle="->", color="red", lw=0.8),
                )
        else:
            ax.set_ylim(0, max(means) * 1.25)

        ax.set_ylabel("Mean Character Error Rate", fontsize=10)

    fig.suptitle(
        "Per-stage preprocessing ablation — 5 variants × 3 models on 30 eval pages each\n"
        "(black dots = median CER; bars = mean CER; lower is better)",
        fontsize=12,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s", OUTPUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
