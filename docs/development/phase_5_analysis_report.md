# Phase 5 — Analysis, Final Report, and Presentation

**Status:** Queued. Starts when Phase 4 has eval-subset and scaled-validation outputs.
**Time estimate:** 3 days. The report is the largest single artifact in the project.
**Rubric dimensions:** Dimension 5 — Analysis and Insights (15 pts), Dimension 6 — Code Quality and Reproducibility (10 pts), Dimension 7 — Report and Presentation (5 pts). Combined 30 pts.

---

## Goal

Synthesize Phases 1-4 into a polished, professional 15+ page Quarto final report; build the 15-minute presentation; finalize the 500+ page processed corpus sample for submission; and ensure the GitHub repo is in a state a senior engineer would sign off on. This is where partial credit becomes full credit.

---

## Dependencies

- Phase 1 corpus characterization report (already drafted).
- Phase 3 OCR comparison matrix (CER/WER outputs for 6 cells).
- Phase 4 calibration analysis and 100+ page scaled validation.
- 500+ page processed corpus sample on disk.

---

## Tasks

### 1. Error categorization analysis [Eric + Teammate split work]

- [ ] Sample ~50 errors across the eval-subset OCR outputs
- [ ] Classify by type: character substitution, word-boundary error, diacritic (mātrā) error, conjunct miss, hallucination, wholesale omission
- [ ] Notebook `notebooks/05_error_analysis.ipynb` producing a frequency table + per-model breakdown
- [ ] Identify the 1-2 error types Gemini handles best vs Tesseract — this is the comparison story

**Completion criterion:** Error-category table per model written; one paragraph of analysis per category in the report.

### 2. Preprocessing-impact quantification [Eric]

- [ ] Read the Phase 3 CER/WER CSV; for each model, compute mean CER with-preprocessing vs without
- [ ] Statistical context: paired t-test or Wilcoxon signed-rank across the 30 pages
- [ ] Bar chart per model showing the delta
- [ ] Per-stage ablation if time: deskew-only vs binarize-only vs full pipeline (requires re-running Phase 3 with stage flags — only do this if calendar allows)

**Completion criterion:** Quantified preprocessing improvement per model; significance test reported; visualization saved.

### 3. Scalability and cost estimate [Eric]

- [ ] From the OCR manifests, compute mean latency per page per model
- [ ] Estimate wall-clock and API cost to process the full ~13 GB corpus (~estimated total pages × per-page latency × parallelism factor)
- [ ] Estimate Gemini API cost if we were to pay (free tier has hard limits — show what paid would look like)
- [ ] One-paragraph discussion of bottlenecks (rate limits, throughput, GPU)

**Completion criterion:** A table with rows = models, columns = (latency, throughput at free tier, full-corpus wall-clock, full-corpus paid cost).

### 4. Draft the final Quarto report [Eric primary, Teammate sections]

- [ ] `reports/final_report.qmd` skeleton with sections: Abstract, Introduction, Corpus (pulled from Phase 1 report), Preprocessing Methods, OCR Methods + Prompt Engineering, Validation Framework, Results (model comparison, preprocessing impact, validation calibration), Error Analysis, Discussion + Limitations + Future Work, Methodology Disclosure (AI tooling per academic-integrity policy), References
- [ ] Target 15+ pages excluding code and figures
- [ ] Embed Phase 1-4 figures from `reports/figures/`
- [ ] Render to HTML and PDF; verify Telugu glyphs render correctly in both

**Completion criterion:** Report renders cleanly; page count meets minimum; Telugu rendering verified.

### 5. Methodology disclosure section [Eric]

- [ ] Per the spec's academic integrity policy and [`../../README.md`](../../README.md), document AI tooling used and for what
- [ ] List Claude Code, any GitHub Copilot use, prompt engineering iterations
- [ ] Be specific: "Used Claude Code for initial scaffolding of the OCR adapter interface; all design decisions and final code reviewed and committed by human team members"

**Completion criterion:** Methodology section drafted; reviewed by teammate.

### 6. Limitations + honest analysis section [Eric]

- [ ] Ground-truth quality caveats (community-contributed corpus)
- [ ] Sample-size caveats (30 eval pages is small for strong statistical claims)
- [ ] Model-choice caveats (no GPT-4o or Claude comparison)
- [ ] Validation-method caveats (LLM judging LLM is non-independent)
- [ ] One paragraph per caveat — honest, not defensive

**Completion criterion:** Limitations section drafted. The honesty is what moves Dimension 5 from 11-13 to 14-15.

### 7. Build the 15-minute presentation [50/50 split — both present roughly equally]

The presentation must visibly reflect equal contribution regardless of where the actual coding load fell. Split is 50/50 by time. Mitigations below de-risk the language-fluency challenge without compromising equality of role.

- [ ] Eric: slide structure (Quarto Reveal.js): Problem → Corpus → Pipeline → Results → Demo → Limitations → Q&A
- [ ] Both: assign sections roughly 50/50 by speaking time. Recommended split — Eric: Problem, Pipeline, Limitations. Teammate: Corpus, Results, Demo. (Section assignment swappable; what matters is equal time.)
- [ ] Each presenter writes their own section's slide notes in **scripted form** — full sentences they will read or have nearly memorized. Reduces ad-lib pressure for both, especially the teammate, and makes timing predictable.
- [ ] Both: rehearse together at least twice end-to-end. Time each section, adjust if anyone runs long.
- [ ] Q&A strategy: the presenter who delivered a section fields questions on that section first. If they get stuck or the question is broader, the other team member chimes in. Practice this hand-off explicitly during rehearsal.
- [ ] Live demo (~3 min, during the teammate's Demo slot): run `python -m src.ocr.cli` on one known-clean sample page. Pre-recorded screen capture as fallback if API is down on the day.

**Completion criterion:** Slides built; both team members own roughly half of speaking time; demo runs end-to-end without manual intervention; rehearsal hits 13-15 min with both presenting confidently. The grader should not be able to tell from the presentation alone who carried more of the coding load.

### 8. Package the 500+ page processed corpus sample [Eric]

- [ ] Confirm `data/processed/submission_sample/` has 500+ pages
- [ ] Add a manifest (`README.md` in that directory or alongside) listing source book IDs and counts
- [ ] Decide submission format: zipped directory in the GitHub repo's release, or a separate cloud-storage link in the README. Class submission instructions should clarify. Default: zipped attached to a GitHub release tag.

**Completion criterion:** 500+ pages packaged; manifest documents provenance.

### 9. Repo hygiene pass [Eric]

- [ ] `ruff check src/ tests/` — clean
- [ ] `pytest -m "not slow and not api"` — clean
- [ ] Confirm `.env` is gitignored and `.env.example` is committed (per [`../standards/credential_handling_standard.md`](../standards/credential_handling_standard.md))
- [ ] Confirm `data/` is gitignored
- [ ] README quickstart works from a fresh clone (have the teammate verify on a clean checkout)
- [ ] All planning checkboxes in `roadmap.md` and `phase_*.md` reflect reality
- [ ] [`loose_ends.md`](loose_ends.md) reviewed; in-scope items either fixed or explicitly deferred with reasoning

**Completion criterion:** Fresh-clone reproduction works through `scripts/download_dataset.py --subset 1` + a single OCR call.

### 10. Final submission package [Eric]

- [ ] Submit per course instructions: GitHub repo URL, rendered report (HTML + PDF), presentation slides, link to processed corpus sample
- [ ] Tag the repo at submission: `git tag v1.0-submission`
- [ ] Confirm the teammate has reviewed the final report

**Completion criterion:** Submitted on time. Submission email/portal entry confirms receipt.

---

## Open questions / decisions needed

1. **Reveal.js vs PowerPoint vs Keynote for the deck?** Reveal.js (via Quarto) keeps everything in the repo and reproducible — recommend that. Risk: rendering Telugu in Reveal.js needs explicit font config.
2. **Does the live demo use the submission sample or a fresh page?** Recommend a known-clean page so the demo doesn't fail dramatically on stage. Have a fallback page if internet/API fails.
3. **15-minute presentation: who presents which sections?** Eric leads given the language asymmetry, but the teammate should own at least one technical section to demonstrate ownership.
4. **Do we cite related work?** The spec doesn't require it, but it adds polish. Recommend 5-10 references (AI4Bharat papers, Telugu OCR history, LLM-as-a-judge literature).

---

## Outputs / deliverables

- `reports/final_report.qmd` + rendered `final_report.html` + `final_report.pdf` — primary graded artifact.
- `reports/presentation.qmd` + rendered slides.
- `data/processed/submission_sample/` — 500+ page sample, packaged.
- Tagged GitHub commit: `v1.0-submission`.
- `notebooks/05_error_analysis.ipynb` — error categorization narrative.
- All `reports/figures/` populated.

---

## Risks

- **Report writing always takes longer than expected.** Mitigation: start the skeleton on day 1 of Phase 5 (or earlier — drafting introduction + methods while Phase 4 runs is sensible). Treat report as concurrent work, not sequential.
- **Telugu rendering in PDF / slides fails on submission day.** Mitigation: verify rendering on day 1 of Phase 5, not day 3. Have HTML as fallback if PDF font config fights us.
- **Live demo fails during presentation.** Mitigation: pre-record a screen capture as fallback; have local Surya OCR ready if Gemini API is unreachable; never demo something untested.
- **The teammate's English proficiency limits report contribution.** Mitigation: assign teammate to slide deck visuals and error-analysis notebook (more visual, less prose-dense). Eric owns the report prose.
- **Loose ends accumulate and we don't notice.** Mitigation: review [`loose_ends.md`](loose_ends.md) explicitly as task 9 above, not as an afterthought.
