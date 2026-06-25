"""Unit tests for ``src.ocr.tesseract``.

Mocks ``subprocess.run`` so we test the adapter's contract (build the right
docker command line, surface failures clearly, NFC-normalize output) without
needing the Docker daemon to be running. End-to-end coverage against the
real Docker image lives in ``tests/integration/test_tesseract_e2e.py``
(marked ``@pytest.mark.integration``).
"""

from __future__ import annotations

import subprocess
import unicodedata
from pathlib import Path

import pytest

from src.ocr.tesseract import (
    DOCKER_IMAGE,
    MODEL_NAME,
    TESSERACT_LANG,
    TESSERACT_PSM,
    TesseractAdapter,
)

# Two Unicode forms of the same character — a precomposed e-acute and its
# canonical decomposition (e + combining acute). Used explicit Unicode
# escapes because writing the literal characters lets editors silently
# normalize them and collapses the two forms into one.
NFC_E_ACUTE = "\u00e9"  # precomposed (NFC): U+00E9
NFD_E_ACUTE = "é"  # e + combining acute U+0301


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_image(tmp_path: Path) -> Path:
    """A dummy image file (Tesseract is mocked, so the bytes do not matter)."""
    p = tmp_path / "page.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    return p


def _make_run(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    """Build a fake ``subprocess.run`` result object."""

    def _runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return _runner


@pytest.fixture
def stub_docker_image_present(monkeypatch: pytest.MonkeyPatch):
    """Make ``docker image inspect`` succeed so the constructor accepts the image."""

    def _runner(cmd, *args, **kwargs):
        # The constructor's check is the only call to inspect; OCR calls use
        # the same module-level subprocess.run, so dispatch by command shape.
        if cmd[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
        # Default fall-through that tests can override per-test.
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", _runner)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_image_present_returns_adapter(self, stub_docker_image_present):
        adapter = TesseractAdapter()
        assert adapter.model_name == MODEL_NAME

    def test_missing_docker_cli_raises(self, monkeypatch: pytest.MonkeyPatch):
        def _runner(*args, **kwargs):
            raise FileNotFoundError("docker not on PATH")

        monkeypatch.setattr(subprocess, "run", _runner)
        with pytest.raises(RuntimeError, match="docker CLI not found"):
            TesseractAdapter()

    def test_missing_image_raises(self, monkeypatch: pytest.MonkeyPatch):
        def _runner(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=1,
                stdout=b"",
                stderr=b"No such image: ml-class-project/tesseract",
            )

        monkeypatch.setattr(subprocess, "run", _runner)
        with pytest.raises(RuntimeError, match="is not present locally"):
            TesseractAdapter()

    def test_docker_daemon_timeout_raises(self, monkeypatch: pytest.MonkeyPatch):
        def _runner(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="docker", timeout=10)

        monkeypatch.setattr(subprocess, "run", _runner)
        with pytest.raises(RuntimeError, match="docker CLI timed out"):
            TesseractAdapter()


# ---------------------------------------------------------------------------
# OCR call shape
# ---------------------------------------------------------------------------


class TestOCRCallShape:
    def test_command_includes_correct_docker_image_and_flags(
        self, monkeypatch: pytest.MonkeyPatch, fake_image: Path
    ):
        captured: dict = {}

        def _runner(cmd, *args, **kwargs):
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=b"hello\n", stderr=b""
            )

        monkeypatch.setattr(subprocess, "run", _runner)

        TesseractAdapter().ocr(fake_image)

        cmd = captured["cmd"]
        assert cmd[0:4] == ["docker", "run", "--rm", "-i"]
        assert DOCKER_IMAGE in cmd
        assert "tesseract" in cmd
        assert "-l" in cmd and TESSERACT_LANG in cmd
        assert "--psm" in cmd and TESSERACT_PSM in cmd
        assert "stdout" in cmd
        # Image bytes piped through stdin verbatim:
        assert captured["input"] == fake_image.read_bytes()


# ---------------------------------------------------------------------------
# Output handling
# ---------------------------------------------------------------------------


class TestOutputHandling:
    def test_successful_call_returns_nfc_normalized_text(
        self, monkeypatch: pytest.MonkeyPatch, fake_image: Path
    ):
        # Telugu identifier so this is not flagged as empty/refusal-shape.
        raw = ("తెలుగు" + NFD_E_ACUTE).encode("utf-8")
        assert raw.decode("utf-8") != unicodedata.normalize(
            "NFC", raw.decode("utf-8")
        )  # raw really is NFD

        def _runner(cmd, *args, **kwargs):
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=raw, stderr=b"")

        monkeypatch.setattr(subprocess, "run", _runner)

        result = TesseractAdapter().ocr(fake_image)

        assert result.text == unicodedata.normalize("NFC", raw.decode("utf-8"))
        assert NFC_E_ACUTE in result.text
        assert NFD_E_ACUTE not in result.text
        assert result.model_name == MODEL_NAME
        assert result.latency_ms >= 0

    def test_empty_output_returns_empty_text_not_error(
        self, monkeypatch: pytest.MonkeyPatch, fake_image: Path, caplog
    ):
        # Tesseract producing no extractable text is NOT an error — it gets
        # captured in the batch manifest as an empty result, not a raise.
        def _runner(cmd, *args, **kwargs):
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _runner)

        result = TesseractAdapter().ocr(fake_image)

        assert result.text == ""
        assert result.model_name == MODEL_NAME


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


class TestFailurePaths:
    def test_missing_image_file_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # Constructor passes; the ocr() call must reject a missing path.
        def _runner(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _runner)
        adapter = TesseractAdapter()
        with pytest.raises(FileNotFoundError, match="image not found"):
            adapter.ocr(tmp_path / "missing.jpg")

    def test_nonzero_exit_raises_with_stderr_tail(
        self, monkeypatch: pytest.MonkeyPatch, fake_image: Path
    ):
        def _runner(cmd, *args, **kwargs):
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout=b"",
                stderr=b"tesseract: failed to recognise something",
            )

        monkeypatch.setattr(subprocess, "run", _runner)

        with pytest.raises(RuntimeError, match="status 1"):
            TesseractAdapter().ocr(fake_image)

    def test_timeout_raises(self, monkeypatch: pytest.MonkeyPatch, fake_image: Path):
        def _runner(cmd, *args, **kwargs):
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=60)

        monkeypatch.setattr(subprocess, "run", _runner)

        with pytest.raises(RuntimeError, match="timed out"):
            TesseractAdapter().ocr(fake_image)

    def test_invalid_utf8_output_raises(self, monkeypatch: pytest.MonkeyPatch, fake_image: Path):
        # Defensive: invalid UTF-8 from Tesseract should surface a clear error,
        # not corrupt the OCR pipeline with mojibake.
        def _runner(cmd, *args, **kwargs):
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=b"\xff\xfe\xfd not utf8", stderr=b""
            )

        monkeypatch.setattr(subprocess, "run", _runner)

        with pytest.raises(RuntimeError, match="not valid UTF-8"):
            TesseractAdapter().ocr(fake_image)
