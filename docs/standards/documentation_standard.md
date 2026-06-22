# Documentation Standard

**Status:** Active
**Scope:** Conventions for documentation in this repo. Covers planning docs, standards, user-facing guides, and code-level documentation.

---

## Where documentation lives

All documentation lives under `docs/`. The split:

```
docs/
├── standards/      ← This kind of doc. How we work.
├── development/    ← Planning, roadmap, phase tracking. What we're building and how.
└── guide/          ← User-facing. How someone else would use what we built.
```

**Code-level documentation** (docstrings, inline comments) lives in source files, not in `docs/`.

---

## Documentation philosophy

- **Docs are deliverable.** The final project report is graded. The supporting docs (standards, roadmap, README) communicate professionalism to the grader and to teammates. Treat them with the same care as code.
- **Docs decay if unloved.** A doc that contradicts the code is worse than no doc — it actively misleads. When you change code that's referenced in a doc, update the doc in the same commit.
- **Write for the next person.** That person might be a teammate, the grader, a future self, or someone reusing this work in another semester. Assume they didn't sit in your head during development.

---

## File naming

- Lowercase, underscore-separated: `documentation_standard.md`, `corpus_characterization.md`.
- Standards files end with `_standard.md`.
- Roadmap and phase files live under `docs/development/` (see [Repo Layout Standard](./repo_layout_standard.md)).
- One concept per file. Don't combine "documentation" and "testing" into one file just because they're short.

---

## Markdown conventions

- **Headings** form the table of contents. Use them.
- One `# H1` per file (the title). Use `##` and `###` for sections.
- **Code blocks** always specify language: ` ```python ` not ` ``` `.
- **Tables** for structured comparisons (e.g., model comparison, file inventory).
- **Bold for emphasis on action words**: *Do X. Never Y.* Not for decoration.
- Wrap prose at ~100 chars or let your editor soft-wrap — don't hard-wrap mid-sentence at arbitrary widths.

---

## Standards docs

A standards doc tells the reader **what to do, when to do it, and what breaking it looks like**.

**Required sections (in this order):**

1. **Title** (`# Standard Name`)
2. **Status + Scope** — brief frontmatter showing the doc is current and what it covers
3. **The rules themselves**, organized by topic
4. **Examples** — show what compliant code/structure looks like

**Do NOT:**
- Mix standards (rules) with planning (what we're building) in the same file
- Write standards for things you don't actually enforce — every rule should be inspectable in code review

---

## Development planning docs

Planning docs live under `docs/development/`. Two main types:

### Roadmap (`roadmap.md`)

The 30,000-foot view of what we're building. One paragraph per phase. Each phase lists 3–5 completion criteria as checkboxes.

**Rules:**
- Status at the top (e.g., "Current phase: Phase 3 — OCR Pipeline").
- Checkboxes are checked only when the phase is genuinely complete.
- Loose ends do NOT live in the roadmap. They live in a dedicated `loose_ends.md`.

### Phase docs (`phase_N_<name>.md`)

Per-phase implementation plans. Detail level: enough that a teammate could pick up where you left off if you got hit by a bus.

**Structure:**
- Goal of this phase
- Dependencies on prior phases
- Tasks (numbered, with completion criteria)
- Open questions (be honest)
- Outputs / deliverables

---

## User-facing guides (`docs/guide/`)

**For this project's scope, the root [`README.md`](../../README.md) is the user-facing guide** — installation, quickstart, pipeline invocation, and reproducibility all live there. `docs/guide/` holds supplementary user-facing docs as they arise:

- `teammate_onboarding.md` — get a new team member productive
- (additional guides added as the project grows)

A larger project would split the guide content into separate files under `docs/guide/` (e.g., `installation.md`, `running_the_pipeline.md`, `data_setup.md`). For a project of this scope, splitting would fragment a small story across several files for no real benefit. Keep `docs/guide/guide.md` as a pointer back to the README.

---

## Loose ends convention

Things we noticed but deferred (bug ideas, future improvements, "we should refactor X") go in `docs/development/loose_ends.md` — **not** scattered in roadmap docs, phase docs, or TODO comments throughout the code.

**Format:** a single flat list of checkbox entries. No `## Open` / `## Resolved` sections — toggle the checkbox in place when an item is resolved and append a short resolution note. Entries stay in the list after they're resolved (the history is useful when something resurfaces).

**Each entry has:**

- `- [ ]` for open, `- [x]` for resolved
- Date noted (`YYYY-MM-DD`)
- One-line summary, bolded
- What we'd do if we got to it (or, for resolved items, what we did)
- Severity: blocking / important / nice-to-have

**Example:**

```markdown
- [x] **2026-06-09 — Upstream dataset has dot-prefixed book directories.**
  Some book directories start with `.` which breaks default-glob walking.
  **Resolution:** download script normalizes by stripping the leading dot.
  *Severity: nice-to-have.*
```

This keeps the roadmap clean and gives us a single place to scan before submission.

---

## Code documentation

Source files use docstrings on every public function, class, and module.

**Format:** Google-style or NumPy-style — pick one in the [Python Code Standard](./python_code_standard.md) and stick to it across the repo.

Inline comments explain **why**, not **what**. The code already shows what; the comment exists for context the code can't convey (e.g., "this hardcoded constant matches the Tesseract page-segmentation mode for column layout").

---

## When in doubt

Look at the existing docs in this repo. Match their tone, structure, and depth. Consistency is more valuable than perfection.
