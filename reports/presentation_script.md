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

> "Thanks Rauf. So this finding came out of an experiment we ran on the last day, and it's probably the most interesting result in the whole project.
>
> Our first matrix showed something we weren't expecting. Preprocessing made every model worse. Even Tesseract, the classical OCR system everyone assumes benefits from binarization. So we went back and ran a per-stage ablation. Five variants per model: raw, just deskew, deskew plus denoise plus contrast which we're calling 'grayscale-soft', then all four stages including binarize, and the original deskew-plus-binarize pipeline.
>
> The chart has the breakdown. Two patterns jump out.
>
> First, binarize is bad for everyone. Every variant that includes binarize loses to that model's raw output. Tesseract got hit hardest, 21 percentage points worse, because binarize collapses our 256-level grayscale image down to just two values, with zero mid-tones. Tesseract's own internal binarization is well-tuned and it needs that grayscale gradient to detect character strokes. We took that away from it.
>
> Second, the other three stages depend on the model. Sonnet and Tesseract both reach their best CER on the grayscale-soft variant. The CLAHE contrast adjustment and the non-local-means denoising help them recover small-stroke detail. Gemini Flash though, actually does worse with grayscale-soft. Its CER goes up. Gemini's vision encoder seems more sensitive to the perturbations than it is helped by the cleaner page.
>
> So the takeaway is, preprocessing has to be tuned per model. Binarize is universally bad. The other stages, try them, measure, and pick what works for your model."

*[Advance to slide 6.]*

---

## Slide 6 — Finding 2: cost vs quality (~60 sec)

> "Second finding. The cost-quality tradeoff is steeper than you'd expect.
>
> The scatter plot reads from top-left down to bottom-right. Tesseract is free per page, accuracy is mediocre. Gemini Flash is basically free, a fraction of a cent, but it's the worst on accuracy. The two Claude models cluster down in the bottom-right at much better accuracy.
>
> Here's the thing though. Claude Opus is the most accurate model in our matrix, 27 percent CER on raw images. But it's only one percentage point better than Sonnet 4.6 at 28 percent. And Opus costs seven times more per call.
>
> So for any real production use, Sonnet is the rational choice. Opus is useful for the comparison because it shows you do get gains from a stronger model, but the gains hit diminishing returns fast. Nobody is going to pay 7x for one percentage point in a real workflow."

*[Advance to slide 7.]*

---

## Slide 7 — Finding 3: Tesseract beats Gemini Flash (~60 sec)

> "Third finding, and this one actually surprised us.
>
> A 30-year-old open-source classical OCR, Tesseract, beats Google's flagship general-purpose vision LLM, Gemini Flash 2.5, by 18 percentage points mean CER on Telugu.
>
> That cuts against the assumption that vision LLMs are automatically better at this stuff. They're not. For low-resource scripts, what matters most is how much of the target language was actually in the training data, more than the model size or how capable it is in general.
>
> So the practical takeaway is, test per language before making any general claim about vision LLM OCR quality."

*[Advance to slide 8.]*

---

## Slide 8 — Per-model failure modes (~60 sec)

> "We also looked at a more granular question. What kinds of errors does each system actually make?
>
> So we computed character-level diffs against ground truth and classified each edit by Unicode codepoint rules. The categories are vowel signs, conjuncts, base consonants, and a few others.
>
> The interesting result is on the right side of the table. The three vision LLMs, Opus, Sonnet, and Gemini, all share the same top failure mode. Vowel signs, the diacritic marks that visually attach to base consonants. They get the overall shape of the page right, they get the base consonants right, but they consistently miss the small marks above and below.
>
> Tesseract is the opposite. Its top error category is base consonant shapes. It misreads the basic letter forms more often than it misses the diacritics.
>
> So classical OCR and vision LLMs don't just have different accuracy numbers. They fail in fundamentally different ways."

*[Advance to slide 9.]*

---

## Slide 9 — LLM validation calibration (~60 sec)

> "On top of the CER work, we built two quality estimators that don't need ground truth, and we calibrated them against the CER on the eval subset.
>
> Method A is LLM fluency scoring. A Claude judge rates each OCR output for how natural it reads as Telugu prose, on a 1-to-5 scale. Method B is cross-model agreement. We compute the SequenceMatcher similarity ratio between two model readings of the same page. Pages where the models converge are presumed easier.
>
> Both correlate negatively with CER, which is the direction we want. Better signal means lower CER. The interesting result is that cross-model agreement is the stronger predictor, Spearman rho of negative 0.53, versus negative 0.40 for fluency.
>
> Why is that. Because cross-model agreement only uses the OCR outputs themselves. There's no judging step. When OCR quality is uniformly poor across a cell, the LLM judge collapses to rating everything a 1 or a 2 and you lose the signal. But cross-model agreement still tells you the difference between pages where the bad readings happen to converge and pages where they wildly diverge.
>
> So for quality estimation at scale on unlabeled data, agreement is both cheaper and more reliable."

*[Advance to slide 10.]*

---

## Slide 10 — Iteration story (~90 sec)

> "I want to spend a minute on the iteration story, because Announcement 3 specifically called out that documenting iteration matters more than the final result.
>
> Our model lineup changed four times in 48 hours. Gemini 1.5 Flash was retired by Google partway through the project. We got a 404 NOT_FOUND on our first live call and had to bump to 2.5. We cut Surya OCR because it pulls two to five gigabytes of model weights on first run, and that was an install risk we couldn't afford on a four-day timeline. We added Claude as the third model when we realized our cross-model agreement metric needed two strong models to produce any meaningful signal. And then late on the last night we brought both Tesseract and Opus back, when it became clear the data would tell a much richer story with them in.
>
> The rate-limit story is worth mentioning too. We fired all four cells of the matrix in parallel against the Gemini free tier, which is 15 requests per minute. Two parallel cells gave us 30 RPM effectively, and the free tier shut us down hard. We tried a serial retry script. We bumped the adapter's retry budget. What actually worked was just enabling Gemini's paid tier, which I did at 11pm by putting a credit card on the AI Studio account directly. The 39 missing pages filled in 7 minutes wall-clock. The full submission run finished overnight. Total Gemini cost, under 30 cents.
>
> We also used a Claude Code extensively as an engineering assistant throughout. It caught bugs in code review that we would have shipped otherwise."

*[Advance to slide 11.]*

---

## Slide 11 — Limitations (~45 sec)

> "Some honest limitations.
>
> We didn't test an alternative binarization. The ablation isolated binarize as universally destructive, but we didn't try a gentler version like Otsu's global threshold alone to see if softer binarization would also hurt. We didn't do a prompt-variant study. Every vision LLM got the same system prompt. We didn't include a purpose-trained document OCR transformer like Surya or TrOCR in the matrix. No systematic hyperparameter tuning. And six pages per bucket is enough to detect large effects, but not subtle ones.
>
> That said, the project did exactly what Announcement 3 is quoting at the bottom of this slide. Performance improvements come from better decisions about data preparation, model selection, workflow design, and evaluation methodology, not from inventing new algorithms. We learned classical and vision LLM failure modes are different. We learned binarization is universally destructive while other preprocessing stages are model-dependent. We learned cross-model agreement is a better quality estimator than LLM judging. That's the kind of result the rubric rewards."

*[Advance to slide 12.]*

---

## Slide 12 — Conclusion (~15 sec)

> "Five-point summary on the slide. Total project spend was under ten dollars. Code, data, and the full 37-page report are all in the repository.
>
> Thanks for watching. Happy to take questions."

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
