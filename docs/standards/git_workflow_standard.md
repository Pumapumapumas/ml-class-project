# Git Workflow Standard

**Status:** Active
**Scope:** Branch strategy, commit conventions, PR workflow, and authorship rules for this repo.

---

## Branching

- **`main` is the protected branch.** All work lands there via feature branches and rebases/merges. No direct commits to `main` after initial setup.
- **Feature branches** are named `<author-initials>/<short-description>` or `<feature>/<short-description>`.
  - Examples: `er/preprocessing-deskew`, `er/ocr-gemini-adapter`, `feature/validation-cer-wer`
- **Teammate(s) work on their own branches** and PR back to main.

### Branch lifetime

- Short-lived (hours to days). Long-lived branches drift and create merge pain.
- Rebase your branch onto the latest `main` before opening a PR.
- Delete the branch after the PR merges.

---

## Commits

### Authorship

**No commits in this repo carry "Co-Authored-By: Claude" or similar AI attribution.** The repo is a graded deliverable that will be inspected by the instructor. Claude-attributed commits would be inappropriate signaling.

- All commits are authored by you (or a teammate).
- Claude assists with code suggestions and refactors; the human author reviews, understands, and commits the work in their own name.
- AI tooling use is disclosed in the project report's methodology section, per the project spec's academic integrity policy.

### Commit message format

We use **conventional commit format**:

```
<type>(<scope>): <short summary>

<optional body — wrap at 72 chars>

<optional footer — refs, breaking changes>
```

**Types:**

| Type | Use for |
|------|---------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `refactor` | Restructuring without behavior change |
| `test` | Adding or fixing tests |
| `docs` | Documentation only |
| `chore` | Build, tooling, dependency bumps |
| `perf` | Performance improvement |

**Examples:**

```
feat(preprocessing): add adaptive thresholding for low-contrast scans
fix(ocr): handle Gemini rate-limit response without crashing pipeline
docs(standards): clarify when to use integration vs unit tests
chore(deps): pin opencv-python to 4.9.0 for reproducibility
```

**Rules:**
- Summary is a sentence, lowercase, no period, present tense ("add" not "added").
- Wrap body lines at 72 chars.
- One logical change per commit. Don't bundle "add feature X" and "refactor unrelated Y" together.

---

## Rebasing

Prefer rebase over merge for keeping `main` linear and readable.

**Standard flow:**

```bash
git checkout main
git pull
git checkout my-feature-branch
git rebase main
# resolve conflicts if any
git push --force-with-lease
```

`--force-with-lease` (not `--force`) protects you from clobbering a teammate's push to the same branch.

Squash multiple WIP commits into a clean set with `git rebase -i main` before opening a PR. The PR commit history should tell a coherent story, not show every "fix typo" along the way.

---

## Pull requests

Even for a small team, PRs serve as a review and documentation checkpoint.

**A PR description has:**
- A summary of what the PR does (1–3 sentences)
- Why it's needed (link to the roadmap phase or loose-end entry if relevant)
- How to verify it (commands to run, screenshots, before/after metrics)
- Any known limitations or follow-up

**A PR is ready to merge when:**
- All tests pass locally
- It rebases cleanly onto `main`
- A teammate (or self, for solo work) has read the diff and understood it
- Linter and formatter are happy

---

## What does NOT go in git

See [`.gitignore`](../../.gitignore) and the [Credential Handling Standard](./credential_handling_standard.md).

- Secrets (`.env`, API keys, credentials)
- Large data (`data/`)
- Generated/derived files (`__pycache__/`, `.ipynb_checkpoints/`, etc.)
- Local Claude context (`CLAUDE.md` if it contains private project notes; **this CLAUDE.md is gitignored** — see the standard)

If something sensitive gets committed by accident, **stop**. Don't push. Rewrite history with `git rebase -i` or `git filter-repo` to scrub it before any push leaves your machine.

---

## When to merge to main

- Feature is complete and tested
- Documentation is updated
- Code passes linter and formatter
- Tests pass
- PR has been reviewed (by self or teammate)

**After merge:**
- Delete the feature branch
- Update `docs/development/roadmap.md` if a phase milestone was hit
