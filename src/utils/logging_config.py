"""Central logging configuration for the OCR pipeline.

Every CLI entry point in ``scripts/`` calls :func:`setup_logging` exactly once,
near the top of ``main``, to configure the root logger for the process. Library
modules never call this — they obtain a logger with
``logging.getLogger(__name__)`` and let the configuration set here govern format
and destination.

Two output formats are supported, per ``docs/standards/logging_standard.md``:

- **Human-readable** (default, interactive use): one line per record matching
  the long-standing convention ``<ts> <LEVEL> <logger> - <message>``, written to
  **stderr** (matching the ``logging.basicConfig`` default these scripts
  previously used, so stdout stays clean for machine-readable ``print`` output).
  Structured extras, if any, are appended in ``key=value`` form.
- **JSON Lines** (``structured=True``, batch pipeline runs): one JSON object per
  line, tee'd to both stdout and a timestamped file under ``logs/``. Structured
  extras passed via ``logger.info(msg, extra={...})`` land at the top level of
  the object alongside the reserved fields ``ts``, ``level``, ``logger``,
  ``msg``.

The structured-vs-human choice is opt-in via the ``PIPELINE_STRUCTURED``
environment variable (set to ``1``) when ``structured`` is left as ``None``. An
environment variable rather than a CLI flag is used deliberately so that
retrofitting an existing script leaves its ``--help`` output unchanged.

See ``docs/standards/logging_standard.md`` for the format/destination/level
discipline this module implements.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Repo root is three levels up: logging_config.py -> utils -> src -> <repo>.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = REPO_ROOT / "logs"

# Timestamp format for log filenames, matching the convention already used by
# scripts/build_corpus_inventory.py for its mismatch report.
_FILE_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

# Environment variable that activates structured mode when ``structured=None``.
STRUCTURED_ENV_VAR = "PIPELINE_STRUCTURED"

# Top-level keys the JSON Lines formatter writes for every record. A structured
# extra that reuses one of these names would silently clobber the real value, so
# we reject it loudly instead (see _ReservedKeyFilter).
RESERVED_KEYS: frozenset[str] = frozenset({"ts", "level", "logger", "msg"})

# Attribute names present on a vanilla LogRecord. Anything on a record's __dict__
# beyond this set was supplied by the caller via ``extra=`` and is treated as a
# structured field. Computed dynamically so it stays correct across Python
# versions (e.g. ``taskName`` added in 3.12). ``message`` and ``asctime`` are
# added by Formatter.format at render time, so they are excluded explicitly.
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}


def _extract_extras(record: logging.LogRecord) -> dict[str, object]:
    """Return the caller-supplied ``extra=`` fields attached to a record."""
    return {
        key: value for key, value in record.__dict__.items() if key not in _STANDARD_RECORD_ATTRS
    }


class _ReservedKeyFilter(logging.Filter):
    """Reject structured extras that collide with a reserved JSON field name.

    Attached to handlers in structured mode. A logging ``Filter`` is used rather
    than enforcing the check in the formatter because exceptions raised inside
    ``Formatter.format`` are swallowed by ``logging.Handler.handleError`` and
    never reach the caller; an exception raised from a filter propagates up
    through ``Logger.handle`` to the ``logger.info(...)`` call site, which is the
    visible, debuggable behaviour the standard wants.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Raise if the record carries a reserved key; otherwise allow it."""
        collisions = RESERVED_KEYS.intersection(_extract_extras(record))
        if collisions:
            names = ", ".join(sorted(collisions))
            raise ValueError(
                f"logging extra uses reserved key(s) {{{names}}}; these names are "
                f"emitted by the structured formatter and would be overwritten. "
                f"Rename the extra field(s)."
            )
        return True


class _JsonLinesFormatter(logging.Formatter):
    """Render a record as a single-line JSON object for machine consumption.

    Output shape::

        {"ts": "...Z", "level": "INFO", "logger": "src.ocr.gemini",
         "msg": "page processed", <extras...>}
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record`` to a one-line JSON string."""
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(_extract_extras(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # ensure_ascii=False keeps Telugu (and other non-ASCII) text readable
        # rather than \u-escaped. default=str lets non-JSON-native extras such as
        # Path serialise to their string form instead of raising.
        return json.dumps(payload, ensure_ascii=False, default=str)


class _HumanFormatter(logging.Formatter):
    """Human-readable formatter matching the repo's long-standing convention.

    Produces ``<ts> <LEVEL> <logger> - <message>`` and appends any structured
    extras as ``key=value`` pairs, matching the example in
    ``docs/standards/logging_standard.md``.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record``, appending ``key=value`` extras when present."""
        base = super().format(record)
        extras = _extract_extras(record)
        if not extras:
            return base
        suffix = " ".join(f"{key}={value}" for key, value in extras.items())
        return f"{base} {suffix}"


def _reset_root_handlers(root: logging.Logger) -> None:
    """Detach and close every handler currently on the root logger.

    Called at the start of each :func:`setup_logging` invocation so configuring
    twice in one process does not double-attach handlers (and so file handlers
    from a prior call release their descriptors).
    """
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def setup_logging(
    *,
    name: str,
    structured: bool | None = None,
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> Path | None:
    """Configure the root logger for this process.

    Idempotent: existing root handlers are removed before new ones are attached,
    so calling this twice in one process does not duplicate output.

    Args:
        name: Pipeline/script name, used in the log filename when
            ``structured=True`` (e.g. ``"build_corpus_inventory"``).
        structured: ``True`` emits JSON Lines to stdout plus a timestamped file
            under ``log_dir``. ``False`` emits human-readable lines to stderr
            only (matching the prior ``logging.basicConfig`` default). ``None``
            auto-detects: ``True`` when the ``PIPELINE_STRUCTURED`` environment
            variable equals ``"1"``, else ``False``.
        log_dir: Directory for the JSON log file when ``structured=True``
            (default: ``<repo>/logs/``). Created if it does not exist.
        level: Root log level (default :data:`logging.INFO`).

    Returns:
        The :class:`~pathlib.Path` to the JSON log file when ``structured=True``,
        otherwise ``None``.
    """
    if structured is None:
        structured = os.environ.get(STRUCTURED_ENV_VAR) == "1"

    root = logging.getLogger()
    _reset_root_handlers(root)
    root.setLevel(level)

    if not structured:
        # Human mode goes to stderr, matching the prior ``logging.basicConfig``
        # default these scripts used. This preserves existing behaviour exactly
        # (stdout stays clean for machine-readable ``print`` output such as
        # ``download_dataset --list``) and follows the Unix logs-to-stderr,
        # data-to-stdout convention.
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(_HumanFormatter())
        root.addHandler(stream_handler)
        return None

    json_formatter = _JsonLinesFormatter()
    reserved_filter = _ReservedKeyFilter()

    # Structured mode tees JSON to stdout so a human watching a batch run sees
    # it scroll (per the "watch it scroll" guidance in logging_standard.md),
    # alongside the timestamped file written below for post-mortem analysis.
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(json_formatter)
    stream_handler.addFilter(reserved_filter)
    root.addHandler(stream_handler)

    target_dir = log_dir if log_dir is not None else DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime(_FILE_TIMESTAMP_FORMAT)
    log_path = target_dir / f"{name}_{timestamp}.jsonl"

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(json_formatter)
    file_handler.addFilter(reserved_filter)
    root.addHandler(file_handler)

    return log_path
