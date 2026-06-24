"""End-to-end integration test for the OCR batch runner CLI.

Builds a tiny multi-page fixture corpus on disk, injects a fake adapter that
returns canned text (so no network, no key, no real SDK), runs the CLI's
``main`` in process, and asserts the output directory structure, the per-page
text files, and the manifest contents.

Only the external OCR backend is faked — the CLI's discovery, output mirroring,
manifest writing, idempotency, and failure handling all run for real, per the
testing standard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
# The CLI lives in scripts/ (not an importable package); add both it and the
# repo root to the path so the test can drive ``main`` directly and import the
# OCRResult type the fake adapter returns.
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_ocr  # noqa: E402  (path must be set up first)

from src.ocr.base import OCRResult  # noqa: E402


class _FakeAdapter:
    """Adapter returning canned text keyed by image filename stem."""

    model_name = "fake-ocr-1.0"

    def __init__(self, text_by_stem: dict[str, str], fail_stems: set[str] | None = None) -> None:
        self._text_by_stem = text_by_stem
        self._fail_stems = fail_stems or set()

    def ocr(self, image_path: Path) -> OCRResult:
        if image_path.stem in self._fail_stems:
            raise RuntimeError(f"simulated OCR failure on {image_path.stem}")
        text = self._text_by_stem.get(image_path.stem, "")
        return OCRResult(text=text, model_name=self.model_name, latency_ms=12.5)


PAGE_TEXT = {
    "page_0001": "మొదటి పేజీ",
    "page_0002": "రెండవ పేజీ",
}


def _make_page(path: Path) -> None:
    """Write a small white JPG page with a few horizontal black bars."""
    path.parent.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (200, 280), color=(255, 255, 255))
    draw = ImageDraw.Draw(page)
    for y in range(40, 240, 30):
        draw.rectangle([20, y, 180, y + 10], fill=(0, 0, 0))
    page.save(path, format="JPEG")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A 2-page corpus under ``corpus/book_alpha/``."""
    book = tmp_path / "corpus" / "book_alpha"
    _make_page(book / "page_0001.jpg")
    _make_page(book / "page_0002.jpg")
    return tmp_path / "corpus"


def _read_manifest(output: Path) -> list[dict]:
    lines = (output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


@pytest.mark.integration
def test_cli_writes_text_files_and_manifest(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(run_ocr, "build_adapter", lambda model: _FakeAdapter(PAGE_TEXT))
    output = tmp_path / "out"

    exit_code = run_ocr.main(["--model", "gemini", "--input", str(corpus), "--output", str(output)])

    assert exit_code == 0

    # Per-page text files mirror the input layout and carry the canned text.
    for stem, text in PAGE_TEXT.items():
        out_path = output / "book_alpha" / f"{stem}.txt"
        assert out_path.read_text(encoding="utf-8") == text

    # Manifest: one record per page, with the documented fields and no errors.
    records = _read_manifest(output)
    assert len(records) == 2
    by_page = {r["page_id"]: r for r in records}
    for stem, text in PAGE_TEXT.items():
        record = by_page[stem]
        assert record["book_id"] == "book_alpha"
        assert record["model"] == "fake-ocr-1.0"
        assert record["text_length"] == len(text)
        assert record["latency_ms"] == 12.5
        assert "error" not in record


@pytest.mark.integration
def test_cli_continues_past_a_failing_page(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    adapter = _FakeAdapter(PAGE_TEXT, fail_stems={"page_0001"})
    monkeypatch.setattr(run_ocr, "build_adapter", lambda model: adapter)
    output = tmp_path / "out"

    exit_code = run_ocr.main(["--model", "gemini", "--input", str(corpus), "--output", str(output)])

    # One page failed -> non-zero exit, but the good page still produced output.
    assert exit_code == 1
    assert not (output / "book_alpha" / "page_0001.txt").exists()
    assert (output / "book_alpha" / "page_0002.txt").read_text(encoding="utf-8") == PAGE_TEXT[
        "page_0002"
    ]

    records = _read_manifest(output)
    by_page = {r["page_id"]: r for r in records}
    assert "error" in by_page["page_0001"]
    assert by_page["page_0001"]["latency_ms"] is None
    assert by_page["page_0001"]["text_length"] == 0
    assert "error" not in by_page["page_0002"]


@pytest.mark.integration
def test_cli_is_idempotent_and_overwrite_reprocesses(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(run_ocr, "build_adapter", lambda model: _FakeAdapter(PAGE_TEXT))
    output = tmp_path / "out"
    argv = ["--model", "gemini", "--input", str(corpus), "--output", str(output)]

    assert run_ocr.main(argv) == 0
    mtimes = {p: p.stat().st_mtime_ns for p in (output / "book_alpha").glob("*.txt")}

    # Second run without --overwrite skips existing outputs: files untouched and
    # the manifest reflects zero pages processed this invocation.
    assert run_ocr.main(argv) == 0
    for path, mtime in mtimes.items():
        assert path.stat().st_mtime_ns == mtime
    assert _read_manifest(output) == []

    # With --overwrite the pages are reprocessed and the manifest is rebuilt.
    assert run_ocr.main([*argv, "--overwrite"]) == 0
    assert len(_read_manifest(output)) == 2


@pytest.mark.integration
def test_cli_aborts_cleanly_when_no_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_ocr, "build_adapter", lambda model: _FakeAdapter(PAGE_TEXT))
    empty = tmp_path / "empty"
    empty.mkdir()
    output = tmp_path / "out"

    exit_code = run_ocr.main(["--model", "gemini", "--input", str(empty), "--output", str(output)])

    assert exit_code == 0
    assert not (output / "manifest.jsonl").exists()
