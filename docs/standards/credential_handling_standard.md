# Credential Handling Standard

**Status:** Active
**Scope:** How API keys, tokens, and other secrets are stored, loaded, and protected in this repo.

---

## The non-negotiables

1. **Secrets never enter git.** Not in source code, not in config files, not in commit messages, not even temporarily.
2. **Secrets never enter the report.** No screenshots that show keys, no examples that include real tokens.
3. **Secrets live in `.env` at the repo root.** The real `.env` is gitignored. `.env.example` is checked in as a template with placeholder values.
4. **If a secret leaks, treat it as compromised.** Rotate it. The cost of rotating a key is hours; the cost of a leaked key in a public report could be unbounded.

---

## Where secrets come from

For this project, the secrets are LLM API keys:

| Variable | Provider | How to obtain |
|----------|----------|---------------|
| `GEMINI_API_KEY` | Google AI Studio | https://aistudio.google.com/app/apikey — free tier |
| `OPENAI_API_KEY` | OpenAI | https://platform.openai.com/api-keys — paid |
| `ANTHROPIC_API_KEY` | Anthropic | https://console.anthropic.com/ — paid |
| `HUGGINGFACE_TOKEN` | HuggingFace | https://huggingface.co/settings/tokens — free, needed for some gated datasets |

---

## `.env` file

The `.env` file at the repo root holds the actual values:

```
# .env  (NEVER commit this file)
GEMINI_API_KEY=AIza...real-key-here...
OPENAI_API_KEY=sk-...real-key-here...
ANTHROPIC_API_KEY=sk-ant-...real-key-here...
HUGGINGFACE_TOKEN=hf_...real-token-here...
```

The `.env.example` file is the safe-to-commit template:

```
# .env.example  (committed to repo)
GEMINI_API_KEY=your-gemini-key-here
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
HUGGINGFACE_TOKEN=your-huggingface-token-here
```

When a teammate clones the repo:
1. `cp .env.example .env`
2. Fill in their own real values
3. Verify `.env` is gitignored — `git status` should not show it

---

## Loading secrets in code

Use `python-dotenv` to load `.env` at process startup:

```python
from dotenv import load_dotenv
import os

load_dotenv()  # reads .env into os.environ

gemini_key = os.environ.get("GEMINI_API_KEY")
if not gemini_key:
    raise RuntimeError(
        "GEMINI_API_KEY not set. Copy .env.example to .env and fill in your keys."
    )
```

**Rules:**
- **Never** hardcode a key in source. Not even as a "temporary" default.
- **Never** print or log a key. If you must log "I'm using the Gemini API," do not log the key itself.
- **Always** check the variable is set before using it; fail fast with a clear error message.

---

## CI / GitHub Actions

If we add CI, secrets go in **GitHub Actions encrypted secrets**, not in the repo. Reference them with `${{ secrets.GEMINI_API_KEY }}`.

For class submission, we don't need CI. This is here for completeness.

---

## What to do if a key leaks

1. **Immediately rotate the key** at the provider's dashboard.
2. **Check git history for the leak**: `git log --all --full-history -- <file>` or `git log -p -S "AIza"` (or whatever the key prefix is).
3. **If the leak is in a pushed commit**, you need `git filter-repo` or `git filter-branch` to scrub history, plus a force-push and notification to anyone who has cloned.
4. **If the leak is in an unpushed commit**, `git reset` or `git rebase` to remove and re-create the commit without the secret.
5. **Document the incident** in `docs/development/loose_ends.md` so the team knows.

---

## Local Claude context

`CLAUDE.md` at the repo root is **gitignored**. It contains project-specific notes intended for Claude during interactive sessions and may include local paths, internal context, or notes that aren't for the grader's eyes.

If you ever copy something into `CLAUDE.md` from a private source (e.g., a teammate's Teams chat about credentials), it stays local. Never check it in.

---

## Why this matters for grading

The project's GitHub repo is a deliverable. The grader will look at the commit history. Even one leaked key in history (even if rotated) communicates carelessness with credentials — and in industry contexts it's a fireable offense. We treat it the same here.
