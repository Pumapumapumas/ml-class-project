# Reports

Quarto sources and rendered outputs for project deliverables.

## Anticipated artifacts

| File | Purpose | Deliverable phase |
|------|---------|-------------------|
| `corpus_characterization.qmd` / `.pdf` | 2–3 page report on the Telugu corpus | Phase 1 |
| `preprocessing_comparison.qmd` / `.pdf` | Before/after visualization of preprocessing stages on 10+ pages | Phase 2 |
| `final_report.qmd` / `.pdf` / `.html` | Full project report covering all 5 phases, minimum 15 pages | Phase 5 |
| `presentation.qmd` / `.html` | 15-minute presentation slides for the project demo | Phase 5 |

## Rendering

```bash
# Single report
quarto render reports/final_report.qmd

# All reports
quarto render reports/
```

Generated PDFs and HTMLs are checked in alongside the `.qmd` source so the rendered deliverable is reviewable directly on GitHub.

## Style

Reports are written in Quarto markdown. Code chunks that execute against the pipeline should pull from `src/`, not re-implement logic. Long-running computations should be cached so the report renders quickly in review iterations.
