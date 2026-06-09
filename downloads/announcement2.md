VG
Venkat Gudivada
AuthorTeacher
Posted Jun 1 10:16pm


Discussion Topic: Telugu OCT DatasetsTelugu OCT Datasets
Publicly Available Datasets

1. IIIT-Hyderabad Datasets IIIT-H has produced several Indic script datasets. Their Devanagari and South Indian Scripts word-level datasets include Telugu, with cropped word images and Unicode labels. Check their CVit lab page at http://cvit.iiit.ac.in/research/projects/cvit-projects/ — they host multiple OCR benchmarks.

2. BHARAT OCR / TDIL (Government of India) The Technology Development for Indian Languages (TDIL) programme under MeitY has released scanned document datasets with ground truth for Telugu and other Indic scripts. Access via https://tdil-dc.in. Registration is free for research use.

3. Dakshina Dataset (Google) Google released the Dakshina dataset, which includes Telugu script data. It is available on GitHub at google-research-datasets/dakshina. While primarily a transliteration dataset, it contains native script text useful for ground truth.

4. MLe-DocBank / IndicOCR Benchmarks AI4Bharat (IIT Madras) has been actively building Indic NLP and OCR resources. Their indic-ocr efforts and the broader AI4Bharat GitHub organization are worth checking directly at https://github.com/AI4Bharat.

5. EMILLE / CIIL Corpus The EMILLE corpus contains Telugu text that can serve as ground truth, though you would need to pair it with scanned images yourself.

If you need to create your own ground truth

A practical approach many researchers use:

Take Telugu books or documents from DLI (Digital Library of India) or archive.org — many are scanned PDFs of Telugu publications
Use Label Studio or Tesseract's tesstrain tooling to annotate ground truth at the line or word level
Tesseract already ships with a Telugu model (tel), and its training data repo (tesseract-ocr/tesstrain on GitHub) includes synthetic ground truth generation pipelines using Unicode text + fonts
Quick Synthetic Ground Truth Option

If you need volume quickly for testing, you can generate synthetic paired data:

Take Unicode Telugu text (from Wikipedia dumps or news corpora like IndicCorp)
Render it to images using Telugu fonts (e.g., Pothana2000, Gautami, Vani) with varied sizes, noise, and blur
This gives you unlimited image–Unicode pairs for evaluation

