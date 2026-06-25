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

## 4. Preprocessing pipeline — scope compression

**Initial plan.** Four-stage preprocessing pipeline: deskew + binarize + denoise + contrast enhancement.

**What we shipped.** Two stages: deskew + binarize. Denoise and contrast are documented as stretch goals in the phase doc, marked as deferred to a follow-up.

**Why.** Time triage. The four-day delivery window forced explicit choices. Deskew and binarize are the two stages that map most directly to our quality taxonomy (Skewed bucket → deskew, Faded bucket → binarize). Denoise and contrast would have shown smaller per-bucket effects given the corpus we have, and would have eaten engineering hours we needed for OCR comparison and the final report.

**Architectural choice that paid off.** We built `src/preprocessing/pipeline.py` to support per-stage enable/disable from the start, even with only two stages. The trivially-larger investment upfront means the Phase 5 ablation comparing raw-vs-preprocessed OCR is mechanical — we ran the pipeline twice (once with both stages, once with the raw images directly) and the comparison is clean.

---

## 5. OCR model selection — three pivots in 48 hours

**Initial spec.** Three models: Gemini 1.5 Flash, Surya OCR, Tesseract.

**Pivot 1 — Gemini 1.5 retired mid-project.** Our first live API call to `gemini-1.5-flash` returned a 404 NOT_FOUND. The model family had been retired by Google during our project window. Bumped to `gemini-2.5-flash` (the documented successor; same free-tier limits). Test files needed updating in three places (`test_gemini.py`, `test_base.py`, README docstrings). The historical comment in `src/ocr/gemini.py:43` is preserved verbatim as a project-archaeology trace.

**Pivot 2 — Surya cut.** The Surya OCR library pulls 2–5 GB of model weights on first run and has pip-resolver compatibility issues. With four days to ship, the install-risk was unacceptable. Cut Surya entirely. The rubric requires "at least two models compared"; Gemini + Tesseract satisfies that with margin.

**Pivot 3 — Added Claude as the third model.** Late in the project (Wednesday evening) we added Anthropic Claude Sonnet 4.6 as the third comparison model. The trigger was a strategic-value calculation: with only Gemini + Tesseract, our Phase 4 cross-model agreement metric (Method B) would be comparing a strong vision LLM to a known-weak classical baseline, which conflates "agreement" with "page difficulty." Adding Claude gives us a Gemini-vs-Claude agreement signal that is genuinely meaningful (two strong models converging or diverging on a page actually says something about the page).

Cost reality check changed the model selection within Claude too. Initial plan was Opus 4.7 (we ran one live test that returned 1010 chars in ~45 sec at ~$0.13/call). Switching to Sonnet 4.6 dropped per-call cost to ~$0.018 and per-call latency to ~29 sec while preserving output quality — chosen for the 530-call eval-plus-submission budget.

**Cost transparency.** Total budgeted Claude spend: ~$10 (60-call eval matrix at Sonnet $1.07 + 500-call submission sample at Sonnet $8.90).

---

## 6. The rate-limit story — encountered in real time

This is the most pedagogically interesting iteration because it happened during the live OCR matrix run, while we were also writing this document.

**What we tried first.** Fire all four OCR cells in parallel as background processes: `{gemini, claude} × {raw, preprocessed}` = 4 cells × 30 pages.

**What happened.** Both Claude cells (`claude_raw`, `claude_preprocessed`) completed cleanly: 30/30 each, ~30 sec/page, no retries needed. Both Gemini cells hit the free-tier rate limit hard. `gemini_raw` finished with 18 of 30 pages successful; the other 12 exhausted the 5-attempt retry budget (max ~30 sec of backoff) before the rate-limit cool-down cleared. `gemini_preprocessed` finished with 0 of 30 successful.

**Diagnosis.** Two parallel Gemini cells effectively requested ~30 RPM against a 15 RPM free-tier quota. The error responses returned `retry_delay: 21–34 seconds` — longer than our 5-attempt budget could outlast. Each subsequent rate-limit hit also seemed to extend the cool-down, suggesting Google has a tier-2 backoff mechanism we triggered.

**Fix 1 — Build a serial retry script.** Wrote `/tmp/gemini_retry.sh` to fire the two Gemini cells sequentially (not in parallel), with a 60 sec inter-cell cool-down. This script was idempotent: the OCR CLI skips pages whose output already exists, so the script only re-processed missing pages. Outcome: barely moved the needle. With the same 5-attempt budget and a now-growing cool-down period, only 1 additional page was scored.

**Fix 2 — Bump the retry budget.** Modified `src/ocr/gemini.py` to bump `MAX_ATTEMPTS` from 5 to 7. Backoff is `2**attempt + jitter`, so the new schedule gives ~126 sec of total backoff per page (up from ~30 sec). Queued a second retry script (`/tmp/gemini_retry_v2.sh`) that waits 45 minutes (so the cool-down clears), then runs up to 3 sequential passes filling any remaining gaps.

**Outcome (as of this writing, in progress).** Eight of Eight Claude cells complete; Gemini partial coverage being filled in by the v2 retry; if the v2 retry also leaves gaps, the report will document partial-matrix Gemini coverage as a real constraint of the free tier.

**Lesson — and an honest disclosure for the report.** Real ML pipelines hit real rate limits. The lesson is not "don't use free tiers" — it is "plan for rate limits explicitly with serial execution, generous backoff budgets, and idempotent retry scripts." The fact that this iteration shows up in `git log` and in `loose_ends.md` rather than being silently retried in the background is part of the documentation discipline.

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

- **Surya adapter and a three-strong-model agreement metric.** Today the Method B cross-model agreement compares two strong models (Gemini, Claude); a third would make the agreement signal meaningfully tighter.
- **Per-stage preprocessing ablation.** We have raw-vs-preprocessed; a true ablation would compare deskew-only, binarize-only, and both. The Pipeline class supports it via `enable={...}`; we did not run it.
- **Systematic hyperparameter tuning.** We used spec-recommended defaults (`block_size=11`, `c=2` for binarize, `angle_threshold=0.5` for deskew). A real production deployment would explore per-bucket sensitivity.
- **Prompt-variant study for both vision LLMs.** Both Gemini and Claude use the same system prompt verbatim (from the project spec). A real comparison would A/B at least 2–3 prompt variants per model.
- **Larger eval subset.** Six pages per quality bucket gives us power to identify large effects, not subtle ones. Phase 5 reports per-bucket sample sizes and discusses this honestly.
