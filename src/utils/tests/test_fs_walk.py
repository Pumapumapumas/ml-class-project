"""Unit tests for :mod:`src.utils.fs_walk`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from src.utils.fs_walk import discover_books

JPG_ONLY = frozenset({".jpg"})
ALL_IMAGES = frozenset({".jpg", ".jpeg", ".png"})


def _make_image(path: Path, ext: str = ".jpg") -> Path:
    """Write a tiny solid-white image so tests exercise real file I/O."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (10, 10), color=(255, 255, 255))
    img.save(path, format={"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG"}[ext.lstrip(".")])
    return path


class TestDiscoverBooks:
    def test_empty_root_returns_empty(self, tmp_path: Path):
        assert discover_books(tmp_path, JPG_ONLY) == []

    def test_groups_by_immediate_subdirectory(self, tmp_path: Path):
        _make_image(tmp_path / "book_alpha" / "page_0001.jpg")
        _make_image(tmp_path / "book_alpha" / "page_0002.jpg")
        _make_image(tmp_path / "book_beta" / "page_0001.jpg")
        result = discover_books(tmp_path, JPG_ONLY)
        assert [b for b, _ in result] == ["book_alpha", "book_beta"]
        assert len(result[0][1]) == 2  # book_alpha has 2 pages
        assert len(result[1][1]) == 1  # book_beta has 1 page

    def test_root_level_images_go_to_dot_book(self, tmp_path: Path):
        _make_image(tmp_path / "loose.jpg")
        _make_image(tmp_path / "book_alpha" / "page_0001.jpg")
        result = discover_books(tmp_path, JPG_ONLY)
        book_ids = [b for b, _ in result]
        assert "." in book_ids
        assert "book_alpha" in book_ids

    def test_hidden_directories_skipped(self, tmp_path: Path):
        _make_image(tmp_path / ".hidden_book" / "page_0001.jpg")
        _make_image(tmp_path / "book_alpha" / "page_0001.jpg")
        result = discover_books(tmp_path, JPG_ONLY)
        assert [b for b, _ in result] == ["book_alpha"]

    def test_extension_filter_respected_single(self, tmp_path: Path):
        _make_image(tmp_path / "book" / "p.jpg", ext=".jpg")
        _make_image(tmp_path / "book" / "p.png", ext=".png")
        result = discover_books(tmp_path, JPG_ONLY)
        assert len(result[0][1]) == 1
        assert result[0][1][0].suffix == ".jpg"

    def test_extension_filter_respected_multi(self, tmp_path: Path):
        _make_image(tmp_path / "book" / "p.jpg", ext=".jpg")
        _make_image(tmp_path / "book" / "p.png", ext=".png")
        result = discover_books(tmp_path, ALL_IMAGES)
        assert len(result[0][1]) == 2

    def test_books_with_no_matching_images_omitted(self, tmp_path: Path):
        (tmp_path / "book_empty").mkdir()
        _make_image(tmp_path / "book_alpha" / "page_0001.jpg")
        result = discover_books(tmp_path, JPG_ONLY)
        assert [b for b, _ in result] == ["book_alpha"]

    def test_image_paths_sorted_within_book(self, tmp_path: Path):
        _make_image(tmp_path / "book" / "page_0003.jpg")
        _make_image(tmp_path / "book" / "page_0001.jpg")
        _make_image(tmp_path / "book" / "page_0002.jpg")
        result = discover_books(tmp_path, JPG_ONLY)
        paths = result[0][1]
        assert [p.name for p in paths] == ["page_0001.jpg", "page_0002.jpg", "page_0003.jpg"]

    def test_raises_on_nonexistent_root(self, tmp_path: Path):
        with pytest.raises(ValueError, match="does not exist"):
            discover_books(tmp_path / "missing", JPG_ONLY)

    def test_raises_on_file_root(self, tmp_path: Path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("nope", encoding="utf-8")
        with pytest.raises(ValueError, match="not a directory"):
            discover_books(f, JPG_ONLY)
