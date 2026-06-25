#!/usr/bin/env python3
"""Batch-run LLM fluency scoring over a directory of OCR outputs.

Mirrors the shape of ``scripts/run_ocr.py``: walks an OCR output tree
produced by ``run_ocr.py``, scores every ``.txt`` with a Claude fluency
judge (Method A from Phase 4), and writes per-page results to a CSV plus a
manifest.jsonl. Idempotent: a page whose score already exists in the
output CSV is skipped on a resumed run.

The fluency rating is an integer 1-5 (1 = mostly gibberish, 5 = fluent
Telugu prose) plus a one-sentence reason and up to ~3 error examples. See
``src.validation.llm_fluency`` for the prompt and the JSON-strict parse.

Usage (from the repo root, with the venv active and ``.env`` populated)::

    python scripts/run_fluency.py
    python scripts/run_fluency.py --ocr-root data/processed/eval_subset --out data/processed/eval_subset/fluency.csv
    python scripts/run_fluency.py --ocr-root data/processed/submission/gemini --out data/processed/submission/gemini_fluency.csv

Standards: see ``docs/standards/python_code_standard.md``,
``docs/standards/logging_standard.md``, and
``docs/standards/credential_handling_standard.md``.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.logging_config import setup_logging  # noqa: E402
from src.validation.llm_fluency import (  # noqa: E402
    ClaudeFluencyJudge,
    FluencyJudgeError,
)

DEFAULT_OCR_ROOT = REPO_ROOT / "data" / "processed" / "eval_subset"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "eval_subset" / "fluency.csv"
OUTPUT_EXTENSION = ".txt"
SCRIPT_NAME = "run_fluency"
CELL_NAME_SEPARATOR = "_"

LOG = logging.getLogger(SCRIPT_NAME)

CSV_FIELDNAMES = [
    "book_id",
    "page_id",
    "model",
    "preprocessing",
    "fluency_rating",
    "fluency_reason",
    "latency_ms",
    "judge_model",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch-score Phase 3 OCR outputs for fluency via a Claude judge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ocr-root",
        type=Path,
        default=DEFAULT_OCR_ROOT,
        help=(
            f"Root directory containing one (model, preprocessing) cell directory "
            f"per child (default: {DEFAULT_OCR_ROOT.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(f"Destination CSV path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})."),
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default="claude-sonnet-4-6",
        help="Claude model name for the fluency judge (default: claude-sonnet-4-6).",
    )
    parser.add_argument(
        "--single-cell",
        action="store_true",
        help=(
            "Treat --ocr-root as a single cell directory (book subdirs directly under "
            "it), not a tree of cells. Used for the submission-sample run where the "
            "OCR root IS the cell."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-score pages already in the output CSV (default: skip).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level): one line per scored page.",
    )
    return parser.parse_args(argv)


def split_cell_name(cell_dir_name: str) -> tuple[str, str]:
    """Split a cell directory name into ``(model, preprocessing)``."""
    if CELL_NAME_SEPARATOR not in cell_dir_name:
        return cell_dir_name, "unknown"
    model, preprocessing = cell_dir_name.split(CELL_NAME_SEPARATOR, 1)
    return model, preprocessing


def _load_existing(out_path: Path) -> set[tuple[str, str, str, str]]:
    """Return the (book_id, page_id, model, preprocessing) tuples already scored."""
    if not out_path.exists():
        return set()
    existing: set[tuple[str, str, str, str]] = set()
    with out_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            existing.add(
                (
                    row["book_id"],
                    row["page_id"],
                    row["model"],
                    row["preprocessing"],
                )
            )
    return existing


def score_cell(
    cell_dir: Path,
    judge: ClaudeFluencyJudge,
    existing: set[tuple[str, str, str, str]],
    model_override: str | None = None,
    preprocessing_override: str | None = None,
) -> list[dict[str, object]]:
    """Score every OCR output in ``cell_dir``."""
    if model_override is None or preprocessing_override is None:
        model, preprocessing = split_cell_name(cell_dir.name)
    else:
        model, preprocessing = model_override, preprocessing_override

    rows: list[dict[str, object]] = []
    ocr_files = sorted(cell_dir.rglob(f"*{OUTPUT_EXTENSION}"))
    LOG.info("Scoring cell %s: %d OCR output file(s).", cell_dir.name, len(ocr_files))

    for i, ocr_txt in enumerate(ocr_files, start=1):
        book_id = ocr_txt.parent.name
        page_id = ocr_txt.stem
        key = (book_id, page_id, model, preprocessing)
        if key in existing:
            LOG.debug(
                "Skipping already-scored %s/%s (%s, %s)", book_id, page_id, model, preprocessing
            )
            continue

        text = ocr_txt.read_text(encoding="utf-8")
        if not text.strip():
            LOG.info(
                "%d/%d: %s/%s (%s, %s) — empty OCR output; recording rating=1 directly.",
                i,
                len(ocr_files),
                book_id,
                page_id,
                model,
                preprocessing,
            )
            rows.append(
                {
                    "book_id": book_id,
                    "page_id": page_id,
                    "model": model,
                    "preprocessing": preprocessing,
                    "fluency_rating": 1,
                    "fluency_reason": "Empty OCR output (no text to evaluate).",
                    "latency_ms": 0.0,
                    "judge_model": judge.model_name,
                }
            )
            continue

        try:
            result = judge.score(text)
        except FluencyJudgeError as exc:
            LOG.warning(
                "%d/%d: %s/%s (%s, %s) — judge returned malformed JSON: %s",
                i,
                len(ocr_files),
                book_id,
                page_id,
                model,
                preprocessing,
                exc,
            )
            continue
        except Exception as exc:
            LOG.error(
                "%d/%d: %s/%s (%s, %s) — judge call failed: %s",
                i,
                len(ocr_files),
                book_id,
                page_id,
                model,
                preprocessing,
                exc,
            )
            continue

        LOG.info(
            "%d/%d: %s/%s (%s, %s) — rating=%d (%.0fms): %s",
            i,
            len(ocr_files),
            book_id,
            page_id,
            model,
            preprocessing,
            result.rating,
            result.latency_ms,
            result.reason[:80],
        )
        rows.append(
            {
                "book_id": book_id,
                "page_id": page_id,
                "model": model,
                "preprocessing": preprocessing,
                "fluency_rating": result.rating,
                "fluency_reason": result.reason,
                "latency_ms": result.latency_ms,
                "judge_model": result.model_name,
            }
        )

    return rows


def _append_or_write_csv(rows: list[dict[str, object]], out_path: Path) -> None:
    """Append rows to ``out_path`` (creating header if file is new)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = out_path.exists()
    with out_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    load_dotenv()
    setup_logging(
        name=SCRIPT_NAME,
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    LOG.info("OCR root:       %s", args.ocr_root)
    LOG.info("Output CSV:     %s", args.out)
    LOG.info("Judge model:    %s", args.judge_model)
    LOG.info("Single-cell:    %s", args.single_cell)

    if not args.ocr_root.exists():
        LOG.error("OCR root does not exist: %s", args.ocr_root)
        return 2

    if args.overwrite and args.out.exists():
        LOG.warning("--overwrite set; deleting existing %s", args.out)
        args.out.unlink()

    existing = _load_existing(args.out)
    LOG.info("Already-scored rows on disk: %d (will be skipped unless --overwrite).", len(existing))

    judge = ClaudeFluencyJudge(model_name=args.judge_model)

    all_rows: list[dict[str, object]] = []
    if args.single_cell:
        # OCR root IS the cell — used for the submission sample.
        rows = score_cell(
            args.ocr_root,
            judge,
            existing,
            model_override="gemini",
            preprocessing_override="raw",
        )
        all_rows.extend(rows)
        # Flush after each cell so a long run can be resumed.
        if rows:
            _append_or_write_csv(rows, args.out)
    else:
        for cell_dir in sorted(args.ocr_root.iterdir()):
            if not cell_dir.is_dir() or cell_dir.name.startswith("."):
                continue
            rows = score_cell(cell_dir, judge, existing)
            all_rows.extend(rows)
            if rows:
                _append_or_write_csv(rows, args.out)

    LOG.info("=" * 60)
    LOG.info("Fluency scoring complete.")
    LOG.info("  New rows written: %d", len(all_rows))
    LOG.info("  Output CSV:       %s", args.out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
