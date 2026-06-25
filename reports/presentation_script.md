# Presentation Script — Telugu OCR Project

**Target: ~10 minutes total. Read verbatim or near-verbatim. Each slide has a duration target.**

**Two presenters:** Rauf Agyemang reads slides 1–4 (intro through corpus/taxonomy). Eric Rue takes over at slide 5 through to the end. The handoff is at the end of slide 4.

Open the slide deck in a browser (`reports/presentation.html`) and screen-record while reading. Tools: OBS, Zoom (record-only mode), Loom, QuickTime screen recording, or Windows Game Bar.

---

## Slide 1 — Title (~30 sec) — RAUF

> "Hello. My name is Rauf Agyemang, and with my teammate Eric Rue, we built a Telugu OCR project using vision-language models.
>
> In this presentation we will walk through what we built, three findings from our experiments, and the story of the iterations behind the project — which Announcement 3 told us matters more than the final result."

*[Pause briefly. Advance to slide 2.]*

---

## Slide 2 — The problem (~60 sec) — RAUF

> "Telugu is a Dravidian language with about 80 million speakers. The script comes from the Brahmi family. Three things make OCR for Telugu harder than for Latin text.
>
> First, compound characters. Two or three consonants stack on top of each other into one visual shape. The visual unit does not match a simple sequence of letters.
>
> Second, vowel marks called matras. They attach above, below, before, or after the base consonant. A single syllable can combine several of them.
>
> Third, the resulting conjuncts do not break apart cleanly into a left-to-right stream of characters. This breaks the assumptions that OCR engines built for alphabet scripts rely on.
>
> On top of this, our corpus is historical Telugu printed books, with the typical problems — fading, paper damage, and page skew.
>
> So our research question is simple. Do vision language models perform better than classical OCR on a script like this? And if so, at what cost?"

*[Advance to slide 3.]*

---

## Slide 3 — Methodology (~60 sec) — RAUF

> "Our comparison matrix is four OCR systems, with up to five preprocessing variants, on thirty stratified pages. The full matrix is 510 measurements.
>
> The four systems cover the cost range. Tesseract 5 is the open-source classical baseline, running in a Docker container with the Telugu language pack — zero dollars per page. Gemini 2.5 Flash is Google's smallest vision LLM, less than one cent per page. Claude Sonnet 4.6 is the mid-tier Anthropic model at about two cents per page. And Claude Opus 4.8 is the flagship, around thirteen cents per page.
>
> We score each output with CER and WER using the jiwer library, with NFC normalization so equivalent Unicode forms do not inflate the error rate.
>
> Beyond CER, we built two validation methods that do not need ground truth: LLM fluency scoring, and cross-model agreement. Eric will show the calibration results later in the presentation."

*[Advance to slide 4.]*

---

## Slide 4 — Corpus + taxonomy (~60 sec) — RAUF (hand off to Eric at the end)

> "Our corpus is a public HuggingFace dataset by AlbertoChestnut. The instructor's promised corpus did not arrive in time, and several class teams converged on this same one. We pinned the upstream commit so the dataset is reproducible. We work with a six-book subset for the submission, and a five-book stratified eval subset for our experiments.
>
> For the eval subset, we tagged 97 pages by hand into five quality buckets — Clean, Skewed, Faded, Complex Layout, and Damaged. Then we drew six pages from each bucket using stratified random sampling with a fixed seed.
>
> One thing to note. Our taxonomy is data-driven, not chosen in advance. We waited to define the buckets until we had actually browsed the pages. This changed two things.
>
> We discovered that every image in our subset is exactly 1500 pixels wide, so the DPI distribution we planned to plot collapsed to a single value. We also discovered that ornamental section dividers and English-digit page numbers are part of standard Telugu typography. They are not quality problems, so we had to be careful not to count them as Complex Layout.
>
> Now I will hand off to my teammate Eric, who will walk through our three findings."

*[Advance to slide 5. Eric takes over.]*

---

## Slide 5 — Finding 1 (~90 sec — this is the headline) — ERIC

> "Thanks Rauf. This is the most interesting empirical finding in the project, and it's the result of an experiment we ran on the last day.
>
> When our initial matrix showed that preprocessing hurt EVERY model — including Tesseract, the classical OCR system we'd specifically expected to benefit — we extended the experiment to a per-stage ablation. We tested five preprocessing variants for each model: raw with no preprocessing, deskew alone, deskew plus denoise plus contrast — what we call 'grayscale-soft' because none of those stages destroys gradient information, then all four stages including binarize, and the original deskew-plus-binarize.
>
> Two patterns emerge from the ablation, shown in the figure on the right.
>
> First — and this is universal — binarization is destructive for every model. Any variant that includes binarize is worse than the same model's raw cell. Tesseract was hurt MOST by binarize, by 21 percentage points, because binarize collapses our 256-level grayscale page to just 2 unique pixel values with zero percent mid-tones, and Tesseract's own tuned internal binarization needs that grayscale gradient to detect character strokes.
>
> Second — and this is the nuance — the other three stages are MODEL DEPENDENT. Claude Sonnet and Tesseract both reach their best CER under the grayscale-soft variant. The CLAHE contrast lift and the non-local-means denoising help these models recover small-stroke detail without destroying anything. But Gemini Flash actively suffers from grayscale-soft — its CER goes UP when we add denoise and contrast. Gemini's vision encoder appears more sensitive to perturbations than the small benefit of cleaning up the page.
>
> The lesson: preprocessing must be tuned to the model class. Binarize is always wrong. The other stages — try them, measure, choose per model."

*[Advance to slide 6.]*

---

## Slide 6 — Finding 2: cost vs quality (~60 sec)

> "Second finding: the cost-quality tradeoff is sharper than you'd think.
>
> Reading the scatter plot from top-left going down to bottom-right: Tesseract is free per page but has mediocre accuracy. Gemini Flash is essentially free at a fraction of a cent but is the worst on accuracy. The two Claude models cluster in the bottom-right at much better accuracy.
>
> Here's the surprise. Claude Opus is the most accurate model in our matrix at 27 percent CER on raw images, but it's only ONE percentage point better than Sonnet 4.6, which sits at 28 percent. And Opus costs SEVEN TIMES more per call.
>
> So for any production deployment, Sonnet is the rational choice. Opus matters for the comparison because it confirms 'more capable models do help, but with diminishing returns,' but you would not pay 7x for one percentage point in a real workflow."

*[Advance to slide 7.]*

---

## Slide 7 — Finding 3: Tesseract beats Gemini Flash (~60 sec)

> "Third finding — and this one was genuinely surprising to me.
>
> A 30-year-old open-source classical OCR system, Tesseract, beats Google's flagship general-purpose vision LLM, Gemini Flash 2.5, by 18 percentage points mean CER on Telugu.
>
> That's a real correction to the implicit assumption that vision LLMs are automatically better. They're not — for low-resource scripts, training-data coverage of the target language matters more than model size or general capability.
>
> The practical takeaway: you should test per-language before making language-wide claims about vision LLM OCR quality."

*[Advance to slide 8.]*

---

## Slide 8 — Per-model failure modes (~60 sec)

> "We also asked a more granular question: WHAT kinds of errors does each system make?
>
> We computed character-level diffs against ground truth and classified each edit by Unicode codepoint rules. The categories are vowel signs, conjuncts, base consonants, and a few others.
>
> The headline finding is on the right side of the table. The three vision LLMs — Opus, Sonnet, and Gemini — all share the SAME top failure mode: vowel signs, the diacritic attachments that visually combine with base consonants. They nail the gestalt of the page and the base consonant shapes, but they consistently miss the small marks above and below.
>
> Tesseract has the opposite signature. Its top error category is base consonant shapes — it misreads the basic letter forms more often than the diacritics.
>
> So classical OCR and vision LLMs don't just have different accuracies — they fail in different ways."

*[Advance to slide 9.]*

---

## Slide 9 — LLM validation calibration (~60 sec)

> "On top of the CER measurements, we built two ground-truth-free quality estimators and calibrated them against the CER on the eval subset.
>
> Method A is LLM fluency scoring — a Claude judge rates each OCR output for naturalness as Telugu prose on a 1-to-5 scale. Method B is cross-model agreement — we compute the SequenceMatcher similarity ratio between two model readings of the same page; pages where models converge are presumed easier.
>
> Both correlate negatively with CER, which is the right direction — better signal means lower CER. The interesting finding is that cross-model agreement is the STRONGER predictor, with Spearman rho of negative 0.53, versus negative 0.40 for fluency scoring.
>
> Why? Because cross-model agreement uses only the OCR outputs themselves, no judging step. When OCR quality is uniformly poor, the LLM judge collapses to giving everything a 1 or 2 — but cross-model agreement still distinguishes pages where the bad readings happen to converge from pages where they wildly diverge.
>
> So for at-scale quality estimation on unlabeled corpora, agreement is the cheaper and more reliable signal."

*[Advance to slide 10.]*

---

## Slide 10 — Iteration story (~90 sec)

> "I want to spend a minute on the iteration story because the course's Announcement 3 explicitly emphasized that documenting iteration matters more than any final number.
>
> Our model lineup changed four times in 48 hours. Gemini 1.5 Flash was retired by Google partway through our project — we got 404 NOT_FOUND on our first live call and had to bump to 2.5. We cut Surya OCR because it pulls 2 to 5 gigabytes of model weights on first run, which was unacceptable install risk on our four-day timeline. We added Claude as the third model when we realized our cross-model agreement metric needed two strong models to produce a meaningful signal. And then late on the last night we brought BOTH Tesseract and Opus back when we realized the data would tell a richer story with them included.
>
> The rate-limit story is also worth mentioning. We fired all four cells of the matrix in parallel against the Gemini free tier, which is 15 requests per minute. Two parallel cells gave us 30 effective RPM and the free tier shut us down hard. We tried a serial retry script. We bumped the adapter's retry budget. The clean resolution was to enable Gemini paid tier, which I did at 11pm last night with my credit card directly in AI Studio. The 39 missing pages filled in 7 minutes wall-clock. The full 415-page submission run finished overnight. Total Gemini cost: under 30 cents.
>
> We also used an autonomous engineer-dispatch workflow extensively — Claude Code instances running headlessly with multi-agent review producing PRs for human review. That model caught real bugs that we would have missed."

*[Advance to slide 11.]*

---

## Slide 11 — Limitations (~45 sec)

> "Honestly disclosed limitations.
>
> No alternative binarization tested — our per-stage ablation isolated binarize as universally destructive, but we did not try a gentler binarization like Otsu's global threshold alone to see if 'softer binarization' would also hurt. No prompt-variant study — every vision LLM got the same system prompt. No purpose-trained document OCR transformer like Surya or TrOCR in the matrix. No systematic hyperparameter tuning. And six pages per bucket is enough for large effects but not subtle ones.
>
> But the project DID exactly what the course's Announcement 3 quotes at the bottom of this slide. Performance improvements often come not from inventing a new algorithm, but from making better decisions about data preparation, model selection, workflow design, and evaluation methodology. We discovered that classical and vision LLM failure modes are different. We discovered binarization is universally destructive while other preprocessing stages are model-dependent. We discovered cross-model agreement is a better quality estimator than LLM judging. That's the kind of finding the rubric explicitly rewards."

*[Advance to slide 12.]*

---

## Slide 12 — Conclusion (~15 sec)

> "Five-point summary, total spend under ten dollars, code and the full thirty-seven page report at the repository.
>
> Questions?"

*[Stop recording.]*

---

## If you run long

The recording target is 10 minutes; the instructor's spec says **no penalty for longer**. If you go to 12-13 minutes, that's fine.

If you go SHORT (under 9 min), the slides where you can naturally elaborate without padding:

- **Slide 5 (preprocessing finding)** — add a sentence about how this is the kind of empirical surprise the rubric rewards
- **Slide 9 (validation calibration)** — add a sentence about how this means we can quality-estimate the full 415-page corpus without ground truth
- **Slide 10 (iteration story)** — add a sentence about Rauf's Phase 1 work or about announcement 4-5's submission-format pivot

## Pacing tips

- Read the script at a measured pace, not rushed. ~150 words/min is comfortable.
- Pause briefly at slide transitions. The pauses make it sound less robotic.
- If you flub a word, just keep going — re-recording costs more than a small slip.

## Recording setup checklist

1. Close email, Slack, and any notifications
2. Set Do Not Disturb on the OS
3. Open `reports/presentation.html` in your browser, full-screen (press `F`)
4. Open this script in a second window or on a phone
5. Test microphone level with a 5-second test recording
6. Record. Aim for one clean take.
7. Save as MP4. Filename suggestion: `FinalProject_Rue_Eric_Presentation.mp4`
