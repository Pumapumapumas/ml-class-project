"""Corpus inventory builder.

Walks a Telugu OCR dataset directory, pairs each ``.jpg`` page image with its
matching ``.txt`` ground-truth file, captures per-page metadata, and produces
an inventory CSV consumed by downstream Phase 1 tasks (statistics, taxonomy,
eval-subset selection) and by all subsequent phases that need to look up the
canonical list of pages.

The library exposes pure functions that operate on filesystem inputs and
return plain Python data structures. A thin CLI wrapper lives at
``scripts/build_corpus_inventory.py``.

See ``docs/development/phase_1_corpus_characterization.md`` Task 1 for the
role this module plays in the project.
"""

from __future__ import annotations

import csv
import json
import logging
import random
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

LOG = logging.getLogger(__name__)

# Recognised image extensions, lowercase. The HuggingFace dataset uses .jpg
# throughout; we list the set explicitly so we don't accidentally pick up
# unexpected formats during a walk.
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg"})
TEXT_EXTENSION: str = ".txt"

# Sentinel reasons for the mismatch report.
REASON_MISSING_TEXT = "missing_text"
REASON_MISSING_IMAGE = "missing_image"


@dataclass(frozen=True)
class InventoryRow:
    """One row in the corpus inventory CSV.

    Attributes:
        book_id: Top-level book directory name (normalized; see
            ``scripts/download_dataset.py`` for the leading-dot normalization).
        page_id: Image and text filename stem (e.g., ``page_0001``).
        image_path: Absolute or repo-relative path to the page image.
        text_path: Absolute or repo-relative path to the ground-truth text.
        image_bytes: File size of the image in bytes.
        text_bytes: File size of the ground-truth text in bytes.
        image_width: Image width in pixels.
        image_height: Image height in pixels.
    """

    book_id: str
    page_id: str
    image_path: Path
    text_path: Path
    image_bytes: int
    text_bytes: int
    image_width: int
    image_height: int


@dataclass(frozen=True)
class MismatchedFile:
    """A file without a matching pair.

    Attributes:
        book_id: Top-level book directory the file belongs to.
        page_id: Filename stem.
        path: Path to the unpaired file on disk.
        reason: ``missing_text`` (we have a .jpg without a .txt) or
            ``missing_image`` (we have a .txt without a .jpg).
    """

    book_id: str
    page_id: str
    path: Path
    reason: str


def pair_files(
    book_dir: Path,
) -> tuple[dict[str, tuple[Path, Path]], list[MismatchedFile]]:
    """Pair ``.jpg`` files with ``.txt`` files by filename stem.

    Both sides of the pair are scoped to the same book directory. Files
    with no partner are reported as mismatches rather than silently
    dropped.

    Args:
        book_dir: Directory representing one book; expected to contain
            ``<page>.jpg`` and ``<page>.txt`` files at the top level.

    Returns:
        A tuple ``(paired, mismatches)`` where:

        - ``paired`` maps a page_id (filename stem) to a 2-tuple
          ``(image_path, text_path)``.
        - ``mismatches`` lists every file in the directory that lacks a
          partner, with a reason tag.

    Raises:
        ValueError: If ``book_dir`` does not exist or is not a directory.
    """
    if not book_dir.exists():
        raise ValueError(f"book_dir does not exist: {book_dir}")
    if not book_dir.is_dir():
        raise ValueError(f"book_dir is not a directory: {book_dir}")

    book_id = book_dir.name

    images: dict[str, Path] = {}
    texts: dict[str, Path] = {}

    for entry in book_dir.iterdir():
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        stem = entry.stem
        if suffix in IMAGE_EXTENSIONS:
            images[stem] = entry
        elif suffix == TEXT_EXTENSION:
            texts[stem] = entry

    paired: dict[str, tuple[Path, Path]] = {}
    mismatches: list[MismatchedFile] = []

    image_stems = set(images)
    text_stems = set(texts)

    for stem in sorted(image_stems & text_stems):
        paired[stem] = (images[stem], texts[stem])

    for stem in sorted(image_stems - text_stems):
        mismatches.append(
            MismatchedFile(
                book_id=book_id,
                page_id=stem,
                path=images[stem],
                reason=REASON_MISSING_TEXT,
            )
        )

    for stem in sorted(text_stems - image_stems):
        mismatches.append(
            MismatchedFile(
                book_id=book_id,
                page_id=stem,
                path=texts[stem],
                reason=REASON_MISSING_IMAGE,
            )
        )

    return paired, mismatches


def extract_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Return ``(width, height)`` in pixels for an image file.

    Uses Pillow's lazy ``Image.open``; the image is closed automatically.
    Raises a clear error if the file is not a readable image.

    Args:
        image_path: Path to a readable image file.

    Returns:
        ``(width, height)`` in pixels.

    Raises:
        OSError: If the file cannot be opened or is not a valid image.
    """
    with Image.open(image_path) as img:
        return img.size  # PIL returns (width, height)


def walk_corpus(
    source: Path,
) -> tuple[list[InventoryRow], list[MismatchedFile]]:
    """Walk every book directory under ``source`` and build the inventory.

    Iterates the immediate children of ``source``. Each child directory is
    treated as one book. Files at the top level of ``source`` itself are
    ignored. Per-book pairing and dimension extraction is delegated to
    ``pair_files`` and ``extract_image_dimensions``.

    Results are returned in deterministic order: sorted by ``book_id``
    then ``page_id``.

    Args:
        source: Root directory containing book subdirectories.

    Returns:
        ``(rows, mismatches)`` — a list of paired inventory rows and a
        list of every unpaired file across all books.

    Raises:
        ValueError: If ``source`` does not exist or is not a directory.
    """
    if not source.exists():
        raise ValueError(f"source does not exist: {source}")
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")

    rows: list[InventoryRow] = []
    mismatches: list[MismatchedFile] = []

    for book_dir in sorted(source.iterdir()):
        if not book_dir.is_dir():
            continue
        # Skip the HuggingFace internal cache and any other hidden dir.
        if book_dir.name.startswith("."):
            LOG.debug("Skipping hidden directory: %s", book_dir.name)
            continue

        book_id = book_dir.name
        paired, book_mismatches = pair_files(book_dir)
        mismatches.extend(book_mismatches)

        LOG.info(
            "Inventorying book %s: %d paired pages, %d mismatches",
            book_id,
            len(paired),
            len(book_mismatches),
        )

        for page_id in sorted(paired):
            image_path, text_path = paired[page_id]
            try:
                width, height = extract_image_dimensions(image_path)
            except OSError as exc:
                LOG.error(
                    "Failed to read image dimensions for %s: %s",
                    image_path,
                    exc,
                )
                # Treat dimension-read failure as a mismatch so the page
                # does not slip into the inventory without dimensions.
                mismatches.append(
                    MismatchedFile(
                        book_id=book_id,
                        page_id=page_id,
                        path=image_path,
                        reason=f"image_unreadable: {exc}",
                    )
                )
                continue

            rows.append(
                InventoryRow(
                    book_id=book_id,
                    page_id=page_id,
                    image_path=image_path,
                    text_path=text_path,
                    image_bytes=image_path.stat().st_size,
                    text_bytes=text_path.stat().st_size,
                    image_width=width,
                    image_height=height,
                )
            )

    return rows, mismatches


def write_csv(
    rows: list[InventoryRow],
    output: Path,
    relative_to: Path | None = None,
) -> None:
    """Write the inventory to a CSV file.

    The CSV has a header row matching the ``InventoryRow`` field names.

    Args:
        rows: Inventory rows to write.
        output: Destination CSV path. Parent directory is created if
            it does not exist.
        relative_to: If provided, image and text paths are rewritten as
            paths relative to this directory before being written. This
            keeps the CSV portable between machines — anyone who clones
            the repo and runs from the same root sees the same paths.
            If a row's path is not under ``relative_to``, the absolute
            path is written instead (and a debug log is emitted).
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "book_id",
        "page_id",
        "image_path",
        "text_path",
        "image_bytes",
        "text_bytes",
        "image_width",
        "image_height",
    ]
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            record = asdict(row)
            record["image_path"] = _format_path(row.image_path, relative_to)
            record["text_path"] = _format_path(row.text_path, relative_to)
            writer.writerow(record)


def _format_path(path: Path, relative_to: Path | None) -> str:
    """Render ``path`` as a string, made relative to ``relative_to`` if possible."""
    if relative_to is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(relative_to.resolve()))
    except ValueError:
        LOG.debug("Path %s is not under %s; writing absolute.", path, relative_to)
        return str(path)


def write_mismatch_report(
    mismatches: list[MismatchedFile],
    log_path: Path,
) -> None:
    """Write the mismatch report to a JSON Lines file.

    Each line is a self-contained JSON object with fields ``timestamp``,
    ``book_id``, ``page_id``, ``path``, ``reason``. The file is created
    even if ``mismatches`` is empty, so the presence of a zero-byte file
    is a positive signal that the pairing invariant held.

    Args:
        mismatches: List of mismatched files.
        log_path: Destination JSONL path. Parent directory is created if
            it does not exist.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    with log_path.open("w", encoding="utf-8") as fh:
        for m in mismatches:
            fh.write(
                json.dumps(
                    {
                        "timestamp": now,
                        "book_id": m.book_id,
                        "page_id": m.page_id,
                        "path": str(m.path),
                        "reason": m.reason,
                    }
                )
                + "\n"
            )


def spot_check_encoding(
    text_paths: list[Path],
    sample_size: int = 5,
    seed: int | None = None,
) -> list[dict]:
    """Sample text files and inspect their encoding and basic plausibility.

    For each sampled file, opens it as UTF-8 and reports:

    - Whether it decoded successfully.
    - Whether it is in NFC form (the canonical Unicode form we target).
    - Length in characters.
    - The first 30 characters (for human eyeballing).

    Files that cannot be decoded are reported with ``decoded=False`` and
    an ``error`` field. The function never raises on a single bad file —
    spot-check is diagnostic, not a hard gate.

    Args:
        text_paths: Pool of text files to sample from.
        sample_size: Number of files to draw without replacement. If
            larger than the pool, the entire pool is checked.
        seed: Optional seed for deterministic sampling.

    Returns:
        A list of result dictionaries, one per sampled file.
    """
    if not text_paths:
        return []

    rng = random.Random(seed)
    n = min(sample_size, len(text_paths))
    sample = rng.sample(text_paths, n)

    results: list[dict] = []
    for path in sample:
        result: dict = {"path": str(path)}
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            normalized_nfc = unicodedata.normalize("NFC", text)
            result.update(
                {
                    "decoded": True,
                    "is_nfc": text == normalized_nfc,
                    "char_count": len(text),
                    "preview": text[:30],
                }
            )
        except (OSError, UnicodeDecodeError) as exc:
            result.update({"decoded": False, "error": str(exc)})
        results.append(result)

    return results
