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

**What this task accomplishes.** Get the Telugu page images and ground-truth text files onto local disk, verify the dataset's "every `.jpg` has a matching `.txt`" invariant, and produce a single CSV that lists every page in the corpus with its metadata. That CSV becomes the canonical "table of contents" everything else in the project reads from — Phase 1's stats notebook loads it directly, Phase 2's preprocessing CLI walks it, Phase 3's OCR batch runner iterates over it, and Phases 4 and 5 join their per-page metrics back to it. Without this CSV, no downstream task can find or describe the data.

**Data flow.** This task is two scripts running in sequence:

```
HuggingFace Hub
  │
  │   scripts/download_dataset.py --subset 5
  ▼
data/raw/telugu-ocr/<book_id>/page_NNNN.jpg + page_NNNN.txt
  │
  │   scripts/build_corpus_inventory.py
  ▼
data/external/corpus_inventory.csv
```

`download_dataset.py` pulls raw files from HuggingFace using a pinned dataset revision (`f2bd895b...` — pinned for reproducibility between teammates) and normalizes any leading-dot directory names. `build_corpus_inventory.py` walks the downloaded files, pairs each `.jpg` with its matching `.txt`, uses Pillow to extract image dimensions, and writes the metadata CSV plus a JSON Lines mismatch report. The CSV is committed to git so teammates do not need to re-download the raw data just to read it.

**Sub-tasks** (verified during execution):

- [x] Run `scripts/download_dataset.py` with the chosen subset size (5-book subset)
- [x] Record total book count, total page count, total bytes (5 books, 415 paired pages, 190 MB)
- [x] Verify the paired-file invariant (every `.jpg` has a matching `.txt`); log mismatches (0 mismatches)
- [x] Spot-check 5 random `.txt` files for encoding (UTF-8 NFC vs NFD) and basic plausibility (all 5 NFC, valid Telugu glyphs)

**Completion criterion:** ✅ CSV at `data/external/corpus_inventory.csv` with one row per page: `book_id, page_id, image_path, text_path, image_bytes, text_bytes, image_width, image_height`. Paths are repo-relative for cross-machine portability.

**Implementation:**

| File | Role |
|------|------|
| `scripts/download_dataset.py` | CLI — pulls a configurable subset of books from HuggingFace at a pinned revision, normalizes leading-dot directory names, writes the raw paired files under `data/raw/telugu-ocr/`. |
| `src/utils/corpus_inventory.py` | Library — pure functions: `pair_files`, `extract_image_dimensions`, `walk_corpus`, `write_csv` (with portable-path rewriting), `write_mismatch_report`, `spot_check_encoding`. |
| `scripts/build_corpus_inventory.py` | Thin CLI wrapper that calls the library, writes the CSV plus a JSON Lines mismatch report under `logs/`, and runs the encoding spot-check. |
| `src/utils/tests/test_corpus_inventory.py` | 29 unit tests covering pairing logic, edge cases, dimension extraction, CSV format, mismatch reporting, and seed-deterministic sampling. |

**How to verify or regenerate.**

```bash
# Regenerate the CSV from whatever is currently on disk
python scripts/build_corpus_inventory.py

# Re-pull the dataset from scratch, then rebuild the inventory
rm -rf data/raw/telugu-ocr/
python scripts/download_dataset.py --subset 5
python scripts/build_corpus_inventory.py

# Run the test suite for the inventory module
pytest src/utils/tests/
```

### 2. Compute basic statistics [Teammate — recommended first PR]

**What this task accomplishes.** Transform the 415-page inventory CSV into the headline numerical and visual story of the corpus. The four plots (image dimensions, estimated DPI, per-page text length, image file sizes) plus a small JSON summary become Phase 1's primary numerical deliverables. They feed directly into Task 5's report — Eric's prose narrates Rauf's figures. Without this task, we have raw data but no characterization, and "characterization" is exactly what Dimension 1 of the rubric is named after.

**Data flow / how it works.**

```
data/external/corpus_inventory.csv
  │
  │   notebooks/01_corpus_characterization.ipynb
  │     (pandas: stats; matplotlib: 4 plots)
  ▼
data/external/corpus_stats.json     (committed — small)
reports/figures/corpus/*.png        (Task 5 picks these up for the report)
```

The notebook depends only on the inventory CSV — no images are opened, no `.txt` files read. All four plots derive from columns already in the inventory (`image_width`, `image_height`, `image_bytes`, `text_bytes`).

**Sub-tasks**:

- [ ] Image dimension distribution (histogram of width × height)
- [ ] DPI estimate (if available in EXIF or inferable from dimensions)
- [ ] Mean / median page text length (character count)
- [ ] File-size distribution (proxy for scan quality variance)

**Completion criterion:** A notebook `notebooks/01_corpus_characterization.ipynb` that loads the inventory CSV and produces the four distributions as plots, plus a `corpus_stats.json` artifact in `data/external/` with the headline numbers.

**Implementation.** `notebooks/01_corpus_characterization.ipynb` (Rauf authors), `data/external/corpus_stats.json` (notebook produces). No new source files under `src/` — this is exploratory analysis territory per the [Repository Layout Standard](../standards/repo_layout_standard.md).

**How to verify when complete.**

- Notebook runs top-to-bottom without errors after kernel restart
- `data/external/corpus_stats.json` exists and contains the headline numbers
- All four plots have titles, axis labels, and a one-sentence observation underneath each

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

**What this task accomplishes.** Create a small, well-defined set of "quality buckets" that describe the different ways scans in this corpus vary — clean print vs faded vs skewed vs noisy vs complex layout. These buckets become (a) the dimension along which Task 4 stratifies the 30-page evaluation subset, (b) the dimension along which Phase 5 reports per-bucket OCR performance ("Gemini drops 12 CER points on faded pages"), and (c) the basis for the "what kinds of pages does this corpus contain?" narrative in the report. Without this taxonomy, the eval subset is just a random sample and we cannot make any per-quality-condition claims downstream.

**Data flow / how it works.** This is a human-in-the-loop task. Pandas helps pick a stratified browsing sample, but the bucketing decision is visual judgment. The browsing sample is stratified across the cheap proxies for scan complexity (image file size and image width) so the ~50 pages cover the variation rather than clustering in one mode.

```
data/external/corpus_inventory.csv
  │
  │   pandas: stratify by image_bytes and image_width quantiles
  ▼
~50 sample page paths
  │
  │   Eric: visual inspection in a file viewer
  ▼
3-5 bucket definitions (written prose)
  +
4-5 example images (one per bucket) saved to reports/figures/corpus/quality_examples/
```

**Sub-tasks**:

- [x] Visually inspect ~50 pages sampled across the file-size and dimension range (47 pages, 5 books × 5 image-file-size quintiles, browsed 2026-06-23)
- [x] Bucket scan-quality artifacts into 3-5 categories — **5 buckets defined**: Clean / Skewed / Complex Layout / Faded / Damaged-or-Content-Loss, plus `has_latin_chars` secondary tag
- [x] Write the taxonomy definitions into `reports/corpus_characterization.qmd` — full definitions with inclusion criteria, disambiguation rules, priority ordering, and OCR-relevance notes
- [x] Pick one canonical example image per bucket and place under `reports/figures/corpus/quality_examples/<bucket>.jpg` — all 5 selected from the browsing sample; bonus `damaged_torn.jpg` retained for optional richer Damaged section in the final report

**Completion criterion:** Taxonomy documented with image examples. Each bucket has a written definition concrete enough that a different annotator would assign the same page to the same bucket ~80% of the time.

**Implementation.** No new source code — pandas one-liners in a scratch notebook or REPL to pick the stratified browsing sample, then a file-viewer pass over the ~50 pages. The outputs are:

| Artifact | Where |
|----------|-------|
| Bucket definitions (prose) | `reports/corpus_characterization.qmd`, taxonomy section |
| Example images per bucket | `reports/figures/corpus/quality_examples/<bucket>.jpg` |

**How to verify when complete.**

- 3-5 bucket definitions are written in the report with one example image each
- Re-reading the definitions a week later, you can apply them consistently to a new page you have not seen before (this is the "would a second annotator agree ~80%" test)

### 4. Select stratified 30-page evaluation subset [Eric]

**What this task accomplishes.** Freeze a small, fixed set of 30 pages that every Phase 3 OCR run, every Phase 4 CER/WER computation, and every Phase 5 per-quality analysis is scored against. "Stratified" means we draw roughly equal numbers from each quality bucket (Task 3), so a "5% mean CER" claim does NOT silently hide "Gemini is great on clean pages and terrible on noisy ones." Without this freeze, downstream phases have no stable target — re-running validation on different page samples would give different numbers and we could not legitimately compare model A on Tuesday with model B on Wednesday.

**Data flow / how it works.**

```
data/external/corpus_inventory.csv  +  quality taxonomy (Task 3)
  │
  │   scripts/select_eval_subset.py
  │     random.choices per bucket, seed-fixed for reproducibility
  ▼
30 selected (book_id, page_id) pairs
  │
  ├── data/external/eval_subset.csv   (committed to git — metadata)
  └── data/external/eval_subset/
        ├── <book_id>/<page>.jpg      (copies, NOT symlinks)
        └── <book_id>/<page>.txt      (copies, NOT symlinks)
```

Copies rather than symlinks because Phase 2 preprocessing will write derived versions next to the originals, and downstream tooling should not have to chase symlinks across filesystem boundaries.

**Sub-tasks**:

- [ ] Sample ~6 pages per quality bucket (30 total) — stratified, not random
- [ ] Freeze the selection: write `data/external/eval_subset.csv` listing the 30 page IDs
- [ ] Copy the 30 image+text pairs to `data/external/eval_subset/` so the rest of the pipeline references a stable location
- [ ] Add a one-paragraph note in the report explaining why stratified sampling matters here

**Completion criterion:** `data/external/eval_subset/` contains 30 paired files; `eval_subset.csv` is committed (the CSV is metadata, not data — small enough to track).

**Implementation.** Small script at `scripts/select_eval_subset.py` (to be written). Reads the inventory CSV, joins on the bucket tags from Task 3 (either a separate CSV that Eric writes during Task 3 OR hand-tagged in a notebook), draws stratified using `random.Random(seed=42)` for reproducibility, writes the eval-subset CSV, copies 60 files (30 `.jpg` + 30 `.txt`) to the eval-subset directory. Could also live as a function in `src/utils/` if we want it tested, but a script is fine for a one-shot freeze.

**How to verify when complete.**

```bash
ls data/external/eval_subset/*/*.jpg | wc -l   # → 30
ls data/external/eval_subset/*/*.txt | wc -l   # → 30
wc -l data/external/eval_subset.csv            # → 31 (header + 30)
```

Plus: each bucket has 6 (±1) pages in the selection — a quick `pandas` value-counts on the bucket column of `eval_subset.csv` confirms.

### 5. Draft corpus characterization report [Eric writes prose, Teammate produces figures/tables]

**What this task accomplishes.** Produce the first graded artifact of the project — a ~3-5 page Quarto document that tells the grader "we understand our data." The 10 rubric points for Dimension 1 are decided by this document. Tasks 1-4 generated the substance (CSV, stats, taxonomy, eval subset); this task assembles them into a narrative, embeds the figures, and renders to PDF.

The split — Eric on prose, Rauf on figures — is deliberate: it protects the rubric by keeping English-prose authority on Eric (he is fluent and detail-oriented in writing), while giving Rauf substantial content ownership through the numerical and visual work. Both names go on the report.

**Data flow / how it works.**

```
Phase 1 Tasks 1-4 deliverables:
  - corpus_inventory.csv             (Eric Task 1)
  - corpus_stats.json + plot PNGs    (Rauf Task 2)
  - quality taxonomy definitions     (Eric Task 3)
  - eval_subset.csv + example imgs   (Eric Task 4)
  │
  │   reports/corpus_characterization.qmd
  │     (Eric writes prose, embeds Rauf's figures)
  ▼
reports/corpus_characterization.pdf   (graded artifact)
```

**Sub-tasks**:

- [ ] Eric: create `reports/corpus_characterization.qmd` skeleton with section headers
- [ ] Eric: write prose for sections — dataset provenance + citation, methodology narrative, quality taxonomy definitions, eval-subset methodology rationale, challenges linked to preprocessing (this last link moves the rubric from 7-8 to 9-10)
- [ ] Teammate: produce the statistics tables and plots embedded in the report (pulled from `notebooks/01_corpus_characterization.ipynb`)
- [ ] Teammate: produce the one example image per quality bucket figure
- [ ] Eric: integrate, render to PDF, confirm Telugu glyphs render without `[]` boxes

**Completion criterion:** PDF rendered, both team members reviewed, no obvious gaps. Telugu text renders correctly.

**Implementation.** `reports/corpus_characterization.qmd` (Quarto markdown — Eric authors). Rendered via `quarto render reports/corpus_characterization.qmd --to pdf`. Figures embedded by relative path from `reports/figures/corpus/`.

Telugu rendering needs `xelatex` as the PDF engine plus a Telugu-supporting font installed on the rendering host (Mallanna, Lohit Telugu, or Noto Sans Telugu). The default `pdflatex` engine produces `[]` boxes for non-Latin scripts. If we see boxes, change the `.qmd` front matter to:

```yaml
format:
  pdf:
    pdf-engine: xelatex
    mainfont: "Noto Sans Telugu"
```

And install the font: `sudo apt install fonts-noto-telugu`.

**How to verify when complete.**

- `reports/corpus_characterization.pdf` exists and is committed
- Telugu characters render as Telugu characters, not as `[]` or `?`
- All four Phase 1 statistics figures embedded with captions
- Quality taxonomy section has a definition + example image per bucket
- Eval-subset section explains the stratified sampling rationale in one paragraph
- Page count is roughly 3-5 (this is a Phase 1 report, not the final report)

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

**What this task accomplishes.** Move from "Phase 1 work is done" to "Phase 1 is formally closed and Phases 2/3 are underway." This is administrative hygiene but matters for grading — the roadmap is the document the grader scans first to see project organization. Stale checkboxes or missing handoff notes signal "they did not really finish Phase 1 cleanly." Closing a phase also forces a moment of reflection: what assumptions did we make under time pressure that we should disclose in the final report? Those go into `loose_ends.md` so they are not forgotten.

**Sub-tasks**:

- [ ] Confirm the corpus characterization PDF is rendered and committed
- [ ] Confirm `data/external/eval_subset/` is populated and committed
- [ ] Update `roadmap.md` status header to "Phase 2 + Phase 3 start (parallel)"
- [ ] Tick Phase 1 checkboxes in `roadmap.md`
- [ ] Note any loose ends in [`loose_ends.md`](loose_ends.md)

**Completion criterion:** Roadmap reflects current phase status; any deferred items are tracked in `loose_ends.md` per the [Documentation Standard](../standards/documentation_standard.md); both team members have reviewed the Phase 1 closeout commit.

**Implementation.** Pure doc editing. No code changes.

**How to verify when complete.**

```bash
git log --oneline -5                                         # closeout commit visible
grep -A 5 "Phase 1" docs/development/roadmap.md | head -10   # checkboxes all [x]
grep "## Phase 2" docs/development/roadmap.md                # status now reflects new phase
```

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
