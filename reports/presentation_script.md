# Presentation Script — Telugu OCR Project

**Target: ~10 minutes total. Read this verbatim or near-verbatim. Each slide has a duration target.**

Open the slide deck in a browser (`reports/presentation.html`) and screen-record yourself reading this script while advancing slides. Tools: OBS, Zoom (record-only mode), Loom, QuickTime screen recording (macOS), or Windows Game Bar.

---

## Slide 1 — Title (~30 sec)

> "Hi, I'm Eric Rue, and this is our project on Telugu OCR using vision-language models. My teammate Rauf contributed the Phase 1 corpus characterization work that the data sections in this report draw on.
>
> Today I'll walk through what we built, three empirical findings that I think are genuinely interesting, and the iteration story behind getting there — which the course's Announcement 3 emphasized matters more than any final number."

*[Pause briefly. Advance to slide 2.]*

---

## Slide 2 — The problem (~60 sec)

> "Telugu is a Dravidian language with about 80 million speakers, written in a script descended from Brahmi. Three properties make OCR for it harder than Latin scripts.
>
> First, compound characters — two or three consonants stack vertically into a single visual ligature, so the visual unit doesn't map to a linear sequence of glyphs.
>
> Second, vowel marks called matras attach above, below, before, or after the base consonant. One syllable can combine several of them.
>
> And third, the resulting conjuncts don't decompose cleanly into a left-to-right character stream, which breaks the segmentation assumptions OCR engines built for alphabets rely on.
>
> On top of that, our corpus is historical Telugu printed books with all the typical degradation — fading, paper damage, skew.
>
> So the research question is simple: do vision LLMs outperform classical OCR on a script like this, and if so, at what cost?"

*[Advance to slide 3.]*

---

## Slide 3 — Methodology (~60 sec)

> "Our comparison matrix is four OCR systems, two preprocessing conditions, thirty stratified pages. That's 240 OCR runs.
>
> The four systems span the cost spectrum. Tesseract 5 is the open-source classical baseline, running in a Docker container with the Telugu language pack — zero dollars per page. Gemini 2.5 Flash is Google's smallest vision LLM, fractions of a cent per page. Claude Sonnet 4.6 is Anthropic's mid-tier model at about two cents per page. And Claude Opus 4.8 is their flagship, around thirteen cents per page.
>
> The preprocessing is a two-stage pipeline: deskew followed by adaptive binarization. We score with CER and WER using the jiwer library, with NFC normalization on both inputs so equivalent Unicode forms don't artificially inflate error rates.
>
> Beyond CER, we built two ground-truth-free validation methods: LLM fluency scoring and cross-model agreement. I'll show the calibration results in a few slides."

*[Advance to slide 4.]*

---

## Slide 4 — Corpus + taxonomy (~60 sec)

> "The corpus is a public HuggingFace dataset by AlbertoChestnut — the instructor's promised corpus didn't arrive, and multiple class teams converged on this same one. We pinned the upstream commit for reproducibility and work with a five-book, 415-page subset.
>
> For the eval subset, we tagged 97 pages by hand into five quality buckets — Clean, Skewed, Faded, Complex Layout, and Damaged — then drew six pages from each bucket by stratified random sampling with a fixed seed.
>
> One thing worth noting: the taxonomy is data-driven, not a-priori. We held off on defining buckets until we'd actually browsed the data. That changed two things. We discovered every image in our subset is exactly 1500 pixels wide, so the DPI distribution we'd planned to plot collapsed to a single value. And we discovered that ornamental section dividers and English-digit page numbers are standard Telugu typography, not quality defects — so we had to be careful disambiguating those from genuine layout complexity."

*[Advance to slide 5.]*

---

## Slide 5 — Finding 1 (~90 sec — this is the headline)

> "This is the most interesting empirical finding we got.
>
> Look at the delta column on the left. Preprocessing — our standard deskew-plus-binarize pipeline — made EVERY model perform worse. The vision LLMs were hurt by 3 to 16 percentage points, which we expected because they're trained on natural color and grayscale images.
>
> But the surprise is the bottom row: Tesseract, the classical OCR system that we specifically expected to benefit from binarization, was hurt the MOST — by 21 percentage points.
>
> We diagnosed this on the right. The raw image has 256 grayscale levels — a full gradient. After our adaptive thresholding, the preprocessed image has 2 unique pixel values — pure black or pure white — with zero percent mid-tones across the entire page.
>
> That destroyed the grayscale information that Tesseract's own well-tuned internal binarization needs to do character-edge detection. The thin Telugu strokes that vowel marks rely on became 1-pixel jagged transitions that Tesseract treated as noise and dropped.
>
> The lesson is sharper than what we'd initially hypothesized. Modern OCR systems all carry highly-tuned internal preprocessing. Pre-binarizing doesn't help them — it competes with their algorithms. Don't try to outsmart the model's preprocessing; trust it."

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
> Both correlate negatively with CER, which is the right direction — better signal means lower CER. The interesting finding is that cross-model agreement is the STRONGER predictor, with Spearman rho of negative 0.59, versus negative 0.45 for fluency scoring.
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
> No per-stage preprocessing ablation — we didn't break the pipeline into deskew-only versus binarize-only to isolate which stage is doing the damage. No prompt-variant study — every vision LLM got the same system prompt verbatim from the project spec. No purpose-trained document OCR transformer like Surya or TrOCR in the matrix. No systematic hyperparameter tuning. And six pages per bucket is enough for large effects but not subtle ones.
>
> But the project DID exactly what the course's Announcement 3 quotes at the bottom of this slide. Performance improvements often come not from inventing a new algorithm, but from making better decisions about data preparation, model selection, workflow design, and evaluation methodology. We discovered that classical and vision LLM failure modes are different. We discovered preprocessing hurts both. We discovered cross-model agreement is a better quality estimator than LLM judging. That's the kind of finding the rubric explicitly rewards."

*[Advance to slide 12.]*

---

## Slide 12 — Conclusion (~15 sec)

> "Five-point summary, total spend under ten dollars, code and the full thirty-page report at the repository. Thanks especially to Rauf for the Phase 1 corpus characterization notebook.
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
