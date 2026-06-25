"""Tesseract OCR adapter — classical OCR baseline.

Wraps the Tesseract 5 binary running inside the project's pinned Docker
image (``ml-class-project/tesseract``) so the host workstation does not
need ``sudo apt install tesseract-ocr-tel``. The image already includes
the Telugu language pack (verified with ``tesseract --list-langs``).

Conforms to the :class:`~src.ocr.base.OCRAdapter` contract: input is an
image ``Path``, output is NFC-normalized Unicode text via
:class:`~src.ocr.base.OCRResult`.

Distinct from the LLM adapters in three ways worth noting in the report:

1. **Local execution.** No API key, no network, no rate limit. The cost
   model is CPU-seconds, not dollars.
2. **No retry loop.** Tesseract is deterministic — there is no "transient
   error" to retry. A failure here is structural (Docker not running,
   image missing, language pack absent) and is surfaced immediately.
3. **No refusal heuristic.** Tesseract cannot refuse a request the way an
   LLM can; an empty output simply means it found no extractable text on
   the page. We pass that through as ``OCRResult(text="")`` so the batch
   manifest records it without raising.

Standards: see ``docs/standards/environment_standard.md`` ("Hybrid
host+Docker" rationale) and ``docs/standards/python_code_standard.md``.

See ``docs/development/phase_3_ocr_pipeline.md`` Task 4.
"""

from __future__ import annotations

import logging
import subprocess
import time
import unicodedata
from pathlib import Path

from src.ocr.base import OCRResult

LOG = logging.getLogger(__name__)

# Model identifier surfaced in OCRResult.model_name. Hardcoded because the
# Docker image is pinned and the language pack does not change between
# runs. If we ever rebuild the image with a different Tesseract version,
# bump this string so downstream analysis can tell them apart.
MODEL_NAME = "tesseract-5-tel"

# The Docker image tag — must match docker/tesseract/Dockerfile and the
# environment_standard.md "all images are pinned" rule. The base
# ``ubuntu:22.04`` ship in our Dockerfile pins Tesseract to whatever 5.x
# Ubuntu Jammy ships, which is acceptable for a reproducibility baseline.
DOCKER_IMAGE = "ml-class-project/tesseract"

# Tesseract language code. The image was built with the ``tesseract-ocr-tel``
# package; "tel" is Telugu's ISO-639-3 code in Tesseract's language
# catalog.
TESSERACT_LANG = "tel"

# Page segmentation mode. PSM 6 = "Assume a single uniform block of text",
# which fits our book-page corpus better than the default PSM 3 (fully
# automatic page segmentation) — Tesseract's auto layout detector tends to
# fragment Telugu paragraphs across detected blocks and reorder them.
TESSERACT_PSM = "6"

# Wall-clock cap for a single Tesseract call. Empirically each page on
# the eval subset finishes in 5-15 seconds; 60 seconds is well above that
# but well below "hung forever".
TESSERACT_TIMEOUT_SECONDS = 60


class TesseractAdapter:
    """OCR adapter backed by the project's Tesseract 5 Docker image.

    Satisfies the :class:`~src.ocr.base.OCRAdapter` protocol. No
    constructor parameters; the Docker image is pinned at module level so
    every batch run uses the same Tesseract version and language pack.

    Attributes:
        model_name: ``"tesseract-5-tel"``. Same as ``MODEL_NAME``.
    """

    model_name: str = MODEL_NAME

    def __init__(self) -> None:
        """Verify the Docker image is available before any OCR call.

        Failing here (rather than per-page during a batch) lets the user
        diagnose missing Docker / missing image before a long batch starts
        wasting wall-clock.

        Raises:
            RuntimeError: If the Docker CLI is missing, the daemon is
                unreachable, or the pinned image is not present locally.
        """
        try:
            inspect = subprocess.run(
                ["docker", "image", "inspect", DOCKER_IMAGE],
                capture_output=True,
                check=False,
                timeout=10,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "docker CLI not found on PATH. Tesseract runs inside the "
                f"{DOCKER_IMAGE} container per environment_standard.md."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "docker CLI timed out responding. Is the Docker daemon running?"
            ) from exc

        if inspect.returncode != 0:
            raise RuntimeError(
                f"Docker image {DOCKER_IMAGE!r} is not present locally. Build it with: "
                "`docker build -t ml-class-project/tesseract docker/tesseract/`"
            )

    def ocr(self, image_path: Path) -> OCRResult:
        """Run Tesseract OCR on a single page image.

        Args:
            image_path: Path to a readable JPEG/PNG page image.

        Returns:
            An :class:`~src.ocr.base.OCRResult` with the NFC-normalized
            Telugu text, the model identifier, the call's wall-clock
            latency in milliseconds, and the raw Tesseract stdout
            preserved as ``raw_response`` for debugging.

        Raises:
            FileNotFoundError: If ``image_path`` does not exist or is not
                readable.
            RuntimeError: If the Docker invocation fails (non-zero exit,
                stderr contains diagnostics), times out, or the
                container's stdout is not decodable UTF-8.
        """
        if not image_path.is_file():
            raise FileNotFoundError(f"image not found: {image_path}")

        image_bytes = image_path.read_bytes()

        # Tesseract command-line:
        #   tesseract <input> <output> -l <lang> --psm <psm>
        # The single ``-`` for input means "read from stdin"; ``stdout``
        # for output means "write recognized text to stdout instead of a
        # .txt file". We invoke via `docker run -i` (interactive — wires
        # our stdin to the container) and `--rm` (remove the container
        # when it exits — no accumulated state).
        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            DOCKER_IMAGE,
            "tesseract",
            "-",
            "stdout",
            "-l",
            TESSERACT_LANG,
            "--psm",
            TESSERACT_PSM,
        ]

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                input=image_bytes,
                capture_output=True,
                check=False,
                timeout=TESSERACT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Tesseract timed out after {TESSERACT_TIMEOUT_SECONDS} s on {image_path.name}"
            ) from exc

        latency_ms = (time.time() - start) * 1000.0

        if result.returncode != 0:
            stderr_tail = result.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(
                f"Tesseract exited with status {result.returncode} on "
                f"{image_path.name}. Stderr tail: {stderr_tail!r}"
            )

        try:
            raw_text = result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            # Tesseract should always produce UTF-8 with the Telugu pack,
            # but defend against an image somehow producing garbage bytes.
            raise RuntimeError(
                f"Tesseract output for {image_path.name} was not valid UTF-8: {exc}"
            ) from exc

        text = unicodedata.normalize("NFC", raw_text)

        if not text.strip():
            # Tesseract found nothing extractable. Log at INFO (not WARNING)
            # because for damaged / blank pages this is the correct behavior
            # — we want the empty result captured in the batch manifest, not
            # treated as an error.
            LOG.info("Tesseract produced empty output for %s", image_path.name)

        return OCRResult(
            text=text,
            model_name=MODEL_NAME,
            latency_ms=latency_ms,
            raw_response=raw_text,
        )
