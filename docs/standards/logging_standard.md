# Logging Standard

**Status:** Active
**Scope:** How the OCR pipeline and supporting code emit logs. Level discipline, format, destination, and what to log vs not log.

---

## Why we have a logging standard

The OCR pipeline runs over thousands of pages, calls remote APIs, retries on failure, and writes derived files. When something goes wrong at page 472 of 4,000, the only way to figure out what happened is the log. **No `print()` calls in pipeline code** — they go to stdout, scroll off, and don't survive a batch run.

Logs are also evidence. When the report claims "Gemini correctly handled 94% of conjunct characters," the log of every Gemini call (or an aggregated summary) is the supporting record.

---

## The Python logging module

Use the standard `logging` module. Configuration goes in one place — a `src/utils/logging_config.py` module — and every other module gets its logger via:

```python
import logging
logger = logging.getLogger(__name__)
```

That gives each module its own logger named for its dotted import path (e.g., `src.preprocessing.deskew`). The format string can include `%(name)s` so log lines show which module emitted them.

**Don't:**
- Create a root logger and call `logging.info(...)` directly — it bypasses the per-module logger pattern.
- Configure logging at import time inside a library module — only the entry-point script or notebook configures.

---

## Log levels

| Level | When to use |
|-------|-------------|
| `DEBUG` | Detailed flow that helps when something is wrong. Off by default in normal runs. |
| `INFO` | Pipeline progress, normal milestones (page X done, model Y started, batch Z complete). Default on. |
| `WARNING` | Something unexpected but recoverable. Retried-and-succeeded API calls, missing optional metadata, falling back to a default. |
| `ERROR` | Something failed and the pipeline cannot make progress on this unit of work (this page, this batch). The pipeline may still continue with other work. |
| `CRITICAL` | The pipeline cannot continue at all. Misconfiguration, missing required credentials, corrupted dataset. |

**Discipline:** don't log every line at `INFO` to make the run feel busy. A noisy log obscures the real signal. Aim for the rule: "if a user reads the log top to bottom, every `INFO` line should tell them something they'd want to know."

---

## What to log

**Always log:**
- Pipeline start/end with timestamps
- Configuration (model name, batch size, input directory) at start
- Each batch transition (page N of M, or "starting batch X of Y")
- Every API call attempt and outcome (success, retry, hard failure)
- Errors with full context: which file, which page, which model, what error

**Conditionally log:**
- Per-page successes only at `DEBUG` (otherwise you get one INFO per page → thousands of lines)
- Intermediate values (extracted text length, processing time) at `DEBUG`
- Performance counters (pages/min, tokens/min) at `INFO` every N pages, not every page

**Never log:**
- API keys, tokens, credentials
- Full prompt contents that include user-provided sensitive data
- The full content of OCR outputs at `INFO` (they're huge — log them at `DEBUG` only, and only when explicitly debugging)

---

## Log format

For pipeline runs, use a structured, machine-readable format. JSON lines (one JSON object per log line) is easy to grep and easy to analyze later:

```
{"ts": "2026-06-09T14:23:01Z", "level": "INFO", "logger": "src.ocr.gemini", "msg": "page processed", "page_id": "book_034_page_217", "model": "gemini-2.5-flash", "duration_ms": 1840, "chars": 1923}
```

A helper formatter in `src/utils/logging_config.py` emits this format when the pipeline runs. For interactive/notebook use, a plain human-readable formatter is fine:

```
2026-06-09 14:23:01 INFO   src.ocr.gemini - page_id=book_034_page_217 model=gemini-2.5-flash duration_ms=1840 chars=1923
```

The entry-point script picks which formatter via the `PIPELINE_STRUCTURED` environment variable (`1` → JSON Lines, unset → human-readable). An environment variable rather than a CLI flag keeps each script's `--help` output unchanged when the structured path is wired in. This is implemented in `src/utils/logging_config.py` as `setup_logging(...)`, which every CLI in `scripts/` calls once at startup.

---

## Log destinations

| Destination | When |
|-------------|------|
| **stderr** | Human-readable mode (default, interactive/dev work). `setup_logging` writes human logs here so stdout stays clean for machine-readable `print` output. |
| **stdout** | Structured (JSON Lines) mode tees here too, so a batch run can be watched scrolling live. |
| **`logs/<name>_<timestamp>.jsonl`** | Batch pipeline runs (structured mode). One new file per run; `<name>` is the pipeline/script name passed to `setup_logging`, `<timestamp>` is the UTC start time (`%Y%m%dT%H%M%SZ`). |
| **`logs/pipeline_summary_<timestamp>.txt`** | Human-readable summary at end of run: total pages, total errors, total time, per-model breakdown. _(Planned — not yet implemented.)_ |

`logs/` is gitignored. Logs are an artifact of running the pipeline, not source-controlled content.

For long-running pipelines, both stdout AND file is good — stdout for "watch it scroll," file for post-mortem.

---

## Error handling and logs

Per the [Python Code Standard](./python_code_standard.md): exceptions are diagnostic information. Logging an error and re-raising is fine. Swallowing an error silently is not.

```python
# Good — logs the error with context, then re-raises so the caller can decide
try:
    result = call_gemini(image_path)
except GeminiApiError as e:
    logger.error(
        "Gemini OCR failed",
        extra={"page_id": page_id, "error": str(e), "image_path": str(image_path)},
    )
    raise

# Bad — silently turns the error into a None
try:
    result = call_gemini(image_path)
except:
    result = None
```

---

## Logging from notebooks

Notebooks are interactive and noisy is fine. Use the same logger pattern (`logging.getLogger(__name__)`) so the imports from `src/` participate, and configure with a simple stdout handler at INFO. Don't write notebook logs to the `logs/` directory — those are for batch pipeline runs.

---

## Reviewing logs

A pipeline run produces `logs/<name>_<timestamp>.jsonl` (e.g. `run_preprocessing_20260609T140000Z.jsonl`). Quick analysis patterns:

```bash
# Count errors per model
jq -r 'select(.level=="ERROR") | .model' logs/run_preprocessing_20260609T140000Z.jsonl | sort | uniq -c

# Time per page distribution
jq -r 'select(.msg=="page processed") | .duration_ms' logs/run_preprocessing_20260609T140000Z.jsonl

# Find the slowest pages
jq -s 'sort_by(.duration_ms) | reverse | .[0:10]' logs/run_preprocessing_20260609T140000Z.jsonl
```

These get faster than `grep` once you have JSON-structured logs.

---

## When in doubt

- More `DEBUG` is free if you don't enable it in production runs. Sprinkle generously, leave it off by default, turn it on when something needs investigation.
- Less `INFO` is better than more. Every `INFO` line is a claim that the reader needs to know about that event.
- A log line you can't write without leaking a secret is a log line you shouldn't write.
