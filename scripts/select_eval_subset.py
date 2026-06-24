#!/usr/bin/env python3
"""Select the stratified evaluation subset for Phases 3-5.

Reads the human-tagged quality manifest at ``data/external/quality_tags.csv``
and draws a fixed number of pages per quality bucket — the frozen 30-page
eval subset that every Phase 3 OCR run, Phase 4 CER/WER score, and Phase 5
per-bucket analysis is computed against.

Outputs:

- ``data/external/eval_subset.csv`` — one row per selected page with bucket
  tag and image/text paths. The CSV is committed to git (small, metadata).
- ``data/external/eval_subset/<book_id>/<page_id>.jpg`` — file copy of the
  source image (NOT a symlink) so downstream tooling does not chase links.
- ``data/external/eval_subset/<book_id>/<page_id>.txt`` — file copy of the
  ground-truth text.

The selection is seed-fixed for reproducibility. Re-running with the same
``--seed`` produces the identical 30-page subset.

Standards: see ``docs/standards/python_code_standard.md`` and
``docs/standards/logging_standard.md``.
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAGS = REPO_ROOT / "data" / "external" / "quality_tags.csv"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "data" / "external" / "eval_subset.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "external" / "eval_subset"
DEFAULT_PER_BUCKET = 6
DEFAULT_SEED = 42

LOG = logging.getLogger("select_eval_subset")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Draw a stratified eval subset from the quality-tagged page pool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tags",
        type=Path,
        default=DEFAULT_TAGS,
        help=(
            f"CSV of human-tagged pages (default: "
            f"{DEFAULT_TAGS.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=(
            f"Destination eval-subset CSV (default: "
            f"{DEFAULT_OUTPUT_CSV.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            f"Destination directory for copied image+text files (default: "
            f"{DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--per-bucket",
        type=int,
        default=DEFAULT_PER_BUCKET,
        help=f"Pages to draw per bucket (default: {DEFAULT_PER_BUCKET}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for reproducibility (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level).",
    )
    return parser.parse_args(argv)


def load_tags(path: Path) -> list[dict]:
    """Load the tagged page manifest into a list of dicts."""
    if not path.exists():
        raise FileNotFoundError(f"tags file not found: {path}")
    rows: list[dict] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def stratified_sample(
    rows: list[dict],
    per_bucket: int,
    seed: int,
) -> list[dict]:
    """Draw ``per_bucket`` pages from each quality bucket, seeded for reproducibility.

    Raises:
        ValueError: If any bucket has fewer than ``per_bucket`` candidates.
    """
    rng = random.Random(seed)
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_bucket[row["quality_bucket"]].append(row)

    selected: list[dict] = []
    shortfalls: list[str] = []
    for bucket in sorted(by_bucket):
        candidates = by_bucket[bucket]
        if len(candidates) < per_bucket:
            shortfalls.append(f"{bucket}: have {len(candidates)}, need {per_bucket}")
            continue
        sample = rng.sample(candidates, per_bucket)
        LOG.info(
            "Bucket %s: drew %d pages from a pool of %d.",
            bucket,
            per_bucket,
            len(candidates),
        )
        selected.extend(sample)

    if shortfalls:
        raise ValueError(
            "Some buckets had fewer candidates than required per_bucket:\n  "
            + "\n  ".join(shortfalls)
        )

    return selected


def copy_pairs(rows: list[dict], output_dir: Path) -> None:
    """Copy each selected page's .jpg and .txt to ``output_dir/<book_id>/``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        book_dir = output_dir / row["book_id"]
        book_dir.mkdir(parents=True, exist_ok=True)
        for src_field in ("image_path", "text_path"):
            src = REPO_ROOT / row[src_field]
            if not src.exists():
                raise FileNotFoundError(f"source file missing: {src}")
            dst = book_dir / src.name
            shutil.copy2(src, dst)
            LOG.debug("Copied %s -> %s", src.relative_to(REPO_ROOT), dst.relative_to(REPO_ROOT))


def write_csv(rows: list[dict], output_csv: Path) -> None:
    """Write the eval-subset CSV with bucket tags + paths."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "book_id",
        "page_id",
        "quality_bucket",
        "has_latin_chars",
        "image_path",
        "text_path",
    ]
    sorted_rows = sorted(rows, key=lambda r: (r["quality_bucket"], r["book_id"], r["page_id"]))
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({k: row[k] for k in fieldnames})


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code suitable for ``sys.exit``."""
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    LOG.info("Tag source:       %s", args.tags)
    LOG.info("Output CSV:       %s", args.output_csv)
    LOG.info("Output directory: %s", args.output_dir)
    LOG.info("Per-bucket size:  %d", args.per_bucket)
    LOG.info("Random seed:      %d", args.seed)

    try:
        rows = load_tags(args.tags)
    except FileNotFoundError as exc:
        LOG.error(str(exc))
        return 2

    LOG.info("Loaded %d tagged pages.", len(rows))

    try:
        selected = stratified_sample(rows, args.per_bucket, args.seed)
    except ValueError as exc:
        LOG.error("Selection failed: %s", exc)
        return 2

    write_csv(selected, args.output_csv)
    copy_pairs(selected, args.output_dir)

    LOG.info("=" * 60)
    LOG.info("Eval subset frozen.")
    LOG.info("  Total pages:   %d", len(selected))
    LOG.info("  CSV:           %s", args.output_csv)
    LOG.info("  Image+text:    %s", args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
