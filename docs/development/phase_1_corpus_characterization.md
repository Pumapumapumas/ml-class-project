# Phase 1 — Corpus Characterization

**Status:** Current phase. Compressed from instructor's Week 1 to ~2 days.
**Time estimate:** 2 days (1.5 calendar days of work, split across team).
**Rubric dimension:** Dimension 1 — Corpus Characterization and Problem Scoping (10 pts).

---

## Goal

Profile the `AlbertoChestnut/telugu-ocr` HuggingFace corpus enough to (a) justify the preprocessing choices we make in Phase 2, (b) select a stratified 30-page evaluation subset that exercises the quality range, and (c) produce a corpus characterization report suitable for the final submission.

The instructor's spec asks teams to "sample 30-50 pages across the quality spectrum and annotate them manually." We skip manual annotation entirely: the HuggingFace corpus ships paired `.jpg` + `.txt` files, so the ground truth is already present. Our job is to characterize what we have, not to create it.

---

## Dependencies

- Phase 0 complete (dataset download script, repo structure, env). [Done]
- Network access to HuggingFace Hub and ~30 GB free disk for the full corpus (or ~500 MB for a representative subset).
- Decision on whether to download the full ~13 GB corpus or a stratified subset for development. See open questions.

---

## Tasks

### 1. Download and inventory the corpus [Eric] — COMPLETE

- [x] Run `scripts/download_dataset.py` with whichever subset size we settle on (5-book subset)
- [x] Record total book count, total page count, total bytes (5 books, 415 paired pages, 190 MB)
- [x] Verify the paired-file invariant (every `.jpg` has a matching `.txt`); log mismatches (0 mismatches)
- [x] Spot-check 5 random `.txt` files for encoding (UTF-8 NFC vs NFD) and basic plausibility (all 5 NFC, valid Telugu glyphs)

**Completion criterion:** ✅ CSV at `data/external/corpus_inventory.csv` with one row per page (`book_id, page_id, image_path, text_path, image_bytes, text_bytes, image_width, image_height`). Paths are repo-relative for cross-machine portability.

**Implementation:** `src/utils/corpus_inventory.py` (library) + `scripts/build_corpus_inventory.py` (CLI) + 29 unit tests in `src/utils/tests/test_corpus_inventory.py`. Regenerate the CSV with `python scripts/build_corpus_inventory.py`.

### 2. Compute basic statistics [Teammate — recommended first PR]

- [ ] Image dimension distribution (histogram of width × height)
- [ ] DPI estimate (if available in EXIF or inferable from dimensions)
- [ ] Mean / median page text length (character count)
- [ ] File-size distribution (proxy for scan quality variance)

**Completion criterion:** A notebook `notebooks/01_corpus_characterization.ipynb` that loads the inventory CSV and produces the four distributions as plots, plus a `corpus_stats.json` artifact in `data/external/` with the headline numbers.

#### Walk-through for Rauf

**Why this task matters.** Before we design preprocessing (Phase 2) or pick OCR models (Phase 3), we need to know what is actually IN the dataset. How big are the images? How wide are the pages? Are some books much longer than others? These statistics drive every downstream decision — for example, if all images are 2000+ pixels wide we may need to downsize before sending to Gemini (cost / latency). Your charts and numbers become the foundation of the corpus characterization report.

**What you will produce.**
- One Jupyter notebook at `notebooks/01_corpus_characterization.ipynb` with four labeled plots and brief observations under each.
- One JSON file at `data/external/corpus_stats.json` with the headline numbers.

**Where the data is.** Eric committed `data/external/corpus_inventory.csv` — one row per page, 415 rows total. Every column you need is already there. You will not need to read individual image or text files for any of these stats.

**How to start.** Create the notebook file in VS Code (`File → New File → Jupyter Notebook`, save as `notebooks/01_corpus_characterization.ipynb`). First cell — imports and load the CSV:

```python
import pandas as pd
import matplotlib.pyplot as plt
import json
from pathlib import Path

REPO_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
df = pd.read_csv(REPO_ROOT / "data" / "external" / "corpus_inventory.csv")
print(f"Total pages: {len(df)}")
print(f"Books: {df['book_id'].nunique()}")
df.head()
```

Run that cell with `Shift+Enter`. You should see 415 pages, 5 books, and a small table of the first few rows. If this works, you are set up.

**Plot 1 — Image dimensions.** Each row has `image_width` and `image_height`. A 2D scatter plot (width on x, height on y) shows whether all pages have similar dimensions or there is spread. One approach:

```python
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(df["image_width"], df["image_height"], s=10, alpha=0.4)
ax.set_xlabel("Image width (pixels)")
ax.set_ylabel("Image height (pixels)")
ax.set_title("Image dimensions across the corpus")
plt.show()
```

**Plot 2 — DPI estimate.** DPI = dots (pixels) per inch. The EXIF approach (reading metadata from each `.jpg`) is slow and most scanned books do not have EXIF DPI set. The simpler approach: **assume a typical Indian-language book is ~6 inches wide**, then `dpi_estimate = image_width / 6`. Plot a histogram of those estimates:

```python
df["dpi_estimate"] = df["image_width"] / 6.0
fig, ax = plt.subplots(figsize=(7, 5))
df["dpi_estimate"].plot(kind="hist", bins=30, ax=ax)
ax.set_xlabel("Estimated DPI (assumes 6-inch page width)")
ax.set_title("Estimated scan DPI")
plt.show()
```

In your markdown cell under the plot, note that this is an estimate and that the 6-inch assumption is an industry-typical book size.

**Plot 3 — Page text length.** The CSV's `text_bytes` column is the file size of each ground-truth `.txt` in bytes — a reasonable proxy for the amount of text on that page. (Telugu in UTF-8 is multi-byte per character so bytes ≠ characters, but for distribution shape it does not matter.)

```python
fig, ax = plt.subplots(figsize=(7, 5))
df["text_bytes"].plot(kind="hist", bins=30, ax=ax)
ax.set_xlabel("Text file size (bytes)")
ax.set_title("Ground-truth text length per page")
plt.show()
print(f"Mean text bytes: {df['text_bytes'].mean():.0f}")
print(f"Median text bytes: {df['text_bytes'].median():.0f}")
```

**Plot 4 — File-size distribution.** Image file size varies with content complexity (a mostly-blank page compresses tiny; a page with dense text + ink bleed compresses large). It is a rough scan-quality proxy.

```python
fig, ax = plt.subplots(figsize=(7, 5))
(df["image_bytes"] / 1024).plot(kind="hist", bins=30, ax=ax)
ax.set_xlabel("Image file size (KB)")
ax.set_title("Image file size distribution")
plt.show()
```

**JSON output.** Collect the headline numbers and write them to `data/external/corpus_stats.json`. Suggested fields (use whatever names you find clearest; just be consistent):

```python
stats = {
    "total_books": int(df["book_id"].nunique()),
    "total_pages": int(len(df)),
    "median_image_width_px": int(df["image_width"].median()),
    "median_image_height_px": int(df["image_height"].median()),
    "median_estimated_dpi": float(round(df["dpi_estimate"].median(), 1)),
    "mean_text_bytes": int(df["text_bytes"].mean()),
    "median_text_bytes": int(df["text_bytes"].median()),
    "median_image_bytes": int(df["image_bytes"].median()),
}

out = REPO_ROOT / "data" / "external" / "corpus_stats.json"
out.write_text(json.dumps(stats, indent=2))
print(f"Wrote {out}")
print(json.dumps(stats, indent=2))
```

**Add brief observations.** Under each plot, add a markdown cell with one or two sentences on what you see. For example: *"Most pages are around 1500x2100 pixels, with one cluster of taller pages around 2400 px height. This suggests at least two scanner/page-size conventions in the source books."* This is the kind of analysis the rubric rewards.

**What good looks like.**
- Notebook runs top-to-bottom without errors after restarting the kernel.
- All four plots have titles and axis labels.
- Each plot has one or two sentences of observation underneath.
- `corpus_stats.json` exists and contains the headline numbers.
- `git status` shows both `notebooks/01_corpus_characterization.ipynb` and `data/external/corpus_stats.json` as new files — both should be committed.

**Common pitfalls.**
- **Path errors:** the notebook lives in `notebooks/` but the CSV lives in `data/external/`. Use `pathlib.Path` and join from the repo root, as in the starter code above. Avoid `os.chdir`.
- **Plots not showing:** if you do not see the plot, add `%matplotlib inline` as the first line of an early cell.
- **JSON serialization errors:** pandas/numpy types (like `int64`) are NOT JSON-serializable by default. Wrap each value in `int(...)` or `float(...)` before saving — the starter code above does this.
- **Cell ordering:** before committing, restart the kernel (`Kernel → Restart`) and run all cells top-to-bottom. A notebook that requires running cells out of order is broken.

**Open a draft PR early.** You do not need to finish before opening a Pull Request. Open it as a draft as soon as the notebook can run the first cell. This lets Eric see your progress and give early feedback. See the [Git Workflow Standard](../standards/git_workflow_standard.md) for the commit message format.

### 3. Define a quality taxonomy [Eric]

- [ ] Visually inspect ~50 pages sampled across the file-size and dimension range
- [ ] Bucket scan-quality artifacts into 3-5 categories (proposed: clean / faded / skewed / noisy / multi-column-or-complex-layout)
- [ ] Write the taxonomy definitions into `reports/corpus_characterization.qmd` with one example image per bucket

**Completion criterion:** Taxonomy documented with image examples. Each bucket has a written definition concrete enough that a different annotator would assign the same bucket to the same page ~80% of the time.

### 4. Select stratified 30-page evaluation subset [Eric]

- [ ] Sample ~6 pages per quality bucket (30 total) — stratified, not random
- [ ] Freeze the selection: write `data/external/eval_subset.csv` listing the 30 page IDs
- [ ] Copy the 30 image+text pairs to `data/external/eval_subset/` so the rest of the pipeline references a stable location
- [ ] Add a one-paragraph note in the report explaining why stratified sampling matters here

**Completion criterion:** `data/external/eval_subset/` contains 30 paired files; `eval_subset.csv` is committed (the CSV is metadata, not data — small enough to track).

### 5. Draft corpus characterization report [Eric writes prose, Teammate produces figures/tables]

- [ ] Eric: create `reports/corpus_characterization.qmd` skeleton with section headers
- [ ] Eric: write prose for sections — dataset provenance + citation, methodology narrative, quality taxonomy definitions, eval-subset methodology rationale, challenges linked to preprocessing (this last link moves the rubric from 7-8 to 9-10)
- [ ] Teammate: produce the statistics tables and plots embedded in the report (pulled from `notebooks/01_corpus_characterization.ipynb`)
- [ ] Teammate: produce the one example image per quality bucket figure
- [ ] Eric: integrate, render to PDF, confirm Telugu glyphs render without `[]` boxes

**Completion criterion:** PDF rendered, both team members reviewed, no obvious gaps. Telugu text renders correctly. Split protects the rubric by keeping English-prose authority on Eric while giving the teammate the visual/numerical content load.

#### Walk-through for Rauf

**Why this task matters.** The corpus characterization report is the first thing the grader reads. The numbers and figures you produce ARE the visible evidence that the team understood the data. Eric writes the prose, you produce the figures and tables — your work is in the report, not just in a notebook.

**What you will produce.**
- Saved versions of the four plots from Task 2, in PNG format, under `reports/figures/corpus/`. Eric will embed them in the report.
- A small CSV or markdown table summarising the headline statistics (so Eric can paste the table directly into the Quarto doc).
- Once Eric has finished Task 3 (quality taxonomy), one example image per quality bucket, also saved under `reports/figures/corpus/`. Eric will tell you which page IDs to extract.

**How to start.** After Task 2 is merged, open your notebook and add a few cells at the bottom that save the existing plots to disk:

```python
from pathlib import Path

FIG_DIR = REPO_ROOT / "reports" / "figures" / "corpus"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Example for the dimensions plot — repeat for each of the four:
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(df["image_width"], df["image_height"], s=10, alpha=0.4)
ax.set_xlabel("Image width (pixels)")
ax.set_ylabel("Image height (pixels)")
ax.set_title("Image dimensions across the corpus")
fig.savefig(FIG_DIR / "dimensions_scatter.png", dpi=150, bbox_inches="tight")
plt.show()
```

The `bbox_inches="tight"` argument trims white space and `dpi=150` makes the saved image sharp for the report.

**For the headline table.** Eric will tell you which numbers he wants in the table. A quick approach: build a small DataFrame and save it as both CSV and markdown:

```python
table = pd.DataFrame({
    "Metric": ["Books", "Pages", "Median width (px)", "Median height (px)",
               "Median estimated DPI", "Median text bytes", "Median image bytes"],
    "Value":  [stats["total_books"], stats["total_pages"],
               stats["median_image_width_px"], stats["median_image_height_px"],
               stats["median_estimated_dpi"], stats["median_text_bytes"],
               stats["median_image_bytes"]],
})
table.to_csv(REPO_ROOT / "reports" / "figures" / "corpus" / "headline_stats.csv", index=False)
print(table.to_markdown(index=False))
```

The markdown output can be copy-pasted directly into Eric's Quarto doc.

**What good looks like.** All figures saved as PNG at 150 DPI under `reports/figures/corpus/`. The headline-stats CSV is committed. When Eric inserts the figures into the report, they look sharp and the labels are readable.

**Communication.** Eric will ping you in chat when his prose draft is ready and ask for specific figures by name. Just be available to re-render with tweaks (font size, color, axis range) if he asks.

### 6. Mark phase complete and hand off [Eric]

- [ ] Update `roadmap.md` status header to "Phase 2 + Phase 3 start (parallel)"
- [ ] Tick Phase 1 checkboxes in `roadmap.md`
- [ ] Note any loose ends in [`loose_ends.md`](loose_ends.md)

---

## Open questions / decisions needed

1. ~~**Subset size for development.**~~ **DECIDED:** 5-book subset (415 paired pages, 190 MB) for Phase 1–2. Pull more if the 500-page submission deliverable demands it; otherwise iterate on this.
2. **Quality taxonomy bucket count.** 3 buckets is faster but reads weak in the report; 5 buckets is more defensible but takes longer. Defaulting to 4 unless the team disagrees.
3. ~~**Does Eric's teammate read Telugu?**~~ **DECIDED:** No (neither of us). Taxonomy stays at the visual-artifact level (which is what the rubric actually asks for anyway).
4. **Do we trust every `.txt` as ground truth?** The dataset is community-contributed. Phase 4's LLM validation will indirectly stress-test the ground truth. If we find ground-truth quality issues, surface in [`loose_ends.md`](loose_ends.md) and discuss in the report's limitations section.

---

## Outputs / deliverables

- `data/external/corpus_inventory.csv` — full inventory.
- `data/external/corpus_stats.json` — headline statistics.
- `data/external/eval_subset.csv` — frozen 30-page selection.
- `data/external/eval_subset/` — copied paired files for stable downstream reference.
- `notebooks/01_corpus_characterization.ipynb` — exploration + plots.
- `reports/corpus_characterization.qmd` + rendered PDF — the graded artifact.

---

## Risks

- **Telugu rendering in PDF.** Quarto's default PDF engine may not have a Telugu font available. Mitigation: render to HTML first and verify; switch PDF engine to `xelatex` with a Telugu-supporting font if needed.
- **Corpus inventory takes longer than expected.** 13 GB across 221 books, iterating per-file metadata can be slow. Mitigation: parallelize with `concurrent.futures` if single-threaded crosses 30 minutes.
- **Quality taxonomy is the squishy part.** Visual judgment is subjective. Mitigation: keep buckets few (4) and definitions concrete (artifact-driven, not interpretive).
