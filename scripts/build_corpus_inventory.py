#!/usr/bin/env python3
"""Build the corpus inventory CSV from the local Telugu OCR dataset.

Thin CLI wrapper around :mod:`src.utils.corpus_inventory`. Walks the
configured source directory, pairs ``.jpg`` files with ``.txt`` files,
captures per-page metadata, writes the inventory CSV, writes a JSON Lines
mismatch report to ``logs/``, and runs a UTF-8 encoding spot check over a
small random sample of text files.

Usage (from the repo root, with the venv active)::

    python scripts/build_corpus_inventory.py
    python scripts/build_corpus_inventory.py --source data/raw/telugu-ocr --output data/external/corpus_inventory.csv
    python scripts/build_corpus_inventory.py --verbose
    python scripts/build_corpus_inventory.py --spot-check 10 --spot-check-seed 42

Standards: see ``docs/standards/python_code_standard.md`` and
``docs/standards/logging_standard.md``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Make src/ importable when this script is invoked directly (not via
# `python -m`). This is the simplest cross-platform way to let a CLI in
# scripts/ import from src/ without an editable pip install of the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.corpus_inventory import (
    spot_check_encoding,
    walk_corpus,
    write_csv,
    write_mismatch_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "data" / "raw" / "telugu-ocr"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "external" / "corpus_inventory.csv"
DEFAULT_LOG_DIR = REPO_ROOT / "logs"

LOG = logging.getLogger("build_corpus_inventory")


def _default_log_path() -> Path:
    """Build the timestamped mismatch-report path under ``logs/``."""
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_LOG_DIR / f"inventory_{ts}.jsonl"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build the corpus inventory CSV from the local Telugu OCR dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=(f"Root directory to walk (default: {DEFAULT_SOURCE.relative_to(REPO_ROOT)})."),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(f"CSV destination (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})."),
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help=(
            "JSON Lines mismatch report destination (default: "
            "logs/inventory_<UTC-timestamp>.jsonl)."
        ),
    )
    parser.add_argument(
        "--spot-check",
        type=int,
        default=5,
        metavar="N",
        help="Number of text files to randomly spot-check for UTF-8 NFC encoding (default: 5). Pass 0 to skip.",
    )
    parser.add_argument(
        "--spot-check-seed",
        type=int,
        default=None,
        help="Random seed for the spot-check sample. Omit for non-deterministic sampling.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level).",
    )
    return parser.parse_args(argv)


def _format_bytes(n: int) -> str:
    """Render a byte count as a short human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n //= 1024
    return f"{n} TB"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code suitable for ``sys.exit``."""
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_path = args.log or _default_log_path()

    LOG.info("Source:           %s", args.source)
    LOG.info("Inventory CSV:    %s", args.output)
    LOG.info("Mismatch report:  %s", log_path)

    try:
        rows, mismatches = walk_corpus(args.source)
    except ValueError as exc:
        LOG.error("Cannot walk corpus: %s", exc)
        return 2

    # Write paths relative to the repo root so the CSV is portable between
    # machines (Eric and Rauf will have different absolute paths).
    write_csv(rows, args.output, relative_to=REPO_ROOT)
    write_mismatch_report(mismatches, log_path)

    # End-of-run summary.
    book_ids = sorted({r.book_id for r in rows})
    total_image_bytes = sum(r.image_bytes for r in rows)
    total_text_bytes = sum(r.text_bytes for r in rows)

    LOG.info("=" * 60)
    LOG.info("Inventory complete.")
    LOG.info("  Books:           %d", len(book_ids))
    LOG.info("  Paired pages:    %d", len(rows))
    LOG.info("  Mismatches:      %d", len(mismatches))
    LOG.info("  Total image MB:  %s", _format_bytes(total_image_bytes))
    LOG.info("  Total text MB:   %s", _format_bytes(total_text_bytes))
    LOG.info("  CSV:             %s", args.output)
    LOG.info("  Mismatch log:    %s", log_path)

    if mismatches:
        LOG.warning(
            "%d paired-file mismatches recorded. Review %s.",
            len(mismatches),
            log_path,
        )

    # Spot check.
    if args.spot_check > 0:
        text_paths = [r.text_path for r in rows]
        LOG.info("-" * 60)
        LOG.info(
            "Spot-checking %d random text files for UTF-8 NFC encoding...",
            min(args.spot_check, len(text_paths)),
        )
        results = spot_check_encoding(
            text_paths,
            sample_size=args.spot_check,
            seed=args.spot_check_seed,
        )
        for r in results:
            if r["decoded"]:
                LOG.info(
                    "  OK   %s | %d chars | nfc=%s | preview=%r",
                    r["path"],
                    r["char_count"],
                    r["is_nfc"],
                    r["preview"],
                )
            else:
                LOG.warning("  FAIL %s | %s", r["path"], r["error"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
