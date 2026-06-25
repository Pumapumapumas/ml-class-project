#!/usr/bin/env python3
"""Phase 5 Task 1 — Programmatic error categorization across the eval matrix.

Rather than hand-tag a small sample of errors, this script computes the
character-level diff between every OCR output and its ground truth, then
classifies each edit (insertion / deletion / substitution) by Unicode
codepoint rules. The categories were chosen to map onto the rubric's "what
kinds of OCR errors does each model make" question:

- ``vowel_sign`` (matra) — vowel signs U+0C3E..U+0C4D drive the
  visually-attached diacritic errors specific to Telugu.
- ``conjunct`` — virama / halant U+0C4D involvement (consonant clusters).
- ``base_consonant_vowel`` — independent Telugu codepoints (consonants,
  independent vowels, digits) substituted/dropped/inserted.
- ``whitespace`` — word-boundary edits (spaces, newlines).
- ``latin_punctuation`` — Latin letters, punctuation, ASCII digits
  appearing in the diff (Telugu books carry some English page numbers and
  punctuation; we separate these so the model's "stuck a Latin word in"
  failure mode shows up distinctly).
- ``hallucination_burst`` — contiguous insertions of length >= 8 chars
  (the model produced text the ground truth never had — visible as long
  unmatched runs in the diff).
- ``omission_burst`` — contiguous deletions of length >= 8 chars (the
  model failed to read a long stretch — common on damaged or faded
  pages).
- ``other`` — anything not in the above categories.

The script aggregates per (model, preprocessing) cell and writes:

- ``reports/figures/errors/error_categories_by_model.png`` — stacked bar
  chart, one bar per cell, showing the proportion of edits in each
  category.
- ``data/processed/eval_subset/error_categories.csv`` — long-format CSV
  with per-cell category counts.

Run:

    python scripts/build_error_analysis.py
"""

from __future__ import annotations

import logging
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.logging_config import setup_logging  # noqa: E402

OCR_ROOT = REPO_ROOT / "data" / "processed" / "eval_subset"
TRUTH_ROOT = REPO_ROOT / "data" / "raw" / "telugu-ocr"
OUT_CSV = REPO_ROOT / "data" / "processed" / "eval_subset" / "error_categories.csv"
OUT_FIG = REPO_ROOT / "reports" / "figures" / "errors" / "error_categories_by_model.png"

# Telugu Unicode block U+0C00..U+0C7F.
TELUGU_BLOCK_START = 0x0C00
TELUGU_BLOCK_END = 0x0C7F

# Vowel signs (matras) — visually attach to a base consonant.
TELUGU_VOWEL_SIGN_START = 0x0C3E
TELUGU_VOWEL_SIGN_END = 0x0C4D  # virama is the upper end of this range

TELUGU_VIRAMA = 0x0C4D  # halanta / virama — used to form conjuncts

# Burst threshold — contiguous edits at least this long count as a single
# "hallucination" or "omission" event rather than per-character edits.
BURST_THRESHOLD = 8

LOG = logging.getLogger("error_analysis")

CATEGORIES = [
    "vowel_sign",
    "conjunct",
    "base_consonant_vowel",
    "whitespace",
    "latin_punctuation",
    "hallucination_burst",
    "omission_burst",
    "other",
]

CATEGORY_COLORS = {
    "vowel_sign": "#1f77b4",
    "conjunct": "#9467bd",
    "base_consonant_vowel": "#2ca02c",
    "whitespace": "#bcbd22",
    "latin_punctuation": "#8c564b",
    "hallucination_burst": "#d62728",
    "omission_burst": "#ff7f0e",
    "other": "#7f7f7f",
}


def _is_telugu(ch: str) -> bool:
    return bool(ch) and TELUGU_BLOCK_START <= ord(ch) <= TELUGU_BLOCK_END


def _is_vowel_sign(ch: str) -> bool:
    return bool(ch) and TELUGU_VOWEL_SIGN_START <= ord(ch) <= TELUGU_VOWEL_SIGN_END


def _is_virama(ch: str) -> bool:
    return bool(ch) and ord(ch) == TELUGU_VIRAMA


def _is_latin_or_punct(ch: str) -> bool:
    if not ch:
        return False
    cat = unicodedata.category(ch)
    # Latin / ASCII letters, digits, punctuation
    return (
        ("LATIN" in unicodedata.name(ch, ""))
        or cat.startswith("P")
        or (ord(ch) < 128 and (ch.isascii() and (ch.isalnum() or not ch.isspace())))
    )


def classify_edit(involved_text: str) -> str:
    """Classify a string of edited characters into a single category."""
    if not involved_text:
        return "other"

    has_vowel_sign = any(_is_vowel_sign(c) for c in involved_text if c.strip())
    has_virama = any(_is_virama(c) for c in involved_text)
    has_telugu_base = any(
        _is_telugu(c) and not _is_vowel_sign(c) and not _is_virama(c) for c in involved_text
    )
    all_whitespace = all(c.isspace() for c in involved_text)
    has_latin = any(_is_latin_or_punct(c) for c in involved_text)

    if all_whitespace:
        return "whitespace"
    if has_virama:
        return "conjunct"
    if has_vowel_sign:
        return "vowel_sign"
    if has_telugu_base:
        return "base_consonant_vowel"
    if has_latin:
        return "latin_punctuation"
    return "other"


def categorize_page_errors(reference: str, hypothesis: str) -> Counter[str]:
    """Walk the SequenceMatcher opcodes; count edits by category.

    Bursts (contiguous edits >= ``BURST_THRESHOLD`` chars) collapse to one
    ``hallucination_burst`` (long insertions) or ``omission_burst`` (long
    deletions). Smaller edits classify by Unicode rule.
    """
    ref = unicodedata.normalize("NFC", reference)
    hyp = unicodedata.normalize("NFC", hypothesis)
    if not ref:
        return Counter()

    counts: Counter[str] = Counter()
    sm = SequenceMatcher(None, ref, hyp, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        deleted = ref[i1:i2]
        inserted = hyp[j1:j2]

        if tag == "delete":
            if len(deleted) >= BURST_THRESHOLD:
                counts["omission_burst"] += 1
            else:
                counts[classify_edit(deleted)] += len(deleted)
        elif tag == "insert":
            if len(inserted) >= BURST_THRESHOLD:
                counts["hallucination_burst"] += 1
            else:
                counts[classify_edit(inserted)] += len(inserted)
        elif tag == "replace":
            # Combine deletion and insertion into a single edit event
            combined = deleted + inserted
            if max(len(deleted), len(inserted)) >= BURST_THRESHOLD:
                # Treat as bursts on both sides
                if len(deleted) >= BURST_THRESHOLD:
                    counts["omission_burst"] += 1
                if len(inserted) >= BURST_THRESHOLD:
                    counts["hallucination_burst"] += 1
            else:
                counts[classify_edit(combined)] += max(len(deleted), len(inserted))
    return counts


def aggregate_per_cell(ocr_root: Path, truth_root: Path) -> pd.DataFrame:
    """Walk every cell, every page, accumulate per-category error counts."""
    rows = []
    for cell_dir in sorted(ocr_root.iterdir()):
        if not cell_dir.is_dir() or cell_dir.name.startswith("."):
            continue
        if "_" not in cell_dir.name:
            continue
        model, preprocessing = cell_dir.name.split("_", 1)
        cell_counts: Counter[str] = Counter()
        n_pages = 0
        for ocr_txt in sorted(cell_dir.rglob("*.txt")):
            book_id = ocr_txt.parent.name
            page_id = ocr_txt.stem
            truth_txt = truth_root / book_id / f"{page_id}.txt"
            if not truth_txt.exists():
                continue
            reference = truth_txt.read_text(encoding="utf-8")
            hypothesis = ocr_txt.read_text(encoding="utf-8")
            if not reference.strip():
                continue
            counts = categorize_page_errors(reference, hypothesis)
            cell_counts.update(counts)
            n_pages += 1

        for cat in CATEGORIES:
            rows.append(
                {
                    "model": model,
                    "preprocessing": preprocessing,
                    "category": cat,
                    "count": cell_counts.get(cat, 0),
                    "n_pages": n_pages,
                }
            )
        LOG.info(
            "Cell %-30s pages=%2d  total_edits=%6d",
            cell_dir.name,
            n_pages,
            sum(cell_counts.values()),
        )
    return pd.DataFrame(rows)


def plot_stacked_bars(df: pd.DataFrame, out_path: Path) -> None:
    """Stacked bar chart — one bar per cell, proportions sum to 1."""
    pivot = df.pivot_table(
        index=["model", "preprocessing"],
        columns="category",
        values="count",
        fill_value=0,
    )
    pivot = pivot[CATEGORIES]
    totals = pivot.sum(axis=1)
    proportions = pivot.div(totals, axis=0).fillna(0)

    # Taller figure so the bottom legend has room to breathe in a slide
    # context — earlier version put the legend on the right with
    # bbox_to_anchor=(1.0, 0.5) which squashed the bar labels when the
    # figure was rendered into a slide-half column.
    fig, ax = plt.subplots(figsize=(13, 7))
    bottom = pd.Series(0.0, index=proportions.index)
    for cat in CATEGORIES:
        ax.bar(
            range(len(proportions)),
            proportions[cat],
            bottom=bottom,
            color=CATEGORY_COLORS[cat],
            label=cat,
            edgecolor="white",
            linewidth=0.5,
        )
        bottom = bottom + proportions[cat]

    labels = [f"{model}\n{preprocessing}" for model, preprocessing in proportions.index]
    ax.set_xticks(range(len(proportions)))
    ax.set_xticklabels(labels, fontsize=9, rotation=20, ha="right")
    ax.set_ylabel("Share of total error edits per cell", fontsize=11)
    ax.set_title(
        "Programmatic error categorization across the eval matrix\n"
        "(per cell: 30 pages, character-level diff classification)",
        fontsize=12,
    )
    ax.set_ylim(0, 1.0)
    # Legend BELOW the chart in a single row of 8 boxes — avoids the
    # right-side legend's overlap-on-narrow-rendering problem.
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=4,
        fontsize=10,
        frameon=True,
        title="Error category",
        title_fontsize=10,
    )
    ax.grid(True, axis="y", alpha=0.3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    LOG.info("Wrote %s", out_path)


def main() -> int:
    setup_logging(name="error_analysis", level=logging.INFO)
    df = aggregate_per_cell(OCR_ROOT, TRUTH_ROOT)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    LOG.info("Wrote %s (%d rows)", OUT_CSV, len(df))
    plot_stacked_bars(df, OUT_FIG)
    LOG.info("Done.")

    # Print headline summary
    print("\n=== Per-cell error-category proportions ===")
    pivot = df.pivot_table(
        index=["model", "preprocessing"], columns="category", values="count", fill_value=0
    )[CATEGORIES]
    proportions = pivot.div(pivot.sum(axis=1), axis=0).fillna(0)
    for (model, prep), row in proportions.iterrows():
        top = row.nlargest(3)
        items = ", ".join(f"{c}={v:.1%}" for c, v in top.items())
        print(f"  {model:<10} {prep:<22}  top-3: {items}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
