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

**What this task accomplishes.** Convert per-page CER numbers into a comparison story. CER says "Gemini scored 4%, Tesseract scored 22%." That is good, but Dimension 5 (Analysis, 15 pts) rewards the next level: "Gemini's errors are mostly subtle diacritic mistakes, while Tesseract's are wholesale conjunct misses and hallucinated English." Without that, the report has numbers but no narrative.

**Data flow / how it works.**

```
data/processed/eval_subset/<model>_<preprocessing>/<book>/<page>.txt
  + ground truth
  │
  │   Eric + Rauf together: sample ~50 errors, tag each by category
  ▼
data/processed/eval_subset/tagged_errors.csv
  columns: book_id, page_id, model, error_text, truth_text, category
  │
  │   notebooks/05_error_analysis.ipynb
  ▼
data/processed/eval_subset/error_categories.csv
  +
reports/figures/error_analysis/*.png
```

**Sub-tasks**:

- [ ] Sample ~50 errors across the eval-subset OCR outputs
- [ ] Classify by type: character substitution, word-boundary error, diacritic (mātrā) error, conjunct miss, hallucination, wholesale omission
- [ ] Notebook `notebooks/05_error_analysis.ipynb` producing a frequency table + per-model breakdown
- [ ] Identify the 1-2 error types Gemini handles best vs Tesseract — this is the comparison story

**Completion criterion:** Error-category table per model written; one paragraph of analysis per category in the report.

**Implementation.** Hand-tagging happens in a shared spreadsheet or CSV (Eric + Rauf collaborating real-time). The notebook is pandas + matplotlib over the tagged CSV.

**How to verify when complete.**

- `data/processed/eval_subset/tagged_errors.csv` has ~50 rows
- `data/processed/eval_subset/error_categories.csv` has the frequency table per model
- Two PNGs in `reports/figures/error_analysis/`: raw counts and normalized percent

#### Walk-through for Rauf

**Why this task matters.** Phase 4 gives us CER and WER numbers — "Gemini scored X, Tesseract scored Y." But the rubric for Dimension 5 (Analysis, 15 pts) wants more than numbers: it wants WHY one model does better, and on what kinds of errors. That is what error categorization gives. Your charts plus Eric's analysis paragraphs are what move the rubric from 11-13 to 14-15 on that dimension.

**What you will produce.**
- A frequency-table CSV at `data/processed/eval_subset/error_categories.csv` with columns `model, category, count` (and maybe a percentage column).
- One or more bar-chart PNGs under `reports/figures/error_analysis/` comparing error frequencies across models.
- The Jupyter notebook at `notebooks/05_error_analysis.ipynb` that produced both.

**When you can start.** After Eric and you have collected the ~50 error samples. Eric will sit with you for ~30 minutes to walk through what each category MEANS in Telugu (diacritic vs conjunct vs substitution) and tag the first 10-15 together. After that, you do the bulk classification on a spreadsheet, then bring the data into pandas for the charts.

**Background — the categories in plain English.**

| Category | What it looks like |
|----------|---------------------|
| Character substitution | One Telugu character replaced by a different but visually similar one. Most common error. |
| Word-boundary error | OCR joins two words or splits one word — spaces wrong. |
| Diacritic (mātrā) error | A vowel mark (the squiggle above/below/beside the base consonant) is wrong, dropped, or added. Telugu-specific. |
| Conjunct miss | Telugu can combine two consonants into a single glyph; OCR sometimes outputs them as two separate characters or as a wrong glyph. |
| Hallucination | OCR invents text that is not in the source — sometimes drops into English, sometimes makes up Telugu words. |
| Wholesale omission | OCR misses an entire word or line. |

Eric will help you tell these apart on a few examples. Once you have the data tagged, the rest is pandas + matplotlib.

**Starter skeleton.**

```python
# notebooks/05_error_analysis.ipynb
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

REPO_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()

# Read the hand-tagged error CSV (Eric and you produce this together).
# Expected columns: book_id, page_id, model, error_text, truth_text, category
errors = pd.read_csv(REPO_ROOT / "data" / "processed" / "eval_subset" / "tagged_errors.csv")

# Frequency table per model
freq = (errors.groupby(["model", "category"])
              .size()
              .reset_index(name="count"))
freq["pct"] = freq.groupby("model")["count"].transform(lambda s: s / s.sum() * 100)
freq.to_csv(REPO_ROOT / "data" / "processed" / "eval_subset" / "error_categories.csv", index=False)
print(freq.pivot(index="category", columns="model", values="count").fillna(0))
```

**Charts.** A side-by-side bar chart per category, one bar per model, is the cleanest comparison:

```python
FIG_DIR = REPO_ROOT / "reports" / "figures" / "error_analysis"
FIG_DIR.mkdir(parents=True, exist_ok=True)

pivot = freq.pivot(index="category", columns="model", values="count").fillna(0)
fig, ax = plt.subplots(figsize=(9, 5))
pivot.plot(kind="bar", ax=ax)
ax.set_xlabel("Error category")
ax.set_ylabel("Error count (sample of ~50)")
ax.set_title("OCR error distribution by category and model")
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
fig.savefig(FIG_DIR / "error_categories_by_model.png", dpi=150, bbox_inches="tight")
plt.show()
```

A second chart can show **percent within each model's errors** (normalizes for the fact that Tesseract simply has more errors than Gemini):

```python
fig, ax = plt.subplots(figsize=(9, 5))
freq.pivot(index="category", columns="model", values="pct").fillna(0).plot(kind="bar", ax=ax)
ax.set_ylabel("Percent of model's errors")
ax.set_title("Error mix by model (normalized)")
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
fig.savefig(FIG_DIR / "error_mix_by_model.png", dpi=150, bbox_inches="tight")
plt.show()
```

**What good looks like.**
- The frequency-table CSV is committed and matches the chart.
- Two PNGs saved (counts + normalized percent).
- A short markdown cell at the end of the notebook lists the 1-2 categories where each model performs best and worst — Eric will turn this into prose paragraphs for the report.

**Common pitfalls.**
- **Tagging is the slow part, not the plotting.** Plan ~2 hours with Eric to tag ~50 errors. Do not try to plot before the tags are in.
- **Categories overlap.** A word-boundary error CAN involve a missing diacritic too. When it does, pick the most salient one and pick consistently. Document the rule.
- **Sample of 50 is small.** Do not over-claim from the data — phrase observations as tendencies, not laws. Eric will calibrate the wording for the report.

**Open a draft PR early.** Once the frequency table CSV exists and one chart renders, draft-PR it. The data-collection step is the hard part; once that is right, the charts are mechanical.

### 2. Preprocessing-impact quantification [Eric]

**What this task accomplishes.** Demonstrate that the preprocessing pipeline is not just architecturally sound but empirically useful. The rubric for Dimension 2 (Preprocessing, 15 pts) and Dimension 5 (Analysis) both reward this directly — "we added deskew + binarize and CER dropped by X% on Skewed pages and Y% on Faded pages, with p < 0.05 by paired Wilcoxon."

**Data flow / how it works.**

```
data/processed/eval_subset/cer_wer.csv  (Phase 4 Task 2)
  │
  │   pandas: group by (model, preprocessing), per-bucket and overall
  │   scipy.stats: paired Wilcoxon test on the 30-page deltas
  ▼
A table (overall + per-bucket) + bar charts + p-values
```

**Sub-tasks**:

- [ ] Read the Phase 3 CER/WER CSV; for each model, compute mean CER with-preprocessing vs without
- [ ] Statistical context: paired t-test or Wilcoxon signed-rank across the 30 pages
- [ ] Bar chart per model showing the delta
- [ ] Per-stage ablation if time: deskew-only vs binarize-only vs full pipeline (requires re-running Phase 3 with stage flags — only do this if calendar allows)

**Completion criterion:** Quantified preprocessing improvement per model; significance test reported; visualization saved.

**Implementation.** Notebook `notebooks/06_preprocessing_impact.ipynb` (or fold into the calibration notebook if that is cleaner). Outputs go to `reports/figures/preprocessing/` for embedding.

**How to verify when complete.**

- A pivoted table (rows = model, cols = bucket × preprocessing, cells = mean CER) printed in the notebook
- One bar chart per model showing the raw vs preprocessed CER delta
- p-values from the Wilcoxon test reported in the notebook and captured in `reports/notes/preprocessing_impact.md` for the final report to embed

### 3. Scalability and cost estimate [Eric]

**What this task accomplishes.** Show that the team thought about real-world deployment, not just a 30-page demo. Dimension 5 rewards realistic projections — what would it cost to OCR the full 13 GB corpus? What is the bottleneck? Is the free tier sufficient or would we need paid quota? This is a small section in the report but a high-credibility one because it requires honest engineering judgment.

**Sub-tasks**:

- [ ] From the OCR manifests, compute mean latency per page per model
- [ ] Estimate wall-clock and API cost to process the full ~13 GB corpus (~estimated total pages × per-page latency × parallelism factor)
- [ ] Estimate Gemini API cost if we were to pay (free tier has hard limits — show what paid would look like)
- [ ] One-paragraph discussion of bottlenecks (rate limits, throughput, GPU)

**Completion criterion:** A table with rows = models, columns = (latency, throughput at free tier, full-corpus wall-clock, full-corpus paid cost).

**Implementation.** Small notebook cell or a paragraph in the final report. Reads the Phase 3 manifests for per-page latency, multiplies by the estimated ~50000 pages in the full corpus, prints the table.

**How to verify when complete.** Table exists in the report's Scalability section. Numbers are defensible (use median latency × page count for wall-clock; use Gemini Pro pricing for "paid" estimate).

### 4. Draft the final Quarto report [Eric primary, Teammate sections]

**What this task accomplishes.** Produce the primary graded artifact. The final report is what the grader spends the most time with and where Dimension 7 (Report) and most of Dimension 5 (Analysis) get scored. It pulls the substance of Phases 1-4 into a single 15+ page document — Phase 1's corpus characterization, Phase 2's preprocessing rationale, Phase 3's OCR methods and comparison, Phase 4's validation framework, Phase 5's analysis. The Phase 1 report (`reports/corpus_characterization.qmd`) provides several already-drafted sections that flow into the final report.

**Data flow / how it works.**

```
Phase 1: corpus_characterization.qmd     (corpus + taxonomy + eval subset)
  + Phase 3 manifests + outputs           (model comparison numbers)
  + Phase 4 cer_wer.csv + calibration     (CER deltas + LLM signals)
  + Phase 5 error_categories.csv          (error narrative)
  + figures: reports/figures/{corpus,preprocessing,validation,error_analysis}/
  │
  │   reports/final_report.qmd
  │     Eric: prose; Rauf: any remaining figure tweaks
  ▼
final_report.pdf  (graded)
final_report.html (backup if PDF font fights us)
```

**Sub-tasks**:

- [ ] `reports/final_report.qmd` skeleton with sections: Abstract, Introduction, Corpus (pulled from Phase 1 report), Preprocessing Methods, OCR Methods + Prompt Engineering, Validation Framework, Results (model comparison, preprocessing impact, validation calibration), Error Analysis, Discussion + Limitations + Future Work, Methodology Disclosure (AI tooling per academic-integrity policy), References
- [ ] Target 15+ pages excluding code and figures
- [ ] Embed Phase 1-4 figures from `reports/figures/`
- [ ] Render to HTML and PDF; verify Telugu glyphs render correctly in both

**Completion criterion:** Report renders cleanly; page count meets minimum; Telugu rendering verified.

**Implementation.** `reports/final_report.qmd` is a NEW Quarto doc (separate from the Phase 1 doc to keep that one as a checkpoint artifact). Many sections (Corpus, Quality Taxonomy, Eval Subset, Limitations) can be transplanted from the Phase 1 doc.

**How to verify when complete.**

```bash
quarto render reports/final_report.qmd --to pdf
quarto render reports/final_report.qmd --to html
# Confirm Telugu glyphs render — no [] boxes
# Confirm page count is 15+
```

### 5. Methodology disclosure section [Eric]

**What this task accomplishes.** Satisfy the course's academic-integrity policy and demonstrate ethical use of AI tooling. The spec asks for explicit disclosure of AI tools used during the project. A vague "we used some AI" hurts; specific, honest disclosure ("Claude Code was dispatched as an autonomous engineer for Phases 2 and 3 module scaffolding under explicit task specs; all PRs were reviewed and merged by the human team") signals professional integrity and is what the grader is looking for on the integrity dimension.

**Sub-tasks**:

- [ ] Per the spec's academic integrity policy and [`../../README.md`](../../README.md), document AI tooling used and for what
- [ ] List Claude Code, any GitHub Copilot use, prompt engineering iterations
- [ ] Be specific: "Used Claude Code for initial scaffolding of the OCR adapter interface; all design decisions and final code reviewed and committed by human team members"

**Completion criterion:** Methodology section drafted; reviewed by teammate.

**Implementation.** Pure prose. ~2 paragraphs in the final report's Methodology Disclosure section.

**How to verify when complete.** Section names Claude Code explicitly, describes the engineer-dispatch model used for Phases 2 and 3, and confirms human review on every merge.

### 6. Limitations + honest analysis section [Eric]

**What this task accomplishes.** Move Dimension 5 (Analysis) from 11-13 ("solid results") to 14-15 ("solid results with self-awareness"). The grader explicitly rewards honest limitations. A report that claims everything worked perfectly looks naive; a report that names its caveats sounds professional.

**Sub-tasks**:

- [ ] Ground-truth quality caveats (community-contributed corpus)
- [ ] Sample-size caveats (30 eval pages is small for strong statistical claims)
- [ ] Model-choice caveats (no GPT-4o or Claude comparison)
- [ ] Validation-method caveats (LLM judging LLM is non-independent)
- [ ] One paragraph per caveat — honest, not defensive

**Completion criterion:** Limitations section drafted. The honesty is what moves Dimension 5 from 11-13 to 14-15.

**Implementation.** Pure prose, ~4-5 paragraphs. Can largely transplant from the Phase 1 `corpus_characterization.qmd` Limitations section, extended with Phase 4 caveats around LLM-judging-LLM independence.

**How to verify when complete.** Section reads as self-aware rather than defensive. Each caveat acknowledges a real constraint and (where possible) sketches what a future version would do differently.

### 7. Build the 15-minute presentation [50/50 split — both present roughly equally]

**What this task accomplishes.** The presentation is the smallest rubric weight (a portion of Dimension 7's 5 pts) but the highest visibility — the grader is in the room. A solid presentation with a working demo elevates the perceived quality of the entire project; a fumbled one drags down even a strong report. The 50/50 split signals equal team contribution, which the grader is explicitly looking for.

The presentation must visibly reflect equal contribution regardless of where the actual coding load fell. Split is 50/50 by time. Mitigations below de-risk the language-fluency challenge without compromising equality of role.

- [ ] Eric: slide structure (Quarto Reveal.js): Problem → Corpus → Pipeline → Results → Demo → Limitations → Q&A
- [ ] Both: assign sections roughly 50/50 by speaking time. Recommended split — Eric: Problem, Pipeline, Limitations. Teammate: Corpus, Results, Demo. (Section assignment swappable; what matters is equal time.)
- [ ] Each presenter writes their own section's slide notes in **scripted form** — full sentences they will read or have nearly memorized. Reduces ad-lib pressure for both, especially the teammate, and makes timing predictable.
- [ ] Both: rehearse together at least twice end-to-end. Time each section, adjust if anyone runs long.
- [ ] Q&A strategy: the presenter who delivered a section fields questions on that section first. If they get stuck or the question is broader, the other team member chimes in. Practice this hand-off explicitly during rehearsal.
- [ ] Live demo (~3 min, during the teammate's Demo slot): run `python -m src.ocr.cli` on one known-clean sample page. Pre-recorded screen capture as fallback if API is down on the day.

**Completion criterion:** Slides built; both team members own roughly half of speaking time; demo runs end-to-end without manual intervention; rehearsal hits 13-15 min with both presenting confidently. The grader should not be able to tell from the presentation alone who carried more of the coding load.

### 8. Package the 500+ page processed corpus sample [Eric]

**What this task accomplishes.** Satisfy the spec's required-deliverable line item ("processed sample of at least 500 pages"). Without this, the project is missing a piece of paper the rubric explicitly enumerates, regardless of how good the report is.

**Sub-tasks**:

- [ ] Confirm `data/processed/submission_sample/` has 500+ pages
- [ ] Add a manifest (`README.md` in that directory or alongside) listing source book IDs and counts
- [ ] Decide submission format: zipped directory in the GitHub repo's release, or a separate cloud-storage link in the README. Class submission instructions should clarify. Default: zipped attached to a GitHub release tag.

**Completion criterion:** 500+ pages packaged; manifest documents provenance.

**Implementation.** Pure packaging. `zip -r submission_sample.zip data/processed/submission_sample/` plus a manifest README. GitHub release tag holds the artifact.

**How to verify when complete.**

```bash
unzip -l submission_sample.zip | grep -c '\.txt$'   # → 500+
```

### 9. Repo hygiene pass [Eric]

**What this task accomplishes.** Score on Dimension 6 (Code Quality and Reproducibility, 10 pts). A repo that lints clean, tests clean, and reproduces from a fresh clone signals professional discipline. A repo with stale checkboxes, leaked secrets, or a broken README quickstart signals the opposite, regardless of how good the code itself is.

**Sub-tasks**:

- [ ] `ruff check src/ tests/` — clean
- [ ] `pytest -m "not slow and not api"` — clean
- [ ] Confirm `.env` is gitignored and `.env.example` is committed (per [`../standards/credential_handling_standard.md`](../standards/credential_handling_standard.md))
- [ ] Confirm `data/` is gitignored (with the documented exceptions for committed metadata)
- [ ] README quickstart works from a fresh clone (have the teammate verify on a clean checkout)
- [ ] All planning checkboxes in `roadmap.md` and `phase_*.md` reflect reality
- [ ] [`loose_ends.md`](loose_ends.md) reviewed; in-scope items either fixed or explicitly deferred with reasoning

**Completion criterion:** Fresh-clone reproduction works through `scripts/download_dataset.py --subset 1` + a single OCR call.

**Implementation.** Pure verification + small doc-state updates. Rauf re-cloning the repo in a temp directory and walking the README is the canonical reproduction test.

**How to verify when complete.** All bullets above pass. The fresh-clone test specifically:

```bash
# In a temp directory, NOT the working repo
git clone https://github.com/Pumapumapumas/ml-class-project.git fresh-test
cd fresh-test
scripts/setup_env.sh
source .venv/bin/activate
python scripts/download_dataset.py --subset 1
# Followed by one OCR call to confirm the pipeline works end-to-end
```

### 10. Final submission package [Eric]

**What this task accomplishes.** The actual shipping step. Pulling everything together into the form the course requires and submitting before the deadline. A perfect project that misses the submission window is a zero.

**Sub-tasks**:

- [ ] Submit per course instructions: GitHub repo URL, rendered report (HTML + PDF), presentation slides, link to processed corpus sample
- [ ] Tag the repo at submission: `git tag v1.0-submission`
- [ ] Confirm the teammate has reviewed the final report

**Completion criterion:** Submitted on time. Submission email/portal entry confirms receipt.

**Implementation.** Pure submission. Verify the artifacts list against the spec one more time before clicking submit.

**How to verify when complete.** Submission confirmation received. Tag visible on GitHub.

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
