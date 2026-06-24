"""End-to-end integration test for the preprocessing CLI.

Builds a tiny multi-page fixture corpus on disk, runs the CLI's ``main`` in
process against it, and asserts the output directory mirrors the input layout.
Uses real images and the real pipeline — no mocking, per the testing standard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
# The CLI lives in scripts/ (not an importable package); add it to the path so
# the test can drive ``main`` directly rather than shelling out.
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_preprocessing  # noqa: E402  (path must be set up first)


def _make_page(path: Path, *, skew: float = 0.0) -> None:
    """Write a small white JPG page with a few horizontal black bars."""
    path.parent.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (300, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(page)
    for y in range(50, 260, 40):
        draw.rectangle([30, y, 270, y + 8], fill=(0, 0, 0))
    if skew:
        page = page.rotate(skew, expand=False, fillcolor=(255, 255, 255))
    page.save(path, format="JPEG")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A 3-page corpus under ``corpus/book_alpha/`` with varied skew."""
    book = tmp_path / "corpus" / "book_alpha"
    _make_page(book / "page_0001.jpg", skew=0.0)
    _make_page(book / "page_0002.jpg", skew=5.0)
    _make_page(book / "page_0003.jpg", skew=-3.0)
    return tmp_path / "corpus"


@pytest.mark.integration
def test_cli_mirrors_input_structure(corpus: Path, tmp_path: Path):
    output = tmp_path / "preprocessed"
    exit_code = run_preprocessing.main(["--input", str(corpus), "--output", str(output)])

    assert exit_code == 0
    expected = {
        output / "book_alpha" / "page_0001.png",
        output / "book_alpha" / "page_0002.png",
        output / "book_alpha" / "page_0003.png",
    }
    produced = set((output / "book_alpha").glob("*.png"))
    assert produced == expected
    # Every output is a non-empty file.
    for path in expected:
        assert path.stat().st_size > 0


@pytest.mark.integration
def test_cli_is_idempotent_on_rerun(corpus: Path, tmp_path: Path):
    output = tmp_path / "preprocessed"

    first = run_preprocessing.main(["--input", str(corpus), "--output", str(output)])
    assert first == 0
    mtimes = {p: p.stat().st_mtime_ns for p in (output / "book_alpha").glob("*.png")}

    # A second run with no --overwrite should skip every existing output and
    # therefore leave the files untouched.
    second = run_preprocessing.main(["--input", str(corpus), "--output", str(output)])
    assert second == 0
    for path, mtime in mtimes.items():
        assert path.stat().st_mtime_ns == mtime


@pytest.mark.integration
def test_cli_disabling_deskew_still_produces_outputs(corpus: Path, tmp_path: Path):
    output = tmp_path / "preprocessed"
    exit_code = run_preprocessing.main(
        ["--input", str(corpus), "--output", str(output), "--no-deskew"]
    )
    assert exit_code == 0
    assert len(list((output / "book_alpha").glob("*.png"))) == 3
