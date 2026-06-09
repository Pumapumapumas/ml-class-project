# Data

Input data for the OCR pipeline. **Subdirectory contents are gitignored** — datasets live on disk only, never in git.

## Layout

```
data/
├── raw/            ← As-downloaded from HuggingFace. Never edited.
├── interim/        ← Partially processed (deskewed, binarized, etc.)
├── processed/      ← Final pipeline outputs ready for analysis
└── external/       ← Reference data: Telugu fonts (for synthetic generation), language models
```

## How to populate

```bash
# Pull a development subset (~500 MB, 5 books)
python scripts/download_dataset.py --subset 5

# Pull the full corpus (~13 GB, 221 books)
python scripts/download_dataset.py --full
```

The dataset is [`AlbertoChestnut/telugu-ocr`](https://huggingface.co/datasets/AlbertoChestnut/telugu-ocr) on HuggingFace, shared by a classmate. See [`downloads/message_from_another_team.md`](../downloads/message_from_another_team.md) for context.

## Why this is gitignored

The full corpus is ~13 GB. Even a development subset is several hundred MB. Repositories do not store datasets — they store the code that retrieves and processes them. Test fixtures (small, representative samples) live in [`tests/fixtures/`](../tests/README.md) when needed for unit tests.
