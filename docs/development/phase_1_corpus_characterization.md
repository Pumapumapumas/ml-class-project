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

### 1. Download and inventory the corpus [Eric]

- [ ] Run `scripts/download_dataset.py` with whichever subset size we settle on (see open questions)
- [ ] Record total book count, total page count, total bytes
- [ ] Verify the paired-file invariant (every `.jpg` has a matching `.txt`); log mismatches
- [ ] Spot-check 5 random `.txt` files for encoding (UTF-8 NFC vs NFD) and basic plausibility

**Completion criterion:** A CSV at `data/external/corpus_inventory.csv` with one row per page: `book_id, page_id, image_path, text_path, image_bytes, text_bytes, image_width, image_height`.

### 2. Compute basic statistics [Teammate — recommended first PR]

- [ ] Image dimension distribution (histogram of width × height)
- [ ] DPI estimate (if available in EXIF or inferable from dimensions)
- [ ] Mean / median page text length (character count)
- [ ] File-size distribution (proxy for scan quality variance)

**Completion criterion:** A notebook `notebooks/01_corpus_characterization.ipynb` that loads the inventory CSV and produces the four distributions as plots, plus a `corpus_stats.json` artifact in `data/external/` with the headline numbers.

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

### 6. Mark phase complete and hand off [Eric]

- [ ] Update `roadmap.md` status header to "Phase 2 + Phase 3 start (parallel)"
- [ ] Tick Phase 1 checkboxes in `roadmap.md`
- [ ] Note any loose ends in [`loose_ends.md`](loose_ends.md)

---

## Open questions / decisions needed

1. **Subset size for development.** Full 13 GB or a stratified ~500 MB subset? Full corpus lets us produce the 500+ page processed sample for submission directly from our own runs; subset is faster to iterate. Recommendation: download a 5-book subset (~500 MB) for Phase 1-2, then pull more once the pipeline runs end-to-end.
2. **Quality taxonomy bucket count.** 3 buckets is faster but reads weak in the report; 5 buckets is more defensible but takes longer. Defaulting to 4 unless the team disagrees.
3. **Does Eric's teammate read Telugu?** If yes, they can validate the quality taxonomy boundaries more authoritatively. If no, taxonomy stays at the visual-artifact level (which is what the rubric actually asks for).
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
