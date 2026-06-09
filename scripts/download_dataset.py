"""Download a configurable subset of the Telugu OCR dataset from HuggingFace.

The dataset is ``AlbertoChestnut/telugu-ocr`` — paired ``.jpg`` (scanned page)
and ``.txt`` (ground-truth Unicode) files organized by book directory. The full
corpus is approximately 13 GB; the default ``--subset 5`` pulls roughly the
first 5 books (~500 MB) for development iteration.

Usage (from the repo root, with the venv active)::

    python scripts/download_dataset.py --subset 5      # ~500 MB, 5 books
    python scripts/download_dataset.py --full          # ~13 GB, full corpus
    python scripts/download_dataset.py --list          # list available books, do not download

Output lands under ``data/raw/telugu-ocr/<book_id>/`` with the dataset's native
directory layout preserved.

See ``docs/development/phase_1_corpus_characterization.md`` for the role this
data plays in the project.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASET_REPO_ID = "AlbertoChestnut/telugu-ocr"
DATASET_REPO_TYPE = "dataset"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET_DIR = REPO_ROOT / "data" / "raw" / "telugu-ocr"
DEFAULT_HF_CACHE = REPO_ROOT / "data" / "external" / "hf_cache"

LOG = logging.getLogger("download_dataset")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the Telugu OCR dataset (paired .jpg + .txt) from HuggingFace.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--subset",
        type=int,
        metavar="N",
        help="Download the first N books (~100 MB per book on average).",
    )
    group.add_argument(
        "--full",
        action="store_true",
        help="Download the entire corpus (~13 GB).",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List available books without downloading any data.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET_DIR,
        help=f"Local directory to write the downloaded data to (default: {DEFAULT_TARGET_DIR.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_HF_CACHE,
        help=f"HuggingFace cache directory (default: {DEFAULT_HF_CACHE.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (DEBUG level).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def configure_environment(cache_dir: Path) -> None:
    """Point HuggingFace caches at the project-local directory per environment_standard.md."""
    cache_dir = cache_dir.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache_dir)
    os.environ["TRANSFORMERS_CACHE"] = str(cache_dir / "transformers")
    LOG.debug("HF_HOME=%s", cache_dir)


def list_book_directories(api) -> list[str]:
    """Return the sorted list of top-level book directories in the dataset.

    HuggingFace stores datasets as a flat list of files; we infer book
    directories by taking the first path component of each file.
    """
    LOG.info("Listing files in %s ...", DATASET_REPO_ID)
    files = api.list_repo_files(DATASET_REPO_ID, repo_type=DATASET_REPO_TYPE)
    # Each path looks like "<book_id>/<page>.jpg" or "<book_id>/<page>.txt".
    book_ids = sorted({path.split("/", 1)[0] for path in files if "/" in path})
    LOG.info("Dataset contains %d top-level entries.", len(book_ids))
    return book_ids


def select_subset_patterns(book_ids: list[str], subset_n: int) -> list[str]:
    """Build glob patterns for snapshot_download that match the first N books."""
    chosen = book_ids[:subset_n]
    if len(chosen) < subset_n:
        LOG.warning(
            "Requested %d books but dataset only has %d — pulling all available.",
            subset_n,
            len(chosen),
        )
    return [f"{book_id}/*" for book_id in chosen]


def verify_pairing(target_dir: Path) -> tuple[int, int, list[str]]:
    """Verify every .jpg has a matching .txt (and vice versa).

    Returns (page_count, mismatch_count, mismatched_paths).
    """
    images = {p.with_suffix("") for p in target_dir.rglob("*.jpg")}
    texts = {p.with_suffix("") for p in target_dir.rglob("*.txt")}

    paired = images & texts
    mismatched = sorted(str(p) for p in (images | texts) - paired)

    return len(paired), len(mismatched), mismatched


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    configure_environment(args.cache_dir)

    # Lazy import — keep argument parsing snappy and avoid forcing the
    # huggingface_hub dependency just to print --help.
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError:
        LOG.error(
            "huggingface_hub is not installed. Run scripts/setup_env.sh "
            "or activate the venv before invoking this script."
        )
        return 2

    api = HfApi()

    # --list path: enumerate and exit.
    if args.list:
        for book_id in list_book_directories(api):
            print(book_id)
        return 0

    # Build the allow_patterns list.
    if args.full:
        allow_patterns = None
        LOG.info("Downloading the full corpus (~13 GB). This may take a while.")
    else:
        book_ids = list_book_directories(api)
        allow_patterns = select_subset_patterns(book_ids, args.subset)
        LOG.info("Downloading %d books to %s", len(allow_patterns), args.target)

    args.target.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=DATASET_REPO_ID,
        repo_type=DATASET_REPO_TYPE,
        local_dir=str(args.target),
        allow_patterns=allow_patterns,
    )

    LOG.info("Download complete. Verifying .jpg / .txt pairing ...")
    page_count, mismatch_count, mismatched = verify_pairing(args.target)
    LOG.info("Paired pages found: %d", page_count)

    if mismatch_count > 0:
        LOG.warning(
            "%d unpaired files found. First 10: %s",
            mismatch_count,
            mismatched[:10],
        )
        # Mismatches are a corpus-quality issue, not a script failure.

    LOG.info("Output directory: %s", args.target)
    LOG.info("HuggingFace cache: %s", args.cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
