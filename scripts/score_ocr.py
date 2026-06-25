#!/usr/bin/env python3
"""Score OCR outputs against ground truth and produce the CER/WER CSV.

Walks the Phase 3 OCR output tree at ``data/processed/eval_subset/``, where
each subdirectory is one ``(model, preprocessing)`` cell — for example
``gemini_raw/``, ``gemini_preprocessed/``, ``claude_raw/``,
``claude_preprocessed/``. Within each cell directory, OCR outputs live at
``<book_id>/<page_id>.txt`` mirroring the input layout.

For every OCR output file, the script pairs it with the ground-truth file
at ``data/raw/telugu-ocr/<book_id>/<page_id>.txt`` and computes CER + WER
using :mod:`src.validation.classical`. The result is written as a single
long-format CSV that Phase 5 analysis (and the final report's figures) pivot
or filter as needed.

Cells with missing OCR outputs (from rate-limit gaps in Phase 3) are scored
on whatever pages exist — the script does not fabricate rows for missing
pages. Phase 5 reports per-cell sample sizes alongside the metric values so
the reader can see partial coverage.

Usage (from the repo root, with the venv active)::

    python scripts/score_ocr.py
    python scripts/score_ocr.py --ocr-root data/processed/eval_subset --truth-root data/raw/telugu-ocr
    python scripts/score_ocr.py --out /tmp/cer_wer.csv --verbose

Standards: see ``docs/standards/python_code_standard.md`` and
``docs/standards/logging_standard.md``.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Make src/ importable when this script is invoked directly (mirrors the other
# CLIs in scripts/). Must precede the first-party import below.
sys.path.insert(0, str(REPO_ROOT))

from src.utils.logging_config import setup_logging  # noqa: E402
from src.validation.classical import compute_cer, compute_wer  # noqa: E402

DEFAULT_OCR_ROOT = REPO_ROOT / "data" / "processed" / "eval_subset"
DEFAULT_TRUTH_ROOT = REPO_ROOT / "data" / "raw" / "telugu-ocr"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "eval_subset" / "cer_wer.csv"

# Cell-directory names follow ``<model>_<preprocessing>`` so the model and
# preprocessing flag fall out of a single ``str.split("_", 1)`` call.
CELL_NAME_SEPARATOR = "_"
OUTPUT_EXTENSION = ".txt"
SCRIPT_NAME = "score_ocr"

LOG = logging.getLogger(SCRIPT_NAME)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Score Phase 3 OCR outputs against Phase 1 ground truth (CER + WER).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ocr-root",
        type=Path,
        default=DEFAULT_OCR_ROOT,
        help=(
            f"Root directory containing one subdirectory per (model, preprocessing) "
            f"cell (default: {DEFAULT_OCR_ROOT.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--truth-root",
        type=Path,
        default=DEFAULT_TRUTH_ROOT,
        help=(
            f"Root directory containing the ground-truth .txt files mirrored at "
            f"<book_id>/<page_id>.txt (default: {DEFAULT_TRUTH_ROOT.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(f"Destination CSV path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})."),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level): one line per scored page.",
    )
    return parser.parse_args(argv)


def split_cell_name(cell_dir_name: str) -> tuple[str, str]:
    """Split a cell directory name (e.g. ``gemini_preprocessed``) into ``(model, preprocessing)``.

    Args:
        cell_dir_name: The directory's base name.

    Returns:
        A 2-tuple ``(model, preprocessing)``. If the directory name does not
        contain ``CELL_NAME_SEPARATOR``, the whole name is treated as the
        model and the preprocessing field falls back to ``"unknown"``.
    """
    if CELL_NAME_SEPARATOR not in cell_dir_name:
        return cell_dir_name, "unknown"
    model, preprocessing = cell_dir_name.split(CELL_NAME_SEPARATOR, 1)
    return model, preprocessing


def score_cell(cell_dir: Path, truth_root: Path) -> list[dict[str, object]]:
    """Score every OCR output in ``cell_dir`` against its truth pair.

    Args:
        cell_dir: A ``(model, preprocessing)`` cell directory under the OCR root,
            named like ``gemini_raw`` or ``claude_preprocessed``. Children are
            expected to be book directories containing ``<page>.txt`` files.
        truth_root: Root directory containing the ground-truth files, mirrored
            at ``<book_id>/<page_id>.txt``.

    Returns:
        One row per successfully-scored OCR output. Rows for which truth is
        missing, the OCR output is empty, or :func:`compute_cer` raises are
        skipped with a WARNING-level log line.
    """
    model, preprocessing = split_cell_name(cell_dir.name)
    rows: list[dict[str, object]] = []

    ocr_files = sorted(cell_dir.rglob(f"*{OUTPUT_EXTENSION}"))
    LOG.info("Scoring cell %s: %d OCR output file(s) found.", cell_dir.name, len(ocr_files))

    for ocr_txt in ocr_files:
        # The OCR output's book is the immediate parent directory; the page id
        # is the filename stem. This mirrors the layout written by run_ocr.py.
        book_id = ocr_txt.parent.name
        page_id = ocr_txt.stem
        truth_txt = truth_root / book_id / f"{page_id}{OUTPUT_EXTENSION}"

        if not truth_txt.exists():
            LOG.warning(
                "Truth file missing for %s/%s — skipping (looked at %s).",
                book_id,
                page_id,
                truth_txt,
            )
            continue

        reference = truth_txt.read_text(encoding="utf-8")
        hypothesis = ocr_txt.read_text(encoding="utf-8")

        if not reference.strip():
            LOG.warning(
                "Empty ground truth for %s/%s — skipping (no characters to score against).",
                book_id,
                page_id,
            )
            continue

        try:
            cer_value = compute_cer(reference, hypothesis)
            wer_value = compute_wer(reference, hypothesis)
        except ValueError as exc:
            LOG.error("Could not score %s/%s: %s", book_id, page_id, exc)
            continue

        LOG.debug(
            "Scored %s/%s: cer=%.4f wer=%.4f (hyp_len=%d)",
            book_id,
            page_id,
            cer_value,
            wer_value,
            len(hypothesis),
        )
        rows.append(
            {
                "book_id": book_id,
                "page_id": page_id,
                "model": model,
                "preprocessing": preprocessing,
                "cer": cer_value,
                "wer": wer_value,
            }
        )

    return rows


def write_csv(rows: list[dict[str, object]], output: Path) -> None:
    """Write scored rows to ``output`` as a CSV with a header.

    Args:
        rows: Score rows produced by :func:`score_cell`.
        output: Destination CSV path. Parent directory is created if it does
            not exist.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["book_id", "page_id", "model", "preprocessing", "cer", "wer"]
    sorted_rows = sorted(
        rows,
        key=lambda r: (r["model"], r["preprocessing"], r["book_id"], r["page_id"]),
    )
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(row)


def summarize(rows: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, float]]:
    """Compute mean / median / p90 CER per ``(model, preprocessing)`` cell.

    Pure Python so no pandas dependency is needed at the script layer.

    Args:
        rows: Score rows produced by :func:`score_cell`.

    Returns:
        A dictionary mapping ``(model, preprocessing)`` -> {n, mean_cer,
        median_cer, p90_cer, mean_wer, median_wer}.
    """
    cells: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (str(row["model"]), str(row["preprocessing"]))
        cells.setdefault(key, []).append(row)

    summary: dict[tuple[str, str], dict[str, float]] = {}
    for key, cell_rows in cells.items():
        cers = sorted(float(r["cer"]) for r in cell_rows)
        wers = sorted(float(r["wer"]) for r in cell_rows)
        n = len(cers)
        summary[key] = {
            "n": float(n),
            "mean_cer": sum(cers) / n,
            "median_cer": cers[n // 2],
            "p90_cer": cers[min(int(n * 0.9), n - 1)],
            "mean_wer": sum(wers) / n,
            "median_wer": wers[n // 2],
        }
    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code suitable for ``sys.exit``."""
    args = parse_args(argv)

    setup_logging(
        name=SCRIPT_NAME,
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    LOG.info("OCR root:       %s", args.ocr_root)
    LOG.info("Truth root:     %s", args.truth_root)
    LOG.info("Output CSV:     %s", args.out)

    if not args.ocr_root.exists():
        LOG.error("OCR root does not exist: %s", args.ocr_root)
        return 2
    if not args.truth_root.exists():
        LOG.error("Truth root does not exist: %s", args.truth_root)
        return 2

    all_rows: list[dict[str, object]] = []
    for cell_dir in sorted(args.ocr_root.iterdir()):
        if not cell_dir.is_dir():
            continue
        # Skip dot-prefixed directories and the directory containing the CSV
        # we are about to write (so a re-run does not try to interpret the
        # CSV's parent as a cell).
        if cell_dir.name.startswith("."):
            continue
        all_rows.extend(score_cell(cell_dir, args.truth_root))

    write_csv(all_rows, args.out)

    LOG.info("=" * 60)
    LOG.info("Scoring complete.")
    LOG.info("  Total rows:  %d", len(all_rows))
    LOG.info("  CSV:         %s", args.out)

    summary = summarize(all_rows)
    if summary:
        LOG.info("-" * 60)
        LOG.info("Per-cell summary (n, mean CER, median CER, p90 CER, mean WER):")
        for (model, preprocessing), stats in sorted(summary.items()):
            LOG.info(
                "  %-10s %-13s  n=%2d  mean_cer=%.4f  median_cer=%.4f  p90_cer=%.4f  mean_wer=%.4f",
                model,
                preprocessing,
                int(stats["n"]),
                stats["mean_cer"],
                stats["median_cer"],
                stats["p90_cer"],
                stats["mean_wer"],
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
