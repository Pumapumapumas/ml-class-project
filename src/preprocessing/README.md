# `src.preprocessing`

Modular, testable image-preprocessing pipeline for the Telugu OCR project. Each stage is an independent function that takes a NumPy image (BGR `uint8` by convention) and returns a NumPy image; a `Pipeline` composes an ordered list of stages, each individually togglable so the Phase 5 ablation study is mechanical. **Phase 2 ships two stages — deskew and binarize.** Denoise and contrast are deferred to a follow-up (see [`docs/development/phase_2_preprocessing.md`](../../docs/development/phase_2_preprocessing.md)).

## Public surface

```python
def deskew(image: NDArray[np.uint8], angle_threshold_deg: float = 0.5) -> NDArray[np.uint8]
```
Detect and correct scan skew. Skew magnitudes below `angle_threshold_deg` (or undetectable angles) return the input unchanged. Output keeps the input's shape and channel count.

```python
def binarize(image: NDArray[np.uint8], block_size: int = 11, c: int = 2) -> NDArray[np.uint8]
```
Adaptive Gaussian thresholding (`cv2.adaptiveThreshold`). Converts colour input to grayscale internally and returns a single-channel `uint8` image of only 0s and 255s. A zero-variance (uniform) image is mapped to its nearest binary extreme, since adaptive thresholding is undefined there.

```python
class Pipeline:
    def __init__(self, stages: Iterable[tuple[str, PreprocessingStage, bool]]) -> None
    def run(self, image: NDArray[np.uint8], enable: Mapping[str, bool] | None = None) -> NDArray[np.uint8]
    @property
    def stage_names(self) -> list[str]
```
Composes `(name, callable, default_enabled)` stage specs and applies the enabled ones in order. Per-run overrides via `enable={"deskew": False}` drive the ablation study.

```python
class PreprocessingStage(Protocol)
```
Structural contract every stage satisfies: `(image) -> image`. Concrete stages are plain functions and do not subclass it.

## Example

```python
from src.preprocessing import Pipeline, binarize, deskew

pipeline = Pipeline([("deskew", deskew, True), ("binarize", binarize, True)])
cleaned = pipeline.run(image)                          # both stages
only_binarized = pipeline.run(image, enable={"deskew": False})
```

## CLI

`scripts/run_preprocessing.py` walks an input directory, runs the pipeline on each image, and writes PNG outputs mirroring the input layout. Idempotent (skips existing outputs unless `--overwrite`); stages disableable via `--no-deskew` / `--no-binarize`. See the script's `--help`.
