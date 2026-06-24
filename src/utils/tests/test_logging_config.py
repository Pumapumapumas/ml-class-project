"""Unit tests for ``src.utils.logging_config``.

These tests configure the real root logger, so an autouse fixture snapshots and
restores its handlers/level around every test to keep them isolated from each
other and from the rest of the suite. Structured-mode assertions read the JSON
log file directly (deterministic); stream assertions use ``capsys`` (human mode
writes to stderr, structured mode tees to stdout).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

from src.utils.logging_config import (
    _PIPELINE_HANDLER_MARKER,
    DEFAULT_LOG_DIR,
    RESERVED_KEYS,
    STRUCTURED_ENV_VAR,
    _HumanFormatter,
    _JsonLinesFormatter,
    _ReservedKeyFilter,
    setup_logging,
)


def _pipeline_handlers() -> list[logging.Handler]:
    """Return the handlers attached by setup_logging (not pytest's caplog).

    setup_logging tags every handler it attaches with _PIPELINE_HANDLER_MARKER so
    foreign handlers (e.g. pytest's caplog capture handler) are not clobbered on
    reconfiguration. Tests count only the pipeline handlers.
    """
    return [h for h in logging.getLogger().handlers if getattr(h, _PIPELINE_HANDLER_MARKER, False)]


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Snapshot and restore the root logger around each test.

    Configuring logging mutates global state; without this, handlers leak
    between tests and pollute unrelated suites (and file handlers keep
    descriptors open).
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        # Only close handlers this test added; a pre-existing handler that was
        # saved must be re-attached open, not closed.
        if handler not in saved_handlers:
            handler.close()
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)


def _read_jsonl(path: Path) -> list[dict]:
    """Parse a JSON Lines file into a list of dicts."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Human (non-structured) mode
# ---------------------------------------------------------------------------


class TestHumanMode:
    def test_configures_single_stream_handler_at_requested_level(self):
        result = setup_logging(name="t", structured=False, level=logging.DEBUG)
        root = logging.getLogger()
        ours = _pipeline_handlers()

        assert result is None
        assert len(ours) == 1
        assert isinstance(ours[0], logging.StreamHandler)
        assert isinstance(ours[0].formatter, _HumanFormatter)
        assert root.level == logging.DEBUG

    def test_default_level_is_info(self):
        setup_logging(name="t", structured=False)
        assert logging.getLogger().level == logging.INFO

    def test_stderr_matches_legacy_format(self, capsys):
        setup_logging(name="t", structured=False)
        logging.getLogger("src.ocr.gemini").info("page processed")
        captured = capsys.readouterr()
        # Human mode writes to stderr (matching the prior basicConfig default);
        # stdout stays clean.
        assert captured.out == ""
        # <ts> LEVEL logger - message — the exact pre-retrofit convention.
        assert captured.err.strip().endswith("INFO src.ocr.gemini - page processed")

    def test_extras_appended_as_key_value(self, capsys):
        setup_logging(name="t", structured=False)
        logging.getLogger("src.ocr.gemini").info(
            "page processed", extra={"page_id": "p_001", "model": "gemini"}
        )
        err = capsys.readouterr().err.strip()
        assert err.endswith("page processed page_id=p_001 model=gemini")


# ---------------------------------------------------------------------------
# Structured (JSON Lines) mode
# ---------------------------------------------------------------------------


class TestStructuredMode:
    def test_creates_json_file_and_stdout_handler(self, tmp_path: Path):
        log_path = setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        root = logging.getLogger()

        assert log_path is not None
        assert log_path.parent == tmp_path
        assert log_path.name.startswith("run_ocr_")
        assert log_path.suffix == ".jsonl"
        assert log_path.exists()

        handler_types = [type(h) for h in root.handlers]
        assert logging.StreamHandler in handler_types
        assert logging.FileHandler in handler_types

    def test_info_with_extras_produces_parseable_json_line(self, tmp_path: Path):
        log_path = setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        logging.getLogger("src.ocr.gemini").info(
            "page processed", extra={"page_id": "p_001", "model": "gemini"}
        )
        records = _read_jsonl(log_path)
        assert len(records) == 1
        rec = records[0]
        assert rec["level"] == "INFO"
        assert rec["logger"] == "src.ocr.gemini"
        assert rec["msg"] == "page processed"
        assert rec["page_id"] == "p_001"
        assert rec["model"] == "gemini"
        # ts is ISO-8601 UTC with a trailing Z.
        assert rec["ts"].endswith("Z")

    def test_tees_to_stdout(self, tmp_path: Path, capsys):
        setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        logging.getLogger("src.ocr.gemini").info("page processed")
        out = capsys.readouterr().out.strip()
        # stdout line is itself valid JSON.
        assert json.loads(out)["msg"] == "page processed"

    def test_non_ascii_extras_not_escaped(self, tmp_path: Path):
        log_path = setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        telugu = "తెలుగు"
        logging.getLogger("src.ocr.gemini").info("ocr", extra={"text": telugu})
        # Raw file contains the literal Telugu, not \u-escapes.
        raw = log_path.read_text(encoding="utf-8")
        assert telugu in raw
        assert _read_jsonl(log_path)[0]["text"] == telugu

    def test_filename_uses_name_and_timestamp(self, tmp_path: Path):
        log_path = setup_logging(name="my_pipeline", structured=True, log_dir=tmp_path)
        assert log_path is not None
        # my_pipeline_<YYYYMMDDTHHMMSSZ>.jsonl
        stem = log_path.stem
        assert stem.startswith("my_pipeline_")
        timestamp = stem.removeprefix("my_pipeline_")
        assert timestamp.endswith("Z")
        assert len(timestamp) == len("20260624T174500Z")


# ---------------------------------------------------------------------------
# Reserved-key collisions
# ---------------------------------------------------------------------------


class TestReservedKeys:
    # 'msg' is excluded from these parametrize lists on purpose: it is a real
    # LogRecord attribute, so stdlib makeRecord blocks it before the filter runs.
    # It is covered separately by test_msg_reserved_key_blocked_by_stdlib.
    @pytest.mark.parametrize("key", ["ts", "level", "logger"])
    def test_filter_rejects_reserved_extra(self, key: str):
        # 'ts', 'level', 'logger' are not LogRecord attributes, so they survive
        # makeRecord and reach the filter, which raises a clear ValueError.
        record = logging.makeLogRecord({"msg": "hi"})
        setattr(record, key, "x")
        with pytest.raises(ValueError, match="reserved key"):
            _ReservedKeyFilter().filter(record)

    @pytest.mark.parametrize("key", ["ts", "level", "logger"])
    def test_logger_call_raises_on_reserved_extra(self, tmp_path: Path, key: str):
        setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        with pytest.raises(ValueError, match="reserved key"):
            logging.getLogger("src.ocr.gemini").info("m", extra={key: "x"})

    @pytest.mark.parametrize("structured", [True, False])
    def test_msg_reserved_key_blocked_by_stdlib(self, tmp_path: Path, structured: bool):
        # 'msg' is a real LogRecord attribute, so the standard library blocks it
        # at makeRecord (KeyError) before the filter runs. Still a loud failure,
        # not a silent overwrite. This holds in both structured and human mode
        # because the block is in makeRecord, independent of which handlers run.
        setup_logging(name="run_ocr", structured=structured, log_dir=tmp_path)
        with pytest.raises(KeyError, match="msg"):
            logging.getLogger("src.ocr.gemini").info("m", extra={"msg": "x"})

    def test_reserved_keys_constant(self):
        assert RESERVED_KEYS == frozenset({"ts", "level", "logger", "msg"})


# ---------------------------------------------------------------------------
# Env-var auto-detection
# ---------------------------------------------------------------------------


class TestEnvVarDetection:
    def test_env_var_activates_structured_mode(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(STRUCTURED_ENV_VAR, "1")
        log_path = setup_logging(name="run_ocr", structured=None, log_dir=tmp_path)
        assert log_path is not None
        assert log_path.exists()

    def test_env_var_unset_is_human_mode(self, monkeypatch):
        monkeypatch.delenv(STRUCTURED_ENV_VAR, raising=False)
        result = setup_logging(name="run_ocr", structured=None)
        assert result is None

    def test_env_var_non_one_value_is_human_mode(self, monkeypatch):
        monkeypatch.setenv(STRUCTURED_ENV_VAR, "true")
        result = setup_logging(name="run_ocr", structured=None)
        assert result is None

    def test_explicit_structured_overrides_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(STRUCTURED_ENV_VAR, "1")
        result = setup_logging(name="run_ocr", structured=False)
        assert result is None


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_human_mode_twice_does_not_double_attach(self):
        setup_logging(name="t", structured=False)
        setup_logging(name="t", structured=False)
        assert len(_pipeline_handlers()) == 1

    def test_structured_mode_twice_does_not_double_attach(self, tmp_path: Path):
        setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        # One stream + one file handler, not two of each.
        assert len(_pipeline_handlers()) == 2

    def test_switching_modes_replaces_handlers(self, tmp_path: Path):
        setup_logging(name="run_ocr", structured=True, log_dir=tmp_path)
        setup_logging(name="t", structured=False)
        ours = _pipeline_handlers()
        assert len(ours) == 1
        assert isinstance(ours[0].formatter, _HumanFormatter)

    def test_foreign_handlers_preserved(self):
        """Handlers we did not attach (e.g. pytest's caplog) survive reconfiguration."""
        root = logging.getLogger()
        foreign = logging.StreamHandler(sys.stderr)
        # Deliberately NOT marked with _PIPELINE_HANDLER_MARKER.
        root.addHandler(foreign)
        try:
            setup_logging(name="t", structured=False)
            assert foreign in root.handlers, (
                "setup_logging cleared a foreign handler — would break pytest caplog"
            )
        finally:
            root.removeHandler(foreign)


# ---------------------------------------------------------------------------
# Module-level wiring
# ---------------------------------------------------------------------------


def test_default_log_dir_points_at_repo_logs():
    assert DEFAULT_LOG_DIR.name == "logs"
    # <repo>/logs, with src/utils/ between this file and the repo root.
    assert DEFAULT_LOG_DIR.parent.joinpath("src", "utils", "logging_config.py").exists()


def test_json_formatter_includes_exception(tmp_path: Path):
    formatter = _JsonLinesFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="src.ocr.gemini",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "ERROR"
    assert "ValueError: boom" in payload["exc_info"]
