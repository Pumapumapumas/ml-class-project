"""Shared pytest fixtures for ``src/utils/`` tests.

Fixtures generate tiny real PNG/JPG images via Pillow at test time so we do
not commit binary blobs to the repo. Each test gets its own ``tmp_path``-
scoped corpus directory so tests are fully isolated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


def _make_jpg(
    path: Path, width: int, height: int, color: tuple[int, int, int] = (255, 255, 255)
) -> Path:
    """Write a tiny solid-color JPG at ``path`` with the given dimensions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=color)
    img.save(path, format="JPEG")
    return path


def _make_txt(path: Path, content: str) -> Path:
    """Write a text file at ``path`` with UTF-8 NFC content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def empty_book_dir(tmp_path: Path) -> Path:
    """An empty book directory (no images, no texts)."""
    book = tmp_path / "empty_book"
    book.mkdir()
    return book


@pytest.fixture
def paired_book_dir(tmp_path: Path) -> Path:
    """A book directory with 3 fully-paired pages.

    page_0001.jpg (10x20), page_0001.txt — "page one content"
    page_0002.jpg (30x40), page_0002.txt — "page two content"
    page_0003.jpg (50x60), page_0003.txt — "page three content"
    """
    book = tmp_path / "paired_book"
    book.mkdir()
    _make_jpg(book / "page_0001.jpg", 10, 20)
    _make_txt(book / "page_0001.txt", "page one content")
    _make_jpg(book / "page_0002.jpg", 30, 40)
    _make_txt(book / "page_0002.txt", "page two content")
    _make_jpg(book / "page_0003.jpg", 50, 60)
    _make_txt(book / "page_0003.txt", "page three content")
    return book


@pytest.fixture
def mismatched_book_dir(tmp_path: Path) -> Path:
    """A book directory with mismatches in both directions.

    page_0001.jpg paired with page_0001.txt   (paired)
    page_0002.jpg                              (no .txt)
                  page_0003.txt                (no .jpg)
    """
    book = tmp_path / "mismatched_book"
    book.mkdir()
    _make_jpg(book / "page_0001.jpg", 10, 20)
    _make_txt(book / "page_0001.txt", "ok")
    _make_jpg(book / "page_0002.jpg", 10, 20)
    _make_txt(book / "page_0003.txt", "orphan text")
    return book


@pytest.fixture
def small_corpus(tmp_path: Path) -> Path:
    """A small multi-book corpus root with a mix of conditions.

    corpus/
      book_alpha/      (2 paired pages)
      book_beta/       (1 paired page + 1 orphan jpg)
      .hidden_book/    (paired pages, but the dir is hidden — must be skipped)
      not_a_book.txt   (top-level file, must be ignored)
    """
    root = tmp_path / "corpus"
    root.mkdir()

    alpha = root / "book_alpha"
    alpha.mkdir()
    _make_jpg(alpha / "page_0001.jpg", 100, 200)
    _make_txt(alpha / "page_0001.txt", "alpha 1")
    _make_jpg(alpha / "page_0002.jpg", 110, 210)
    _make_txt(alpha / "page_0002.txt", "alpha 2")

    beta = root / "book_beta"
    beta.mkdir()
    _make_jpg(beta / "page_0001.jpg", 50, 60)
    _make_txt(beta / "page_0001.txt", "beta 1")
    _make_jpg(beta / "page_0002.jpg", 50, 60)
    # Note: no page_0002.txt — orphan jpg

    hidden = root / ".hidden_book"
    hidden.mkdir()
    _make_jpg(hidden / "page_0001.jpg", 10, 10)
    _make_txt(hidden / "page_0001.txt", "should be skipped")

    (root / "not_a_book.txt").write_text("noise at the root level", encoding="utf-8")

    return root
