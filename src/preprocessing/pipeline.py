"""Composable preprocessing pipeline.

A :class:`Pipeline` holds an ordered list of named stages and applies the
enabled ones to an image in sequence. Each stage carries a default
on/off flag, and any stage can be toggled per-run via the ``enable`` argument
to :meth:`Pipeline.run`. That per-stage toggling is what makes the Phase 5
ablation study mechanical: the same pipeline object runs every
on/off combination without rebuilding.

See ``docs/development/phase_2_preprocessing.md`` Task 1 and Task 5.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping

import numpy as np
from numpy.typing import NDArray

from src.preprocessing.base import PreprocessingStage

logger = logging.getLogger(__name__)

# A stage entry: (name, callable, default-enabled).
StageSpec = tuple[str, PreprocessingStage, bool]


class Pipeline:
    """An ordered, individually-togglable sequence of preprocessing stages.

    Example:
        >>> from src.preprocessing import deskew, binarize, Pipeline
        >>> pipeline = Pipeline(
        ...     [
        ...         ("deskew", deskew, True),
        ...         ("binarize", binarize, True),
        ...     ]
        ... )
        >>> cleaned = pipeline.run(image)                       # all enabled
        >>> only_binarized = pipeline.run(image, enable={"deskew": False})
    """

    def __init__(self, stages: Iterable[StageSpec]) -> None:
        """Build a pipeline from an ordered iterable of stage specs.

        Args:
            stages: Ordered ``(name, callable, default_enabled)`` triples. The
                callable must accept and return a NumPy image (see
                :class:`~src.preprocessing.base.PreprocessingStage`). Stage
                names must be unique so per-run toggling is unambiguous.

        Raises:
            ValueError: If two stages share the same name.
        """
        self._stages: list[StageSpec] = list(stages)
        counts = Counter(name for name, _, _ in self._stages)
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"stage names must be unique; duplicated: {duplicates}")

    @property
    def stage_names(self) -> list[str]:
        """The stage names in pipeline order."""
        return [name for name, _, _ in self._stages]

    def run(
        self,
        image: NDArray[np.uint8],
        enable: Mapping[str, bool] | None = None,
    ) -> NDArray[np.uint8]:
        """Apply the enabled stages to ``image`` in order.

        Args:
            image: Input image as a 2-D grayscale or 3-D BGR ``uint8`` array.
            enable: Optional per-stage overrides of the default on/off flags,
                keyed by stage name. A stage absent from this mapping uses its
                default. Every key must name a stage in this pipeline.

        Returns:
            The image after the enabled stages have been applied. Note that a
            stage may change the channel count (binarize returns single-channel),
            so the output shape need not match the input. With no enabled stages
            (empty pipeline or all disabled) the input is returned unchanged.

        Raises:
            ValueError: If ``enable`` references a stage name not in the
                pipeline.
        """
        enable = enable or {}
        unknown = set(enable) - set(self.stage_names)
        if unknown:
            raise ValueError(
                f"enable references unknown stage(s): {sorted(unknown)}; "
                f"known stages: {self.stage_names}"
            )

        result = image
        for name, stage, default_enabled in self._stages:
            if not enable.get(name, default_enabled):
                logger.debug("Skipping disabled stage %r.", name)
                continue
            logger.debug("Applying stage %r.", name)
            result = stage(result)
        return result
