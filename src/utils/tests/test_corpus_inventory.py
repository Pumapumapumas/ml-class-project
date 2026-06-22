"""Unit tests for ``src.utils.corpus_inventory``.

Tests use real Pillow-generated images and real filesystem operations via
``tmp_path``-scoped fixtures (see ``conftest.py``). No mocking of Pillow or
the filesystem — exercises the same code paths the CLI hits in production.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from PIL import Image

from src.utils.corpus_inventory import (
    REASON_MISSING_IMAGE,
    REASON_MISSING_TEXT,
    InventoryRow,
    MismatchedFile,
    extract_image_dimensions,
    pair_files,
    spot_check_encoding,
    walk_corpus,
    write_csv,
    write_mismatch_report,
)

# ---------------------------------------------------------------------------
# pair_files
# ---------------------------------------------------------------------------


class TestPairFiles:
    def test_empty_book_returns_empty_pairing(self, empty_book_dir: Path):
        paired, mismatches = pair_files(empty_book_dir)
        assert paired == {}
        assert mismatches == []

    def test_fully_paired_book(self, paired_book_dir: Path):
        paired, mismatches = pair_files(paired_book_dir)
        assert set(paired.keys()) == {"page_0001", "page_0002", "page_0003"}
        assert mismatches == []
        # Each entry maps to (jpg, txt) in that order.
        for page_id, (jpg, txt) in paired.items():
            assert jpg.suffix == ".jpg"
            assert txt.suffix == ".txt"
            assert jpg.stem == page_id
            assert txt.stem == page_id

    def test_mismatches_in_both_directions(self, mismatched_book_dir: Path):
        paired, mismatches = pair_files(mismatched_book_dir)
        # Only page_0001 should be paired.
        assert set(paired.keys()) == {"page_0001"}
        # Two mismatches: page_0002 missing text, page_0003 missing image.
        by_page = {m.page_id: m for m in mismatches}
        assert set(by_page.keys()) == {"page_0002", "page_0003"}
        assert by_page["page_0002"].reason == REASON_MISSING_TEXT
        assert by_page["page_0003"].reason == REASON_MISSING_IMAGE

    def test_raises_on_nonexistent_dir(self, tmp_path: Path):
        with pytest.raises(ValueError, match="does not exist"):
            pair_files(tmp_path / "nope")

    def test_raises_when_path_is_a_file(self, tmp_path: Path):
        not_a_dir = tmp_path / "not_a_dir"
        not_a_dir.write_text("just a file", encoding="utf-8")
        with pytest.raises(ValueError, match="not a directory"):
            pair_files(not_a_dir)

    def test_ignores_unrelated_files(self, tmp_path: Path):
        book = tmp_path / "book_with_noise"
        book.mkdir()
        # A paired page.
        Image.new("RGB", (10, 10)).save(book / "page_0001.jpg", format="JPEG")
        (book / "page_0001.txt").write_text("ok", encoding="utf-8")
        # Noise files that must be ignored.
        (book / "metadata.json").write_text("{}", encoding="utf-8")
        (book / "thumb.png").write_bytes(b"")
        (book / "page_0001.bak").write_text("backup", encoding="utf-8")

        paired, mismatches = pair_files(book)
        assert set(paired.keys()) == {"page_0001"}
        assert mismatches == []


# ---------------------------------------------------------------------------
# extract_image_dimensions
# ---------------------------------------------------------------------------


class TestExtractImageDimensions:
    def test_returns_width_and_height(self, paired_book_dir: Path):
        jpg = paired_book_dir / "page_0001.jpg"
        width, height = extract_image_dimensions(jpg)
        assert (width, height) == (10, 20)

    def test_different_dimensions(self, paired_book_dir: Path):
        jpg = paired_book_dir / "page_0003.jpg"
        width, height = extract_image_dimensions(jpg)
        assert (width, height) == (50, 60)

    def test_raises_on_nonexistent_file(self, tmp_path: Path):
        with pytest.raises((FileNotFoundError, OSError)):
            extract_image_dimensions(tmp_path / "nope.jpg")

    def test_raises_on_non_image(self, tmp_path: Path):
        fake = tmp_path / "fake.jpg"
        fake.write_text("not an image", encoding="utf-8")
        with pytest.raises(OSError):
            extract_image_dimensions(fake)


# ---------------------------------------------------------------------------
# walk_corpus
# ---------------------------------------------------------------------------


class TestWalkCorpus:
    def test_walks_multi_book_corpus(self, small_corpus: Path):
        rows, mismatches = walk_corpus(small_corpus)

        # 3 paired pages total: 2 in book_alpha + 1 in book_beta.
        # The hidden book is skipped.
        assert len(rows) == 3

        book_ids = [r.book_id for r in rows]
        assert "book_alpha" in book_ids
        assert "book_beta" in book_ids
        assert ".hidden_book" not in book_ids

        # 1 mismatch: orphan jpg in book_beta.
        assert len(mismatches) == 1
        assert mismatches[0].book_id == "book_beta"
        assert mismatches[0].page_id == "page_0002"
        assert mismatches[0].reason == REASON_MISSING_TEXT

    def test_rows_are_sorted_deterministically(self, small_corpus: Path):
        rows, _ = walk_corpus(small_corpus)
        keys = [(r.book_id, r.page_id) for r in rows]
        assert keys == sorted(keys)

    def test_image_dimensions_populated(self, small_corpus: Path):
        rows, _ = walk_corpus(small_corpus)
        alpha_p1 = next(r for r in rows if r.book_id == "book_alpha" and r.page_id == "page_0001")
        assert alpha_p1.image_width == 100
        assert alpha_p1.image_height == 200

    def test_byte_sizes_populated(self, small_corpus: Path):
        rows, _ = walk_corpus(small_corpus)
        for row in rows:
            assert row.image_bytes > 0
            assert row.text_bytes > 0

    def test_empty_corpus_returns_empty(self, tmp_path: Path):
        empty = tmp_path / "empty_corpus"
        empty.mkdir()
        rows, mismatches = walk_corpus(empty)
        assert rows == []
        assert mismatches == []

    def test_raises_on_nonexistent_source(self, tmp_path: Path):
        with pytest.raises(ValueError, match="does not exist"):
            walk_corpus(tmp_path / "missing")

    def test_top_level_files_ignored(self, small_corpus: Path):
        # The conftest fixture puts a not_a_book.txt at the corpus root.
        # walk_corpus should not blow up and should not include it.
        rows, _mismatches = walk_corpus(small_corpus)
        assert all("not_a_book" not in r.book_id for r in rows)


# ---------------------------------------------------------------------------
# write_csv
# ---------------------------------------------------------------------------


class TestWriteCsv:
    def test_writes_header_and_rows(self, tmp_path: Path):
        rows = [
            InventoryRow(
                book_id="book_a",
                page_id="page_0001",
                image_path=Path("data/raw/book_a/page_0001.jpg"),
                text_path=Path("data/raw/book_a/page_0001.txt"),
                image_bytes=1234,
                text_bytes=89,
                image_width=800,
                image_height=1200,
            ),
            InventoryRow(
                book_id="book_a",
                page_id="page_0002",
                image_path=Path("data/raw/book_a/page_0002.jpg"),
                text_path=Path("data/raw/book_a/page_0002.txt"),
                image_bytes=2345,
                text_bytes=140,
                image_width=820,
                image_height=1180,
            ),
        ]
        out = tmp_path / "out" / "inventory.csv"
        write_csv(rows, out)

        # Parent dir was auto-created.
        assert out.parent.is_dir()

        with out.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            records = list(reader)

        assert reader.fieldnames == [
            "book_id",
            "page_id",
            "image_path",
            "text_path",
            "image_bytes",
            "text_bytes",
            "image_width",
            "image_height",
        ]
        assert len(records) == 2
        assert records[0]["book_id"] == "book_a"
        assert records[0]["page_id"] == "page_0001"
        assert records[0]["image_width"] == "800"
        assert records[0]["image_height"] == "1200"
        assert records[1]["image_bytes"] == "2345"

    def test_empty_rows_produces_header_only(self, tmp_path: Path):
        out = tmp_path / "inventory.csv"
        write_csv([], out)
        with out.open(encoding="utf-8") as fh:
            content = fh.read()
        # Header line only, no data.
        assert content.startswith("book_id,page_id,")
        assert content.count("\n") == 1

    def test_relative_to_rewrites_paths(self, tmp_path: Path):
        # Simulate a "repo root" with the data under it.
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        data_dir = repo_root / "data" / "raw" / "book_a"
        data_dir.mkdir(parents=True)
        jpg = data_dir / "page_0001.jpg"
        txt = data_dir / "page_0001.txt"
        jpg.write_bytes(b"x")
        txt.write_text("y", encoding="utf-8")

        rows = [
            InventoryRow(
                book_id="book_a",
                page_id="page_0001",
                image_path=jpg,
                text_path=txt,
                image_bytes=1,
                text_bytes=1,
                image_width=10,
                image_height=20,
            ),
        ]
        out = repo_root / "data" / "external" / "inventory.csv"
        write_csv(rows, out, relative_to=repo_root)

        with out.open(encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
        # Paths in the CSV must be repo-relative (no leading slash, no tmp_path).
        assert records[0]["image_path"] == "data/raw/book_a/page_0001.jpg"
        assert records[0]["text_path"] == "data/raw/book_a/page_0001.txt"

    def test_relative_to_falls_back_to_absolute_when_path_outside(self, tmp_path: Path):
        # Path outside the repo root should be written as absolute, not crash.
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        outside_jpg = tmp_path / "elsewhere" / "page_0001.jpg"
        outside_jpg.parent.mkdir()
        outside_jpg.write_bytes(b"x")
        outside_txt = tmp_path / "elsewhere" / "page_0001.txt"
        outside_txt.write_text("y", encoding="utf-8")

        rows = [
            InventoryRow(
                book_id="orphan",
                page_id="page_0001",
                image_path=outside_jpg,
                text_path=outside_txt,
                image_bytes=1,
                text_bytes=1,
                image_width=1,
                image_height=1,
            ),
        ]
        out = repo_root / "inventory.csv"
        write_csv(rows, out, relative_to=repo_root)

        with out.open(encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
        # Absolute path retained (starts with /) since it's outside repo_root.
        assert records[0]["image_path"].startswith("/")


# ---------------------------------------------------------------------------
# write_mismatch_report
# ---------------------------------------------------------------------------


class TestWriteMismatchReport:
    def test_writes_one_json_object_per_line(self, tmp_path: Path):
        mismatches = [
            MismatchedFile(
                book_id="book_a",
                page_id="page_0007",
                path=Path("data/raw/book_a/page_0007.jpg"),
                reason=REASON_MISSING_TEXT,
            ),
            MismatchedFile(
                book_id="book_b",
                page_id="page_0042",
                path=Path("data/raw/book_b/page_0042.txt"),
                reason=REASON_MISSING_IMAGE,
            ),
        ]
        out = tmp_path / "logs" / "mismatches.jsonl"
        write_mismatch_report(mismatches, out)

        # Parent dir was auto-created.
        assert out.parent.is_dir()

        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        assert {r["page_id"] for r in records} == {"page_0007", "page_0042"}
        for r in records:
            assert "timestamp" in r
            assert r["reason"] in {REASON_MISSING_TEXT, REASON_MISSING_IMAGE}

    def test_empty_mismatches_produces_zero_byte_file(self, tmp_path: Path):
        out = tmp_path / "mismatches.jsonl"
        write_mismatch_report([], out)
        # Empty file exists as a positive signal that the check ran.
        assert out.exists()
        assert out.stat().st_size == 0


# ---------------------------------------------------------------------------
# spot_check_encoding
# ---------------------------------------------------------------------------


class TestSpotCheckEncoding:
    def test_returns_results_for_each_sampled_file(self, tmp_path: Path):
        paths = []
        for i in range(5):
            p = tmp_path / f"file_{i}.txt"
            p.write_text(f"content {i}", encoding="utf-8")
            paths.append(p)

        results = spot_check_encoding(paths, sample_size=3, seed=42)
        assert len(results) == 3
        for r in results:
            assert r["decoded"] is True
            assert r["is_nfc"] is True
            assert r["char_count"] > 0

    def test_empty_pool_returns_empty_list(self):
        assert spot_check_encoding([], sample_size=5) == []

    def test_sample_larger_than_pool_returns_all(self, tmp_path: Path):
        paths = []
        for i in range(2):
            p = tmp_path / f"file_{i}.txt"
            p.write_text("hello", encoding="utf-8")
            paths.append(p)

        results = spot_check_encoding(paths, sample_size=10, seed=1)
        assert len(results) == 2

    def test_undecodable_file_reported_not_raised(self, tmp_path: Path):
        bad = tmp_path / "bad.txt"
        # Write a byte sequence that is not valid UTF-8.
        bad.write_bytes(b"\xff\xfe\xfd")
        results = spot_check_encoding([bad], sample_size=1, seed=0)
        assert len(results) == 1
        assert results[0]["decoded"] is False
        assert "error" in results[0]

    def test_seed_makes_sampling_deterministic(self, tmp_path: Path):
        paths = []
        for i in range(10):
            p = tmp_path / f"file_{i:03d}.txt"
            p.write_text(f"content {i}", encoding="utf-8")
            paths.append(p)

        r1 = spot_check_encoding(paths, sample_size=3, seed=12345)
        r2 = spot_check_encoding(paths, sample_size=3, seed=12345)
        assert [r["path"] for r in r1] == [r["path"] for r in r2]


# ---------------------------------------------------------------------------
# End-to-end integration: walk -> write
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestIntegration:
    def test_walk_then_write_csv_roundtrip(self, small_corpus: Path, tmp_path: Path):
        rows, mismatches = walk_corpus(small_corpus)
        csv_out = tmp_path / "inventory.csv"
        log_out = tmp_path / "mismatches.jsonl"
        write_csv(rows, csv_out)
        write_mismatch_report(mismatches, log_out)

        # Re-read the CSV and confirm the row count matches.
        with csv_out.open(encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
        assert len(records) == len(rows) == 3

        # Mismatch log has the one orphan jpg.
        mismatch_lines = log_out.read_text(encoding="utf-8").splitlines()
        assert len(mismatch_lines) == 1
