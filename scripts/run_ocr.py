#!/usr/bin/env python3
"""Batch-run an OCR adapter over a directory of page images.

Thin CLI wrapper around :mod:`src.ocr`. Walks the input directory for ``.jpg``
images, runs the chosen adapter on each, writes one ``.txt`` per page mirroring
the input layout, and writes a ``manifest.jsonl`` recording per-page latency,
text length, and any error.

The run is idempotent: a page whose output ``.txt`` already exists is skipped
unless ``--overwrite`` is given. A single page failing does **not** abort the
batch — the error is logged and recorded in the manifest's ``error`` field, and
the run continues. The manifest records every page that has output on disk: a
freshly processed page carries its ``latency_ms`` and ``text_length``; a skipped
page is recorded with ``"skipped": true`` and a null ``latency_ms`` (so a
resumed run never silently produces an empty manifest); a failed page carries an
``error`` field.

Usage (from the repo root, with the venv active and ``.env`` populated)::

    python scripts/run_ocr.py --model gemini
    python scripts/run_ocr.py --model gemini --input data/external/eval_subset --output data/processed/eval_subset/gemini_raw
    python scripts/run_ocr.py --model gemini --overwrite --verbose

Standards: see ``docs/standards/python_code_standard.md``,
``docs/standards/logging_standard.md``, and
``docs/standards/credential_handling_standard.md``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Make src/ importable when this script is invoked directly (not via
# `python -m`). This is the simplest cross-platform way to let a CLI in
# scripts/ import from src/ without an editable pip install of the project.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ocr import OCRAdapter
from src.utils.fs_walk import discover_books
from src.utils.logging_config import setup_logging

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "data" / "external" / "eval_subset"

# Recognised input image extension, lowercase. The corpus is .jpg throughout.
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg"})
OUTPUT_SUFFIX = ".txt"
MANIFEST_NAME = "manifest.jsonl"

# Adapter identifiers accepted by --model. "gemini" and "claude" are
# implemented; "tesseract" is wired into the CLI so the future adapter has a
# home, but raises until Rauf implements it (Task 4 in the phase doc).
MODEL_GEMINI = "gemini"
MODEL_CLAUDE = "claude"
MODEL_TESSERACT = "tesseract"
MODEL_CHOICES = (MODEL_GEMINI, MODEL_CLAUDE, MODEL_TESSERACT)

LOG = logging.getLogger("run_ocr")


def build_adapter(model: str) -> OCRAdapter:
    """Construct the OCR adapter for the given ``--model`` choice.

    Args:
        model: One of :data:`MODEL_CHOICES`.

    Returns:
        A ready-to-use adapter satisfying :class:`~src.ocr.base.OCRAdapter`.

    Raises:
        NotImplementedError: For ``tesseract`` — its adapter is implemented in a
            separate task (see ``docs/development/phase_3_ocr_pipeline.md``
            Task 4). The choice is accepted so the CLI is ready for it.
        ValueError: For an unknown model identifier.
    """
    if model == MODEL_GEMINI:
        # Imported lazily so other models (and `--help`) do not require the
        # Gemini SDK or a GEMINI_API_KEY to be present.
        from src.ocr import GeminiAdapter

        return GeminiAdapter()
    if model == MODEL_CLAUDE:
        # Imported lazily so other models (and `--help`) do not require the
        # anthropic SDK or an ANTHROPIC_API_KEY to be present.
        from src.ocr import ClaudeAdapter

        return ClaudeAdapter()
    if model == MODEL_TESSERACT:
        raise NotImplementedError(
            "The Tesseract adapter is not implemented in this PR. See "
            "docs/development/phase_3_ocr_pipeline.md Task 4 (Rauf): implement "
            "src/ocr/tesseract.py against the src.ocr.base.OCRAdapter contract, "
            "then register it here."
        )
    raise ValueError(f"unknown model: {model!r} (choices: {', '.join(MODEL_CHOICES)})")


def default_output_dir(model: str) -> Path:
    """Return the default output directory for a model: ``<model>_raw``."""
    return REPO_ROOT / "data" / "processed" / "eval_subset" / f"{model}_raw"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch-run an OCR adapter over a directory of page images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=MODEL_CHOICES,
        help="OCR backend to run. 'gemini' and 'claude' are implemented; 'tesseract' is not yet.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=(
            "Root directory of images to OCR; walked recursively for .jpg files "
            f"(default: {DEFAULT_INPUT.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Root directory for output .txt files and manifest.jsonl; mirrors "
            "the input layout (default: data/processed/eval_subset/<model>_raw)."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-process pages whose output .txt already exists (default: skip).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level): one line per page.",
    )
    return parser.parse_args(argv)


def _write_manifest(manifest_path: Path, records: list[dict]) -> None:
    """Write the per-page manifest as JSON Lines.

    Args:
        manifest_path: Destination ``manifest.jsonl`` path. Parent created if
            needed.
        records: One dict per processed page.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code suitable for ``sys.exit``."""
    args = parse_args(argv)

    # Load .env so a populated key file works without the user exporting the
    # variable into their shell first (see credential_handling_standard.md).
    # No-op if there is no .env; the adapter still fails fast if the key is
    # absent from the environment after loading.
    load_dotenv()

    setup_logging(
        name="run_ocr",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    output_root = args.output or default_output_dir(args.model)

    LOG.info("Model:   %s", args.model)
    LOG.info("Input:   %s", args.input)
    LOG.info("Output:  %s", output_root)
    LOG.info("Mode:    %s", "overwrite" if args.overwrite else "skip-existing")

    try:
        books = discover_books(args.input, IMAGE_EXTENSIONS)
    except ValueError as exc:
        LOG.error("Cannot walk input directory: %s", exc)
        return 2

    total = sum(len(images) for _, images in books)
    if total == 0:
        LOG.warning("No .jpg images found under %s.", args.input)
        return 0

    try:
        adapter = build_adapter(args.model)
    except (NotImplementedError, RuntimeError, ValueError) as exc:
        # NotImplementedError: tesseract not wired yet. RuntimeError: missing
        # GEMINI_API_KEY. ValueError: unknown model. All are configuration
        # problems that should abort before any page is processed.
        LOG.error("Cannot build adapter: %s", exc)
        return 2

    # The adapter's own identifier (e.g. "gemini-1.5-flash") is the single
    # source of truth for the manifest's "model" field on every record —
    # processed, skipped, and failed — so a downstream grouping by model never
    # splits one run across the CLI choice string and the resolved model name.
    model_name = adapter.model_name

    records: list[dict] = []
    processed = 0
    skipped = 0
    failed = 0

    for book_id, image_paths in books:
        LOG.info("Processing book %s: %d pages", book_id, len(image_paths))
        for image_path in image_paths:
            relative = image_path.relative_to(args.input)
            output_path = (output_root / relative).with_suffix(OUTPUT_SUFFIX)
            page_id = image_path.stem

            if output_path.exists() and not args.overwrite:
                # Still record the page so the manifest reflects every output on
                # disk, not just pages processed this run. Without this, a
                # skip-only rerun would write an empty manifest and a downstream
                # reader would conclude nothing had ever been OCR'd.
                LOG.debug("Skipping (output exists): %s", relative.as_posix())
                try:
                    existing_length: int | None = len(output_path.read_text(encoding="utf-8"))
                except OSError as exc:
                    LOG.warning("Could not read existing output %s: %s", output_path, exc)
                    existing_length = None
                records.append(
                    {
                        "page_id": page_id,
                        "book_id": book_id,
                        "model": model_name,
                        "latency_ms": None,
                        "text_length": existing_length,
                        "skipped": True,
                    }
                )
                skipped += 1
                continue

            try:
                result = adapter.ocr(image_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(result.text, encoding="utf-8")
            except Exception as exc:
                # Per the phase doc: a single page failure must not abort the
                # batch. This covers both the OCR call and the output write, so
                # a transient disk/permission error on one page is recorded and
                # the run continues rather than losing the whole batch. Log with
                # full context and record it in the manifest so downstream code
                # can find the failures; then continue.
                LOG.error("OCR failed for %s: %s", relative.as_posix(), exc)
                records.append(
                    {
                        "page_id": page_id,
                        "book_id": book_id,
                        "model": model_name,
                        "latency_ms": None,
                        # None (not 0) so a downstream reader does not confuse a
                        # failed page with a genuinely blank one that produced a
                        # zero-length file; the "error" field marks the failure.
                        "text_length": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                failed += 1
                continue

            if not result.text:
                LOG.warning("Empty OCR output for %s (blank page or refusal).", relative.as_posix())

            LOG.debug(
                "OCR ok %s: %d chars, %.0f ms",
                relative.as_posix(),
                len(result.text),
                result.latency_ms,
            )
            records.append(
                {
                    "page_id": page_id,
                    "book_id": book_id,
                    "model": model_name,
                    "latency_ms": round(result.latency_ms, 1),
                    "text_length": len(result.text),
                }
            )
            processed += 1

    manifest_path = output_root / MANIFEST_NAME
    _write_manifest(manifest_path, records)

    LOG.info("=" * 60)
    LOG.info("OCR run complete.")
    LOG.info("  Pages found:   %d", total)
    LOG.info("  Processed:     %d", processed)
    LOG.info("  Skipped:       %d", skipped)
    LOG.info("  Failed:        %d", failed)
    LOG.info("  Manifest:      %s", manifest_path)

    if failed:
        LOG.warning("%d page(s) failed. See the 'error' field in %s.", failed, manifest_path)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
