#!/usr/bin/env python3
"""Run the preprocessing pipeline over a directory of page images.

Thin CLI wrapper around :mod:`src.preprocessing`. Walks the input directory,
runs the deskew + binarize pipeline on each image, and writes the result to a
mirrored layout under the output directory. Outputs are written as PNG to keep
the binary (single-channel) result lossless.

The run is idempotent: an image whose output already exists is skipped unless
``--overwrite`` is given. Individual stages can be disabled to support the
Phase 5 ablation study.

Usage (from the repo root, with the venv active)::

    python scripts/run_preprocessing.py
    python scripts/run_preprocessing.py --input data/raw/telugu-ocr --output data/interim/preprocessed
    python scripts/run_preprocessing.py --no-deskew
    python scripts/run_preprocessing.py --overwrite --verbose

Standards: see ``docs/standards/python_code_standard.md`` and
``docs/standards/logging_standard.md``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2

# Make src/ importable when this script is invoked directly (not via
# `python -m`). This is the simplest cross-platform way to let a CLI in
# scripts/ import from src/ without an editable pip install of the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.preprocessing import Pipeline, binarize, contrast, denoise, deskew
from src.utils.fs_walk import discover_books
from src.utils.logging_config import setup_logging

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "data" / "raw" / "telugu-ocr"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "interim" / "preprocessed"

# Recognised input image extensions, lowercase. Outputs are always PNG.
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})
OUTPUT_SUFFIX = ".png"

LOG = logging.getLogger("run_preprocessing")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the deskew + binarize preprocessing pipeline over an image directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Root directory of images to process (default: {DEFAULT_INPUT.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Root directory for outputs; mirrors the input layout "
            f"(default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--no-deskew",
        action="store_true",
        help="Disable the deskew stage.",
    )
    parser.add_argument(
        "--no-binarize",
        action="store_true",
        help="Disable the binarize stage.",
    )
    parser.add_argument(
        "--denoise",
        action="store_true",
        help="Enable the denoise stage (off by default; grayscale-preserving, fast non-local means).",
    )
    parser.add_argument(
        "--contrast",
        action="store_true",
        help="Enable the contrast stage (off by default; CLAHE, grayscale-preserving).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-process images whose output already exists (default: skip).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level): one line per page.",
    )
    return parser.parse_args(argv)


def build_pipeline() -> Pipeline:
    """Construct the default deskew -> binarize pipeline.

    Both stages default to enabled; the CLI disables individual stages per-run
    via the ``enable`` mapping passed to :meth:`Pipeline.run`, so the pipeline
    object itself is configuration-free.

    Returns:
        A :class:`~src.preprocessing.pipeline.Pipeline` with the deskew and
        binarize stages, in that order.
    """
    # Stage order: deskew first (geometric), then denoise (remove noise before
    # any subsequent processing builds on it), then contrast (grayscale-
    # preserving lift), then binarize last (destructive — turns grayscale into
    # 2-level black/white, so anything that needs gradient must run before it).
    return Pipeline(
        [
            ("deskew", deskew, True),
            ("denoise", denoise, False),
            ("contrast", contrast, False),
            ("binarize", binarize, True),
        ]
    )


def process_image(
    image_path: Path,
    output_path: Path,
    pipeline: Pipeline,
    enable: dict[str, bool],
) -> None:
    """Run the pipeline on one image and write the result.

    Args:
        image_path: Path to the input image.
        output_path: Destination path; its parent is created if needed.
        pipeline: The preprocessing pipeline to apply.
        enable: Per-stage on/off overrides passed to :meth:`Pipeline.run`.

    Raises:
        OSError: If the image cannot be read or the output cannot be written.
    """
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise OSError(f"could not read image (unsupported or corrupt): {image_path}")

    result = pipeline.run(image, enable=enable)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), result):
        raise OSError(f"could not write output image: {output_path}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code suitable for ``sys.exit``."""
    args = parse_args(argv)

    setup_logging(
        name="run_preprocessing",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    enable = {
        "deskew": not args.no_deskew,
        "denoise": args.denoise,
        "contrast": args.contrast,
        "binarize": not args.no_binarize,
    }
    pipeline = build_pipeline()

    LOG.info("Input:   %s", args.input)
    LOG.info("Output:  %s", args.output)
    LOG.info("Stages:  %s", {name: enable[name] for name in pipeline.stage_names})
    LOG.info("Mode:    %s", "overwrite" if args.overwrite else "skip-existing")

    try:
        books = discover_books(args.input, IMAGE_EXTENSIONS)
    except ValueError as exc:
        LOG.error("Cannot walk input directory: %s", exc)
        return 2

    total = sum(len(images) for _, images in books)
    if total == 0:
        LOG.warning(
            "No images found under %s (extensions: %s).", args.input, sorted(IMAGE_EXTENSIONS)
        )
        return 0

    processed = 0
    skipped = 0
    failed = 0
    # Outputs are forced to .png, so two inputs that differ only by extension
    # (e.g. page.jpg and page.png in one directory) map to the same output.
    # Track what we have written this run to turn that silent overwrite into a
    # loud warning rather than quiet data loss.
    written_this_run: dict[Path, Path] = {}

    for book_id, image_paths in books:
        LOG.info("Processing book %s: %d images", book_id, len(image_paths))
        for image_path in image_paths:
            relative = image_path.relative_to(args.input)
            output_path = (args.output / relative).with_suffix(OUTPUT_SUFFIX)

            collision = written_this_run.get(output_path)
            if collision is not None:
                LOG.warning(
                    "Output collision: %s and %s both map to %s; skipping the latter.",
                    collision,
                    image_path,
                    output_path,
                )
                failed += 1
                continue

            if output_path.exists() and not args.overwrite:
                LOG.debug("Skipping (output exists): %s", relative)
                skipped += 1
                continue

            try:
                process_image(image_path, output_path, pipeline, enable)
            except OSError as exc:
                LOG.error("Failed to process %s: %s", image_path, exc)
                failed += 1
                continue

            written_this_run[output_path] = image_path
            LOG.debug("Processed %s -> %s", relative, output_path.relative_to(args.output))
            processed += 1

    LOG.info("=" * 60)
    LOG.info("Preprocessing complete.")
    LOG.info("  Images found:    %d", total)
    LOG.info("  Processed:       %d", processed)
    LOG.info("  Skipped:         %d", skipped)
    LOG.info("  Failed:          %d", failed)
    LOG.info("  Output root:     %s", args.output)

    if failed:
        LOG.warning("%d image(s) failed to process. Review the errors above.", failed)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
