"""Unit tests for ``src.ocr.base``.

Covers the :class:`OCRResult` value type and the :class:`OCRAdapter` structural
protocol. The protocol test doubles as the contract documentation for adapters
implemented in separate tasks (Tesseract, Surya): a minimal class exposing
``model_name`` and ``ocr`` satisfies the protocol, so those authors can verify
their implementation against the same ``isinstance`` check.
"""

from __future__ import annotations

from pathlib import Path

from src.ocr.base import OCRAdapter, OCRResult


class _MinimalAdapter:
    """Smallest object that satisfies the OCRAdapter contract."""

    model_name = "fake-1.0"

    def ocr(self, image_path: Path) -> OCRResult:
        return OCRResult(text="ఒక", model_name=self.model_name, latency_ms=1.0)


def test_minimal_adapter_satisfies_protocol():
    # @runtime_checkable verifies the structural contract (model_name + ocr).
    assert isinstance(_MinimalAdapter(), OCRAdapter)


def test_object_missing_ocr_does_not_satisfy_protocol():
    class NoOcr:
        model_name = "x"

    assert not isinstance(NoOcr(), OCRAdapter)


def test_object_missing_model_name_does_not_satisfy_protocol():
    class NoModelName:
        def ocr(self, image_path: Path) -> OCRResult:  # pragma: no cover - never called
            raise NotImplementedError

    assert not isinstance(NoModelName(), OCRAdapter)


def test_ocr_result_holds_its_fields():
    result = OCRResult(
        text="ఒక వాక్యం",
        model_name="gemini-2.5-flash",
        latency_ms=1840.0,
        raw_response={"char_count": 8},
    )
    assert result.text == "ఒక వాక్యం"
    assert result.model_name == "gemini-2.5-flash"
    assert result.latency_ms == 1840.0
    assert result.raw_response == {"char_count": 8}


def test_ocr_result_raw_response_defaults_to_none():
    result = OCRResult(text="", model_name="m", latency_ms=0.0)
    assert result.raw_response is None


def test_ocr_result_is_frozen():
    result = OCRResult(text="x", model_name="m", latency_ms=1.0)
    # frozen=True makes it a hashable value object; field assignment must fail.
    import dataclasses

    try:
        result.text = "y"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover - only reached on a contract regression
        raise AssertionError("OCRResult should be frozen")
