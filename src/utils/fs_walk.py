"""Shared filesystem-walking utilities for batch-pipeline CLIs.

The OCR and preprocessing batch runners both group input images by book
directory in the exact same way. This module is the single source of truth
for that walk, called from both ``scripts/run_ocr.py`` and
``scripts/run_preprocessing.py`` (and any future per-page batch script).
"""

from __future__ import annotations

from pathlib import Path


def discover_books(
    input_root: Path,
    image_extensions: frozenset[str],
) -> list[tuple[str, list[Path]]]:
    """Group input images by book directory for per-book progress logging.

    Each immediate subdirectory of ``input_root`` is treated as one book and
    walked recursively for images matching ``image_extensions``. Images
    directly under ``input_root`` (i.e. not nested in a book directory) are
    grouped under the synthetic book id ``"."``. Results are sorted for
    deterministic processing order.

    Hidden directories (names starting with ``.``) are skipped. This matches
    the dot-prefix normalization in ``scripts/download_dataset.py`` — any
    book directories we care about have already had their leading dots
    stripped at download time.

    Args:
        input_root: Root directory to walk.
        image_extensions: A frozenset of lowercase file extensions to recognise
            as images, e.g. ``frozenset({".jpg"})`` or
            ``frozenset({".jpg", ".jpeg", ".png"})``. Extensions must include
            the leading dot.

    Returns:
        A list of ``(book_id, image_paths)`` pairs, sorted by book id, with
        image paths sorted within each book. Books with no matching images
        are omitted.

    Raises:
        ValueError: If ``input_root`` does not exist or is not a directory.
    """
    if not input_root.exists():
        raise ValueError(f"input does not exist: {input_root}")
    if not input_root.is_dir():
        raise ValueError(f"input is not a directory: {input_root}")

    def images_in(paths: list[Path]) -> list[Path]:
        return sorted(p for p in paths if p.is_file() and p.suffix.lower() in image_extensions)

    books: list[tuple[str, list[Path]]] = []

    root_images = images_in(list(input_root.iterdir()))
    if root_images:
        books.append((".", root_images))

    for child in sorted(input_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        book_images = images_in(list(child.rglob("*")))
        if book_images:
            books.append((child.name, book_images))

    return books
