# Iteration Narrative — Working Notes for the Final Report

**Purpose.** Per the instructor's Announcement 3 ("Please document the approach and iterations. The end result is not as important. You may not have a great solution. This is perfectly fine."), this document captures the real iterations, pivots, and compromises we made during the project. It is a working notes file. Selected sections will be transplanted (and tightened) into the final report's "Project Journey" section under Phase 5 Task 4.

The narrative is organized by theme, not by phase, because the most instructive pivots cut across phases.

---

## 1. Dataset acquisition — adapting to what we actually had

**Initial plan.** The project specification anticipated a course-provided corpus. The instructor's 27 May 2026 announcement promised the corpus "next week."

**What actually happened.** As of project start (early June), the promised corpus had not been distributed and multiple follow-up requests from other teams went unanswered. We treated the schedule risk as binding and adopted the publicly available `AlbertoChestnut/telugu-ocr` HuggingFace dataset, the same dataset multiple other class teams converged on (per `downloads/message_from_another_team.md`).

**What we changed.**

- Switched the entire project to `AlbertoChestnut/telugu-ocr` rather than wait
- Pinned the upstream commit (`f2bd895b...`) in `scripts/download_dataset.py` so every team member and any future re-runner gets the exact same files
- Built `scripts/download_dataset.py` to download a configurable subset rather than the full 13 GB corpus

**Iteration during dataset prep.** Our first download surfaced a real upstream quirk: at least one book directory began with a leading `.` (`.Kalidasa-Charitra_by_chilakamarthi_lakshminarasimham`), which behaves as a hidden file on Unix and breaks default-glob file walking. We did not anticipate this; we found it when our inventory script reported the wrong page count. Added a `normalize_book_dirs` post-download step that strips the leading dot and renames the directory in place. Documented in `loose_ends.md` so that if we later switch to the full corpus, we re-audit for other unusual names.

**Lesson.** "Pinned upstream + normalize at download time" turned out to be the right shape. The alternative — propagating the dot-prefix through every downstream tool — would have created bugs across the inventory, preprocessing, OCR, and report layers.

---

## 2. Five-book subset rather than full corpus

**Decision.** Work with a five-book subset (415 paired pages, ~190 MB) rather than the full ~221-book, ~13 GB corpus.

**Why.** Iteration speed. With 415 pages we could re-run the inventory, the preprocessing pipeline, and the OCR adapters end-to-end in minutes rather than hours. On a four-day delivery window, that compounded fast.

**Trade-off acknowledged honestly.** If a particular book in the full corpus contains visual conditions absent from our five books, our quality taxonomy will not cover them and our eval subset will not represent them. We mitigated by drawing the subset across image-file-size quintiles, which is the cheapest proxy for content variation, but the residual risk is real and disclosed in the report's Limitations section.

---

## 3. Quality taxonomy — letting the data shape the buckets

**Initial plan.** Define the quality taxonomy a priori based on what we expected to see (faded text, skew, etc.).

**What we did instead.** Held off on bucket definitions until we had browsed a stratified sample of 97 pages with our actual eyes. The browsing pass surfaced things we had not anticipated:

- White-band horizontal scanning artifacts (scanner-roller defects propagated from photocopier intermediates) — distinct from "faded" or "noisy" and unrecoverable by preprocessing
- "Damaged / Content Loss" emerged as a bucket of its own, sitting at the most-severe end of the priority order because no preprocessing recovers physically lost content
- Telugu publishing-specific features: ornamental section dividers (rows of stars/dots), numbered verses with English digits, decorative borders. These look like noise to a non-Telugu reader but are NOT quality defects — they're standard typography. Disambiguating these from genuine layout complexity was a real judgment call.

**DPI estimate had to be reframed.** Our original plan was a DPI distribution histogram. After running the inventory, we discovered every single image in our subset is exactly 1500 pixels wide (consistent scanner setting across the source). The "distribution" collapsed to a single value. Rather than fake a histogram with a single bar, we reframed the deliverable: a single DPI estimate (~250 DPI from the 6-inch typical-book-width assumption) and an explicit `image_width_uniform: true` flag in the corpus stats JSON. Honesty + a real finding.

**Lesson.** Letting the data shape the analysis methodology (not the other way around) caught a real corpus property that would otherwise have been hidden.

---

## 4. Preprocessing pipeline — what we shipped, and what the data later told us

**Initial plan.** Four-stage preprocessing pipeline: deskew + binarize + denoise + contrast enhancement.

**What we shipped.** Two stages: deskew + binarize. Denoise and contrast deferred under time pressure.

**The empirical surprise.** When we ran the full eval matrix on Wednesday night, the preprocessed cell scored WORSE than the raw cell for every model tested, including the classical Tesseract baseline:

| Model | Mean CER raw | Mean CER preprocessed | Delta |
|-------|--------------|------------------------|-------|
| Claude Opus 4.8 | 0.271 | 0.395 | +0.124 worse |
| Claude Sonnet 4.6 | 0.281 | 0.315 | +0.034 worse |
| Gemini 2.5 Flash | 0.564 | 0.725 | +0.161 worse |
| Tesseract 5 | 0.385 | 0.599 | +0.214 worse |

We had expected the vision LLMs to be hurt by binarization (they are trained on natural color/grayscale images) and the classical Tesseract baseline to benefit (classical OCR pipelines are usually fed binary images by design). **The data showed Tesseract was hurt MOST.** That was the moment our hypothesis broke.

**Root cause diagnosis.** A pixel-level inspection of one Clean-bucket page revealed what the binarization had done:

| Image | Unique pixel values | Mid-tones (30-225) |
|-------|---------------------|---------------------|
| Raw JPG | 256 | substantial gradient |
| Preprocessed PNG | 2 | **0.00%** |

Our adaptive thresholding (OpenCV `cv2.adaptiveThreshold` with `block_size=11, c=2`) collapsed every page to pure black/white with no gradient. Tesseract's tuned internal binarization (Otsu's method, plus Sauvola-style local adaptive thresholding) was deprived of the grayscale gradient it depends on for character-edge detection; the anti-aliased strokes that vowel marks like ర్, ా, ి rely on became 1-pixel jagged transitions and got filtered as noise. The vision LLMs were hurt for a related reason: their training distribution is natural images, not pure-binary documents.

**The lesson — sharper than the original hypothesis.** Modern OCR systems all carry well-tuned internal preprocessing. **Pre-binarizing competes with their algorithms rather than helping them.** A "right preprocessing for the right model" framing would have led us to invest in even MORE preprocessing for Tesseract; the actual finding is "trust the model's internal preprocessing, don't try to outsmart it."

This is the kind of empirical surprise the project's grading rubric explicitly rewards — and we discovered it because we ran a 4-model × 2-preprocessing matrix rather than just measuring the preprocessing's effect on a single model. Phase 5 Limitations frames the matrix design choice as a load-bearing methodological decision.

**A side benefit of how we built it.** `src/preprocessing/pipeline.py` was designed with per-stage enable/disable from the start. That meant running the raw-vs-preprocessed comparison was mechanical — invoke the pipeline twice with different stage sets. The cost of designing for ablation upfront was low; the value, given the surprise finding, was high.

**What this implies for the cut stages.** Denoise + contrast were deferred for time. The matrix data now suggests that adding them would likely have made things even WORSE for every model — preprocessing was the wrong direction, not just the wrong amount. The deferral turned out to be free; the report frames this as evidence, not as a gap.

---

## 5. OCR model selection — four pivots and a tiered head-to-head

**Initial spec.** Three models: Gemini 1.5 Flash, Surya OCR, Tesseract.

**Pivot 1 — Gemini 1.5 retired mid-project.** Our first live API call to `gemini-1.5-flash` returned a 404 NOT_FOUND. The model family had been retired by Google during our project window. Bumped to `gemini-2.5-flash` (the documented successor; same free-tier limits at the time, paid tier limits later). Test files needed updating in three places (`test_gemini.py`, `test_base.py`, README docstrings). The historical comment in `src/ocr/gemini.py:43` is preserved verbatim as a project-archaeology trace.

**Pivot 2 — Surya cut.** The Surya OCR library pulls 2–5 GB of model weights on first run and has pip-resolver compatibility issues. With four days to ship, the install-risk was unacceptable. Cut Surya entirely.

**Pivot 3 — Added Claude as the third model.** Wednesday evening we added Anthropic Claude Sonnet 4.6. The trigger was a strategic-value calculation: with only Gemini + Tesseract, the cross-model agreement signal would compare a strong vision LLM to a known-weak classical baseline, which conflates "agreement" with "page difficulty." Adding Claude gives a Gemini-vs-Claude pairwise signal that genuinely measures convergence between two strong models.

Cost reality check changed the model selection within Claude too. Initial plan was Opus (validated at ~$0.13/call, ~45 sec/page). Switching to Sonnet 4.6 dropped per-call cost to ~$0.018 and per-call latency to ~29 sec — chosen as the production-default for the 60-call eval and 415-call submission runs.

**Pivot 4 — Tesseract brought back; tiered Opus comparison added.** Late Wednesday night, with the eval matrix complete and time available, we revisited two earlier cuts:

- **Tesseract.** The Docker image (`ml-class-project/tesseract` with the Telugu language pack) had been built at project setup and verified, but the Python adapter was never written. We implemented `src/ocr/tesseract.py` against the existing `OCRAdapter` contract, ran it on the 60-page eval (raw + preprocessed), and added the classical baseline back into the comparison.
- **Opus on the full eval.** Originally Opus was meant for a 5-page comparison only (cost concerns). We started with that 5-page sample, observed Opus was ~5.6 percentage points better on mean CER than Sonnet on the same pages, and scaled to the full 30 + 30 matrix because the cost was actually trivial (~$7.80 total, well within budget).

The final eval matrix is **4 models × 2 preprocessing × 30 pages = 240 rows.**

**Tiered comparison findings (raw images, the better cell for every model).**

| Rank | Model | Mean CER | Median CER | Cost/page |
|------|-------|----------|------------|-----------|
| 1 | Claude Opus 4.8 | 0.271 | **0.185** | $0.13 |
| 2 | Claude Sonnet 4.6 | 0.281 | 0.255 | $0.018 |
| 3 | Tesseract 5 (Docker) | 0.385 | 0.340 | $0.00 (CPU) |
| 4 | Gemini 2.5 Flash | 0.564 | 0.444 | ~$0.0004 |

**Two further publishable findings from this matrix.**

1. **Opus is only ~1 percentage point better than Sonnet on mean CER, at 7× the cost.** For the eval subset, Sonnet 4.6 is the cost-quality sweet spot. Opus matters for the comparison story (it confirms "stronger models do help, but with diminishing returns"); it would not be the production choice.

2. **A 30-year-old open-source classical OCR baseline (Tesseract 5) beats Google's flagship vision LLM (Gemini Flash 2.5) on Telugu by 18 percentage points.** Vision LLMs are NOT automatically superior to classical methods for low-resource scripts. This is a useful corrective to the "LLMs everywhere" framing; the report frames it as a methodology-disclosure caveat.

**Cost transparency.** Total spend on the full pipeline:

| Service | Pages | Cost |
|---------|-------|------|
| Claude Sonnet 4.6 (60 eval) | 60 | ~$1.08 |
| Claude Opus 4.8 (60 eval) | 60 | ~$7.80 |
| Gemini 2.5 Flash (415 submission + 60 eval) | 475 | ~$0.30 |
| Tesseract 5 (60 eval) | 60 | $0 (Docker, CPU) |
| **Total** | **655** | **~$9.18** |

---

## 6. The rate-limit story — encountered in real time

This is the most pedagogically interesting iteration because it happened during the live OCR matrix run, while we were also writing this document.

**What we tried first.** Fire all four OCR cells in parallel as background processes: `{gemini, claude} × {raw, preprocessed}` = 4 cells × 30 pages.

**What happened.** Both Claude cells (`claude_raw`, `claude_preprocessed`) completed cleanly: 30/30 each, ~30 sec/page, no retries needed. Both Gemini cells hit the free-tier rate limit hard. `gemini_raw` finished with 18 of 30 pages successful; the other 12 exhausted the 5-attempt retry budget (max ~30 sec of backoff) before the rate-limit cool-down cleared. `gemini_preprocessed` finished with 0 of 30 successful.

**Diagnosis.** Two parallel Gemini cells effectively requested ~30 RPM against a 15 RPM free-tier quota. The error responses returned `retry_delay: 21–34 seconds` — longer than our 5-attempt budget could outlast. Each subsequent rate-limit hit also seemed to extend the cool-down, suggesting Google has a tier-2 backoff mechanism we triggered.

**Fix 1 — Build a serial retry script.** Wrote `/tmp/gemini_retry.sh` to fire the two Gemini cells sequentially (not in parallel), with a 60 sec inter-cell cool-down. This script was idempotent: the OCR CLI skips pages whose output already exists, so the script only re-processed missing pages. Outcome: barely moved the needle. With the same 5-attempt budget and a now-growing cool-down period, only 1 additional page was scored.

**Fix 2 — Bump the retry budget.** Modified `src/ocr/gemini.py` to bump `MAX_ATTEMPTS` from 5 to 7. Backoff is `2**attempt + jitter`, so the new schedule gives ~126 sec of total backoff per page (up from ~30 sec). Queued a second retry script (`/tmp/gemini_retry_v2.sh`) that waits 45 minutes (so the cool-down clears), then runs up to 3 sequential passes filling any remaining gaps.

**Fix 3 — Enable Gemini paid tier.** The serial retry script + bumped budget was making slow forward progress, but the cool-down was escalating with each rate-limit hit (`retry_delay: 21s` early in the night → `51s` later). The team enabled Google Cloud billing on the project that owned the Gemini API key (the project's $300 Cloud free-trial credit covered the work). One subtlety: the AI Studio project where the key lived needed billing linked separately — the resolution path was to add a credit card directly to AI Studio rather than rely on the Cloud-trial credit alone. Once paid tier was live (verified with 5 rapid sequential calls, all 200 OK), the 15 RPM cap was replaced with a 1,000 RPM cap. The 39 missing matrix pages filled in ~7 minutes wall-clock. The full 415-page submission run finished overnight without a single rate-limit error.

**Outcome.** All 8 eval cells complete (30/30 each, 240 rows); the 415-page submission sample is also complete (413/415 from the overnight run, plus 2 retried in a 10-second idempotent re-run after Google's intermittent 500 errors). Total Gemini spend for the night: under $0.30.

**Lesson — and an honest disclosure for the report.** Real ML pipelines hit real rate limits. The lesson is not "don't use free tiers" — it is "plan for the rate limit explicitly with serial execution, generous backoff budgets, and idempotent retry scripts; have a paid-tier escape hatch ready." The fact that this iteration shows up in `git log` and in the iteration narrative rather than being silently retried in the background is part of the documentation discipline.

---

## 7. Tooling, standards, and engineer-dispatch discipline

We made extensive use of an autonomous engineer-dispatch workflow throughout the project. The engineer is a Claude Code instance running headlessly in an isolated git worktree, given a task spec, and producing a Pull Request for human review. This is itself a non-trivial iteration that bears on the "mindset of an ML engineer" goal.

**What worked.**

- Phase 2 preprocessing pipeline: clean engineer dispatch, caught two real bugs during the review stage (BGR `borderValue` blue-corner bug; CLI silent-overwrite collision)
- Phase 3 OCR pipeline (interface + Gemini + batch runner): caught a manifest-field consistency bug that would have broken Phase 4 grouping
- Phase 3 Claude adapter: engineer rejected a factually-inverted code-reviewer finding after independent verification — good discipline
- Logging system retrofit: surfaced standards-vs-code drift we had not seen ourselves (the documented `src/utils/logging_config.py` had never been built)

**What did not work.**

- One engineer dispatch's task spec was over-tight on "out of scope" boundaries. The engineer surfaced a real adjacent-code duplication (`discover_books` between OCR and preprocessing CLIs) and deferred fixing it because we explicitly told it not to touch the adjacent file. Lesson: task spec language should give engineers explicit room for small adjacent refactors that prevent duplication.
- The logging engineer's `setup_logging` cleared every root handler, including pytest's caplog handler, which silently broke an existing integration test. The test failure landed on `main`. We fixed it forward by tagging our own handlers with a sentinel attribute and only removing those. Lesson: when retrofitting infrastructure, run the full test suite (not just the new tests) before merging.

**What the dispatch model is for.** Substantive code work where a fresh-context engineer with structured review (code-reviewer + refactoring-evaluator + standards-auditor + quality-control) catches bugs we would miss. Not for small judgment-call tasks where dispatch overhead exceeds the work itself.

---

## 8. The corpus-stats notebook — a real teammate-collaboration iteration

Rauf, the second team member, owns `notebooks/01_corpus_characterization.ipynb`. The story of this notebook is itself an iteration worth documenting.

**What he produced.** A solid notebook covering all four required distributions (image dimensions, DPI estimate, page text length, file-size distribution) plus the JSON statistics artifact. The numerical work was right and his honest DPI-uniformity finding was exactly the analytical voice the rubric rewards.

**What needed iteration.**

1. He reorganized the notebook in place several times and ended up with duplicate cells (two `df.describe()` blocks, two file-size plots, two interpretation paragraphs). We cleaned these up in a follow-up commit on `main`.
2. The plots rendered inline but had no `plt.savefig()` calls, so no figures landed in `reports/figures/corpus/` for the final report. We added the savefig calls in the same follow-up.
3. Cell ordering was non-linear (the JSON-write cell fired before the plotting cells). Restart-and-run-all would have caught this.

**Lesson for the team.** Pre-push hygiene — restart kernel, run all, save with `plt.savefig` for any figure that goes in a report — matters more on a team than solo. Surface area for "works on my machine" mistakes is larger when the next person is consuming your output for a different purpose.

---

## 9. Submission format — discovered Wednesday evening

The instructor's Announcement 4 (received Wednesday evening, with the project deadline at Thursday 8 PM EST, not midnight as we had previously assumed) revealed that the submission is a **shared directory** (Google Drive or similar), not a GitHub link.

We had structured the project around the GitHub repo as the primary artifact. The pivot was minor (package the directory, share via Drive, include a README pointing at GitHub for full history), but the discovery itself was significant: **carefully read the latest instructor announcement, not just the original spec.**

Announcement 5 (also Wednesday evening) confirmed the presentation is recorded (not live) and team participation is flexible (one team member can record the entire presentation). This removed a coordination risk and let us de-prioritize live-demo rehearsal in favor of report polish.

---

## What the next iteration would be, if we had more time

For a Phase 6 we would not be able to do in this timeline but should disclose:

- **Per-stage preprocessing ablation.** We have raw-vs-(deskew+binarize). The actual data showed even this two-stage pipeline hurt every model. A clean ablation would compare deskew-only vs binarize-only to isolate which of the two is doing the damage, and try gentler binarization (Otsu or a less aggressive adaptive threshold) to test whether the lesson is "no binarization" or "softer binarization." The `Pipeline` class supports per-stage enable/disable via `enable={...}`; the experiment is mechanical to run.
- **Prompt-variant study for the vision LLMs.** All three vision LLMs (Gemini Flash, Claude Sonnet, Claude Opus) used the same system prompt verbatim from the project spec. A real comparison would A/B at least 2–3 prompt variants per model, particularly testing whether explicit "preserve diacritics" / "do not translate" / "preserve layout" hints meaningfully change CER.
- **Surya OCR or another transformer-based document model.** The matrix has three vision LLMs (different sizes) and one classical baseline. A purpose-trained document-OCR transformer (Surya, TrOCR, or one of the InternVL OCR variants) would complete the methodology landscape.
- **Larger eval subset.** Six pages per quality bucket gives us power to identify large effects (the +18 pp Tesseract-vs-Gemini gap) but not subtle ones (the +1 pp Opus-vs-Sonnet gap). A 50-page-per-bucket subset would let us run paired statistical tests (Wilcoxon signed-rank on the per-page CER differences) with confidence intervals tight enough to publish. Phase 5 reports per-bucket sample sizes alongside CER deltas and acknowledges this honestly.
- **Apply LLM-fluency scoring to the full submission sample.** We have CER ground truth on 30 pages; we have OCR text from Gemini on all 415 pages. Calibrating the fluency-score / CER correlation on the eval subset and then applying fluency scoring at scale on the 415-page submission is the natural "no-ground-truth quality estimation" story. The fluency-scoring adapter exists; we have not run it across all 415 pages because of time.
