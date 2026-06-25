"""Integration test for ``scripts/score_ocr.py``.

Builds a tiny fixture corpus inside ``tmp_path`` and runs the script end-to-
end so a future refactor of the CLI plumbing breaks loudly. Covers the
happy path (paired files score), the missing-truth path (skipped with
warning, no row), the empty-truth path (skipped with warning, no row), and
the missing-cell-directory path (just no rows from that cell).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import scripts.score_ocr as score_ocr


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def fixture_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a minimal fixture corpus and return (ocr_root, truth_root, out_csv)."""
    ocr_root = tmp_path / "processed"
    truth_root = tmp_path / "raw"
    out_csv = tmp_path / "cer_wer.csv"

    # Cell 1: claude_raw — two paired pages, one perfect, one one-substitution
    _write(truth_root / "book_a" / "page_0001.txt", "hello world")
    _write(ocr_root / "claude_raw" / "book_a" / "page_0001.txt", "hello world")
    _write(truth_root / "book_a" / "page_0002.txt", "hello")
    _write(ocr_root / "claude_raw" / "book_a" / "page_0002.txt", "hellp")  # 1 sub

    # Cell 2: gemini_raw — one paired page (perfect) + one OCR with missing truth
    _write(truth_root / "book_b" / "page_0001.txt", "test")
    _write(ocr_root / "gemini_raw" / "book_b" / "page_0001.txt", "test")
    _write(ocr_root / "gemini_raw" / "book_b" / "page_0099.txt", "orphan")  # no truth

    # Cell 3: gemini_preprocessed — one page where truth is empty (whitespace only)
    _write(truth_root / "book_c" / "page_0001.txt", "   ")
    _write(ocr_root / "gemini_preprocessed" / "book_c" / "page_0001.txt", "some text")

    return ocr_root, truth_root, out_csv


class TestScoreOCR:
    def test_score_cell_returns_rows_for_paired_pages(self, fixture_tree: tuple[Path, Path, Path]):
        ocr_root, truth_root, _ = fixture_tree
        rows = score_ocr.score_cell(ocr_root / "claude_raw", truth_root)
        assert len(rows) == 2
        # The perfect-match row has cer == 0
        perfect = next(r for r in rows if r["page_id"] == "page_0001")
        assert perfect["cer"] == 0.0
        assert perfect["wer"] == 0.0
        # The single-substitution row has cer == 0.2 (1 of 5 chars)
        sub = next(r for r in rows if r["page_id"] == "page_0002")
        assert sub["cer"] == pytest.approx(0.2)

    def test_score_cell_propagates_model_and_preprocessing(
        self, fixture_tree: tuple[Path, Path, Path]
    ):
        ocr_root, truth_root, _ = fixture_tree
        rows = score_ocr.score_cell(ocr_root / "claude_raw", truth_root)
        assert all(r["model"] == "claude" for r in rows)
        assert all(r["preprocessing"] == "raw" for r in rows)

    def test_score_cell_skips_missing_truth(self, fixture_tree: tuple[Path, Path, Path]):
        ocr_root, truth_root, _ = fixture_tree
        rows = score_ocr.score_cell(ocr_root / "gemini_raw", truth_root)
        # 2 OCR files but only 1 has a truth partner.
        assert len(rows) == 1
        assert rows[0]["page_id"] == "page_0001"

    def test_score_cell_skips_empty_truth(self, fixture_tree: tuple[Path, Path, Path]):
        ocr_root, truth_root, _ = fixture_tree
        rows = score_ocr.score_cell(ocr_root / "gemini_preprocessed", truth_root)
        assert rows == []

    def test_split_cell_name_normal(self):
        assert score_ocr.split_cell_name("gemini_preprocessed") == ("gemini", "preprocessed")
        assert score_ocr.split_cell_name("claude_raw") == ("claude", "raw")

    def test_split_cell_name_no_underscore_falls_back(self):
        # Defensive: a directory without an underscore in the name should not crash.
        assert score_ocr.split_cell_name("standalone") == ("standalone", "unknown")

    def test_write_csv_produces_header_and_sorted_rows(self, tmp_path: Path):
        rows = [
            {
                "book_id": "book_b",
                "page_id": "page_0002",
                "model": "claude",
                "preprocessing": "raw",
                "cer": 0.1,
                "wer": 0.4,
            },
            {
                "book_id": "book_a",
                "page_id": "page_0001",
                "model": "claude",
                "preprocessing": "raw",
                "cer": 0.0,
                "wer": 0.0,
            },
        ]
        out = tmp_path / "cer_wer.csv"
        score_ocr.write_csv(rows, out)

        with out.open(encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
        # Sorted by (model, preprocessing, book_id, page_id)
        assert [(r["book_id"], r["page_id"]) for r in records] == [
            ("book_a", "page_0001"),
            ("book_b", "page_0002"),
        ]
        assert records[0]["cer"] == "0.0"

    def test_end_to_end_via_main(self, fixture_tree: tuple[Path, Path, Path]):
        ocr_root, truth_root, out_csv = fixture_tree
        exit_code = score_ocr.main(
            [
                "--ocr-root",
                str(ocr_root),
                "--truth-root",
                str(truth_root),
                "--out",
                str(out_csv),
            ]
        )
        assert exit_code == 0
        assert out_csv.exists()

        with out_csv.open(encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
        # claude_raw contributes 2; gemini_raw contributes 1 (the orphan is skipped);
        # gemini_preprocessed contributes 0 (truth is empty).
        assert len(records) == 3
        # Per-cell counts
        cells = {(r["model"], r["preprocessing"]) for r in records}
        assert ("claude", "raw") in cells
        assert ("gemini", "raw") in cells

    def test_summarize_computes_per_cell_aggregates(self):
        rows = [
            {"model": "claude", "preprocessing": "raw", "cer": 0.1, "wer": 0.4},
            {"model": "claude", "preprocessing": "raw", "cer": 0.2, "wer": 0.5},
            {"model": "claude", "preprocessing": "raw", "cer": 0.3, "wer": 0.6},
            {"model": "gemini", "preprocessing": "raw", "cer": 0.5, "wer": 0.9},
        ]
        summary = score_ocr.summarize(rows)
        claude_key = ("claude", "raw")
        gemini_key = ("gemini", "raw")
        assert summary[claude_key]["n"] == 3
        assert summary[claude_key]["mean_cer"] == pytest.approx(0.2)
        assert summary[gemini_key]["n"] == 1
        assert summary[gemini_key]["mean_cer"] == 0.5
