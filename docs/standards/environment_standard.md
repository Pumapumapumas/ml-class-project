# Environment Standard

**Status:** Active
**Scope:** How the project's Python environment, system tools, and model caches are installed and isolated. The discipline that keeps the host OS unbroken.

---

## Why we have an environment standard

This project runs on a personal workstation, not a dedicated VM. The host runs other things you care about. The single largest risk in a 2-week ML project is a teammate or future-you `sudo apt install`-ing something during a frustrated debugging session and leaving the workstation worse than they found it.

This standard says: **none of this project's setup touches the host as `sudo`. Project code lives in a `venv`. System tools that would otherwise need `sudo apt install` live in Docker. Model weights live in project-local caches.**

---

## The hybrid model

| Concern | Where it lives | Rationale |
|---------|---------------|-----------|
| Project Python code | `./.venv/` | Pure Python, isolated, fast iteration |
| Python ML/OCR libs (pandas, opencv-python, jiwer, google-generativeai, huggingface-hub, surya-ocr, etc.) | `./.venv/` via `pip install -r requirements.txt` | All pip-installable; venv keeps them off the host |
| Tesseract + Telugu language pack | Docker image | Requires `sudo apt install tesseract-ocr-tel` on the host — exactly the thing we avoid |
| Surya OCR | `./.venv/` (Python package) | Model weights pointed to `./data/external/hf_cache/` via `HF_HOME` env var so they don't bloat `~/.cache/`. **First invocation downloads ~2–5 GB of weights** — budget time accordingly. |
| Gemini / OpenAI / Anthropic clients | `./.venv/` | HTTP calls, no system component |
| Jupyter Lab | `./.venv/` | Runs from the venv kernel |
| Quarto | Host install | Already widely installed; rendering doesn't bork anything |
| Pre-trained model weights (Surya, future Qwen) | `./data/external/hf_cache/` | Project-local, gitignored, doesn't pollute `~` |

---

## The non-negotiable rules

1. **Never `sudo pip install`.** All Python deps go in `./.venv/`. If a command requires `sudo` to install a Python package, you are doing it wrong.
2. **Never `sudo apt install` a project dependency on the host.** If a tool needs system-level installation (apt, brew), it goes in Docker, with a `Dockerfile` checked into `docker/<tool>/`.
3. **Cache directories point at project-local paths via environment variables.** Specifically:
   - `HF_HOME=$PWD/data/external/hf_cache` — HuggingFace model weights
   - `TRANSFORMERS_CACHE=$PWD/data/external/hf_cache/transformers` — transformers-specific caches
   These are set by `scripts/setup_env.sh` and assumed by the pipeline code. Keeps `~/` clean.
4. **Docker images are pinned to specific tags.** No `:latest`. Reproducibility requires us to know exactly which base image we're on.
5. **Dockerfiles are checked into the repo.** Under `docker/<tool>/Dockerfile`. Building any image is `docker build -t ml-class-project/<tool> docker/<tool>/`.
6. **The bootstrap script is the source of truth.** `scripts/setup_env.sh` does the entire setup on a fresh clone: creates the venv, installs requirements, builds Docker images, prints next steps. If you change how the environment is set up, you change that script too.

---

## Bootstrap on a fresh clone

```bash
git clone git@github.com:<owner>/ml-class-project.git
cd ml-class-project

# Single bootstrap command
scripts/setup_env.sh

# Configure credentials
cp .env.example .env
# Edit .env, fill in API keys

# Activate the venv for development
source .venv/bin/activate

# Verify the environment
pytest -m "not slow and not api"
```

`scripts/setup_env.sh` exits non-zero if anything fails, so you can wire it into CI later if needed.

---

## Adding a new dependency

### Python (the common case)

1. Add the package + minimum-version pin to `requirements.txt`
2. Run `pip install -r requirements.txt` in your active venv
3. Add an `import` and use it; tests prove it works
4. Commit the `requirements.txt` change

Pinning policy: prefer `>=X.Y.Z` for application dependencies; use `==X.Y.Z` for fragile pin requirements (e.g., a package with known breakage on the next minor version). Document the reason for any `==` pin with an inline comment.

### System tool (rare; needs Docker)

1. Create `docker/<tool>/Dockerfile`. Use a pinned base image (`ubuntu:22.04` or similar, with a digest if you want to be strict).
2. Install the tool inside the image, not on the host.
3. Update `scripts/setup_env.sh` to build the image as part of bootstrap.
4. Add a thin wrapper script `scripts/run_<tool>.sh` if calling the tool ergonomically matters.
5. Document the rationale in this standard (which tool, why Docker over venv).
6. Commit the Dockerfile + script changes together.

---

## What we explicitly do NOT do

- **Conda environments.** Standardized away. Reasons: conda's solver is slow, conda envs are a parallel universe to pip, and the team needs one mental model.
- **Poetry / PDM / uv project tooling.** All add value in larger projects but add friction in a 2-week academic context. `pip + requirements.txt` is the lowest common denominator.
- **Dev Containers / `.devcontainer/`.** Strong pattern, but the learning curve eats time we don't have. Reconsider for future projects.
- **Docker as the project's deployment target.** There is no deployment. The deliverable is the repo + the report. Docker is for system-tool isolation only.
- **A virtual machine.** This is a personal workstation; venv + Docker provides sufficient isolation. A VM is overkill for a class project.

---

## Verifying isolation

Sanity-check periodically that nothing has leaked onto the host:

```bash
# Should NOT show any Tesseract on the host
which tesseract 2>/dev/null && echo "WARN: tesseract found on host"

# Should NOT show HuggingFace caches in ~/
du -sh ~/.cache/huggingface 2>/dev/null

# Should NOT show project Python packages in user site
pip list --user 2>/dev/null | head
```

If any of these show project-related artifacts, something installed outside the venv/Docker boundary. Investigate and fix.

---

## When things break

If the venv gets into a bad state, the recovery is cheap:

```bash
deactivate
rm -rf .venv/
scripts/setup_env.sh
```

If a Docker image gets weird, rebuild from the Dockerfile:

```bash
docker rmi ml-class-project/tesseract
docker build -t ml-class-project/tesseract docker/tesseract/
```

Neither recovery path touches the host's system Python or apt packages, so blast radius stays local to the project. This is the entire point of the discipline.

---

## See also

- [`python_code_standard.md`](./python_code_standard.md) — code style and discipline
- [`credential_handling_standard.md`](./credential_handling_standard.md) — `.env` policy
- [`testing_standard.md`](./testing_standard.md) — how tests interact with the env
- Root [`README.md`](../../README.md) — quickstart for new clones
