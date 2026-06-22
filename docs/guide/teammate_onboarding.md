# Teammate Onboarding — Telugu OCR Project

Welcome, Rauf. This doc gets you from a fresh clone to your first PR.

---

## Welcome

You are a real contributor on this project, not a helper. Your work — corpus statistics,
preprocessing components, error analysis figures — goes directly into the graded deliverable.
Eric is the project lead and handles coordination, but the code and analysis you write will be
the substance of Phase 1 and Phase 2 deliverables.

**Please reach out as often as you need to.** Email, Teams, text — whatever works. Quick
questions are welcome; staying stuck silently is not. This doc and the linked phase docs are
the written reference, but they're not a substitute for talking when something doesn't make
sense. Eric is happy to walk through anything in this repo with you.

---

## What this project is

We are building an end-to-end pipeline that extracts Unicode text from scanned Telugu book
images using vision-capable large language models. The pipeline includes image preprocessing,
OCR with at least three models, and a validation framework that scores OCR quality without
needing manual ground-truth annotation.

This is a graded deliverable for CSCI/DASC 6020 (Machine Learning, Summer 2026) at East
Carolina University. The deadline is **June 23, 2026**. Full project details are in the root
[README.md](../../README.md).

---

## Windows setup (start here if you are on Windows)

This project's scripts are written for Linux. Windows can run them, but
you need to install one extra thing called **WSL2** (Windows Subsystem
for Linux). After you install WSL2, your Windows laptop can run Linux
programs side by side with Windows. This is the standard way professional
developers use Linux tools on a Windows machine.

If you are on macOS or Linux Mint, skip this section and jump to
[Setting up your environment](#setting-up-your-environment) below.

### Step 1 — Install WSL2 with Ubuntu

WSL2 is a one-time install. After this you will have a real Linux
environment running inside Windows.

1. Click the **Start menu**, type `PowerShell`.
2. **Right-click "Windows PowerShell"** and choose **"Run as administrator"**.
   (You must run as administrator or the install will fail.)
3. In the PowerShell window, type this exact command and press **Enter**:

   ```powershell
   wsl --install
   ```

4. Wait a few minutes for it to finish. It will download Ubuntu and set
   up everything.
5. When it finishes, **restart your computer**.
6. After restart, an "Ubuntu" window will open automatically. It will
   ask you to choose a **username** and **password**.
   - Pick any username (lowercase, no spaces — e.g., `rauf`).
   - Pick any password. **Write it down.** You will need it later for
     `sudo` commands.
   - When you type the password, the screen will not show anything as you
     type. That is normal Linux behavior.
7. When you see a prompt like `rauf@your-pc:~$` you are inside Ubuntu.
   You can close this window for now.

**Official Microsoft guide** if you need more help:
https://learn.microsoft.com/en-us/windows/wsl/install

### Step 2 — Install Docker Desktop

Docker Desktop runs the Tesseract OCR container we use as one of our
baseline models. It is free for students and personal use.

1. Open your web browser and go to: https://www.docker.com/products/docker-desktop/
2. Click **"Download for Windows"** and run the installer.
3. The installer will show a configuration page with checkboxes. **Two
   prompts matter — set them like this:**

   - **"Use WSL 2 instead of Hyper-V (recommended)"** → **leave CHECKED**.
     This is the default. This tells Docker to use the Ubuntu WSL2 you
     just installed as its Linux runtime. It is exactly what we want.
   - **"Use Windows containers"** (you may or may not see this prompt;
     it depends on the installer version) → **leave UNCHECKED**.
     Windows containers are a completely different thing — they run
     Windows applications, not Linux ones. Our Tesseract container is
     a Linux container, so this option must stay off.
   - Any other checkbox (e.g., "Add shortcut to desktop") is your choice.

4. After install, **restart your computer** if asked.
5. Open Docker Desktop from the Start menu. The first time it runs, it
   will ask you to accept the license — read and accept it.
6. Wait until the Docker Desktop status icon shows "Docker is running"
   (a small whale icon in the bottom-right system tray).
7. (Sanity check) Open Docker Desktop's settings → **General** tab.
   Confirm **"Use the WSL 2 based engine"** is checked. If it isn't,
   check it and click "Apply & Restart".

You do not need to learn Docker. Our scripts use it for you. You just
need it installed and running with the WSL 2 backend.

### Step 3 — Install Visual Studio Code (VS Code)

VS Code is the code editor we use. It has a special mode that lets it
work inside WSL2 / Ubuntu seamlessly.

1. Go to: https://code.visualstudio.com/
2. Click **"Download for Windows"** and run the installer.
3. During install, on the **"Select Additional Tasks"** screen, **check
   the box** that says **"Add to PATH"**. This lets you launch VS Code
   from the Ubuntu terminal later.
4. Finish the install and open VS Code at least once.

### Step 4 — Install the WSL extension in VS Code

This lets VS Code open files that live inside Ubuntu.

1. Open VS Code.
2. Click the **Extensions** icon on the left sidebar (looks like four
   little squares).
3. In the search box, type: `WSL`
4. Find the extension named **"WSL"** by **Microsoft** (the publisher
   matters — there are copycats).
5. Click **Install**.

After install, you should see a small green icon in the **bottom-left
corner** of VS Code. That icon is how you connect to WSL.

### Step 5 — Connect VS Code to Ubuntu

1. In VS Code, click the **green icon in the bottom-left corner** (or
   press **Ctrl+Shift+P** and type **"WSL: Connect to WSL"**).
2. VS Code will reopen itself. The bottom-left icon should now say
   something like **"WSL: Ubuntu"**.
3. Open the integrated terminal: **View → Terminal** (or press
   **Ctrl+`** — the backtick key, top-left of the keyboard).
4. The terminal prompt should look like: `rauf@your-pc:~$` — that means
   you are inside Ubuntu, not Windows.

You are now ready to continue with the steps below. **Every command
in the rest of this document is run inside the Ubuntu terminal** (the
one you just opened in VS Code).

### Step 6 — Install Git and Python inside Ubuntu

Ubuntu does not come with Git or all the Python pieces we need. Install
them with one command. When it asks for a password, use the Ubuntu
password you set in Step 1.

```bash
sudo apt update && sudo apt install -y git python3 python3-venv
```

Verify:

```bash
git --version
python3 --version
```

You should see Git 2.x and Python 3.12.x (or 3.11+).

### One critical rule for Windows + WSL

**Always clone the project into the Ubuntu home directory (`~/...`),
NEVER into `/mnt/c/Users/...`.**

WSL2 can technically read files on your Windows C: drive, but reading
hundreds of files from there is *extremely* slow — what should take 1
second can take 30 seconds or more. Our project has 415 page images,
so this matters.

The "right" place to clone is somewhere like `~/Repos/ml-class-project`.

---

## Setting up your environment

### Prerequisites

Before you begin, confirm you have:

| Requirement | Minimum version | Notes |
|-------------|----------------|-------|
| Linux, macOS, or Windows + WSL2 | — | Windows users: complete the [Windows setup](#windows-setup-start-here-if-you-are-on-windows) section above first |
| Python | 3.11+ | Check: `python3 --version` |
| Git | — | On Ubuntu/WSL: `sudo apt install git` |
| Docker | — | Needed for Tesseract; install before bootstrap. On Windows that's Docker Desktop |
| Free disk space | ~30 GB | The full corpus is ~13 GB; weights add ~2-5 GB more |

### Setup steps

```bash
# 1. Clone the repo (use SSH, not HTTPS)
git clone git@github.com:Pumapumapumas/ml-class-project.git
cd ml-class-project

# 2. Run the bootstrap script — this creates the venv, installs all deps, builds Docker images
scripts/setup_env.sh

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Copy the credentials template and fill it in
cp .env.example .env
# Open .env in any editor and fill in your Gemini API key (free tier is fine)

# 5. Download a small corpus subset for development (~500 MB, 5 books)
python scripts/download_dataset.py --subset 5
```

The bootstrap script (`scripts/setup_env.sh`) is the authoritative setup path. The README
Quickstart section also documents these steps: [README.md — Quickstart](../../README.md#quickstart).

### Verify the setup

Run the fast test suite. All tests should pass:

```bash
pytest -m "not slow and not api"
```

If this exits green, your environment is correctly set up. If tests fail, check that:
- The venv is activated (`source .venv/bin/activate`)
- `pip install -r requirements.txt` completed without errors (the bootstrap script does this,
  but a partial failure can leave a broken state)
- Docker is running (the Tesseract container is built during bootstrap)

If you are still stuck, open a draft PR with the error output and ping Eric.

---

## What you will be working on

### How the plan is structured

The project is organized into five phases. Two documents describe the plan:

- **[`docs/development/roadmap.md`](../development/roadmap.md)** — the high-level view. One
  paragraph per phase, a status header, and ownership checkboxes. Read this first to understand
  the shape of the whole project.

- **Phase docs** (`docs/development/phase_N_*.md`) — one file per phase. Each has a goal,
  task list with checkboxes, completion criteria, and open questions. These are your working
  documents while you are inside a phase.

### The plan is deliberate but not rigid

The roadmap is a plan, not a contract. We have two weeks and compressed timelines. Things will
shift. When something deviates from the plan — a task turns out to be different, you discover
a problem, a step becomes unnecessary — do not silently move on. Document it in
[`docs/development/loose_ends.md`](../development/loose_ends.md). That file is the single
place for deferred items, open questions, and discovered problems. It is reviewed before every
phase boundary and before submission.

### Your ownership at a glance

The roadmap has a full ownership table. The short version:

| Phase | Your tasks |
|-------|-----------|
| 1 | Corpus statistics notebook, plots and tables |
| 2 | Deskew module, binarize module, before/after visualization notebook |
| 3 | Tesseract adapter, Surya adapter (paired with Eric) |
| 4 | Classical CER/WER scoring module and CLI |
| 5 | Error categorization tables and plots, figures for the report, slide visual content |

Eric owns the prose, prompt engineering, pipeline interfaces, and orchestration. You own the
numerical work, visualizations, and the components listed above.

---

## Your recommended first PR

**This is the right place to start.** It validates your full setup end-to-end and does not
block Eric's parallel work.

### The task

Build the corpus statistics notebook: **Phase 1, Task 2** in
[`docs/development/phase_1_corpus_characterization.md`](../development/phase_1_corpus_characterization.md).

This requires:
1. Eric to have completed Task 1 (corpus inventory CSV). Eric will commit
   `data/external/corpus_inventory.csv` to `main`; when it's there, you'll see it
   after running `git pull`. If it is not there yet, you can still set up your
   environment, read the phase doc, and download the dataset.
2. Your environment is working and the corpus subset is downloaded.

### How we share files between us

Some files we work on together — the inventory CSV, headline statistics JSON, the
evaluation subset CSV, plots embedded in the report. These small "metadata" files
ARE tracked in git, alongside the code. The workflow:

1. Eric (or you) produces the file locally
2. Commits it with normal git: `git add data/external/corpus_inventory.csv` → `git commit` → `git push`
3. The other person pulls it: `git pull`

Files NOT shared via git (because they're too big):
- The raw Telugu page images and ground-truth text under `data/raw/` (~500 MB each pull)
- Preprocessed and OCR'd output under `data/interim/` and `data/processed/`
- Downloaded model weights under `data/external/hf_cache/`

These are regenerated on each machine by running the scripts (`download_dataset.py`,
the pipeline CLIs in Phase 2/3). Anything small and derived (a CSV, a JSON, a plot
PNG in `reports/`) goes in git. Anything large or easily regenerable does not.
See [`../standards/repo_layout_standard.md`](../standards/repo_layout_standard.md)
and the `.gitignore` at the repo root for the full picture.

### Step-by-step

**1. Create your branch**

Use your initials. For example, if your initials are "RS":

```bash
git checkout main
git pull
git checkout -b rs/01-corpus-stats
```

The branch naming convention is `<your-initials>/<short-description>`. See
[Git Workflow Standard](../standards/git_workflow_standard.md) for details.

**2. Create the notebook**

Create a new notebook at this exact path:

```
notebooks/01_corpus_characterization.ipynb
```

Start Jupyter Lab from the repo root with the venv active:

```bash
source .venv/bin/activate
jupyter lab
```

**3. What the notebook must produce**

The notebook loads the corpus inventory CSV (`data/external/corpus_inventory.csv`) that Eric
produces in Task 1. It then computes and plots:

- Image dimension distribution (histogram of width × height)
- DPI estimate (if available in EXIF data, or estimated from image dimensions)
- Mean and median page text length in characters
- File-size distribution (a proxy for scan quality variance)

The completion criterion from the phase doc:

> A notebook `notebooks/01_corpus_characterization.ipynb` that loads the inventory CSV and
> produces the four distributions as plots, plus a `corpus_stats.json` artifact in
> `data/external/` with the headline numbers.

**4. Create the JSON artifact**

Save headline numbers as `data/external/corpus_stats.json`. Example structure:

```json
{
  "total_books": 221,
  "total_pages": 18432,
  "median_image_width_px": 1240,
  "median_image_height_px": 1754,
  "mean_text_length_chars": 1823,
  "median_text_length_chars": 1712,
  "median_file_size_bytes": 412800
}
```

The exact fields should match what the notebook computes. Use whatever keys are clear and
consistent.

**5. Files you will create**

```
notebooks/01_corpus_characterization.ipynb   ← the notebook
data/external/corpus_stats.json              ← headline numbers artifact
```

Note: `data/` is gitignored. The `corpus_stats.json` file is small metadata — it IS committed.
Confirm with `git status` after creating it.

**6. Open a draft PR early**

You do not need to finish before opening a PR. Open a draft PR as soon as the notebook exists
with any content. This lets Eric see your progress and give early feedback.

```bash
git add notebooks/01_corpus_characterization.ipynb data/external/corpus_stats.json
git commit -m "feat(notebooks): add corpus characterization notebook with stats"
git push -u origin rs/01-corpus-stats
# Then open a Pull Request on GitHub and mark it as Draft
```

---

## Coding standards

The `docs/standards/` directory has one file per topic. You do not need to read all of them
now. Read the relevant one when a question comes up.

| Standard | Read when |
|----------|-----------|
| [Documentation Standard](../standards/documentation_standard.md) | Adding or modifying any doc file |
| [Python Code Standard](../standards/python_code_standard.md) | Writing Python code: naming, type hints, docstrings, error handling |
| [Testing Standard](../standards/testing_standard.md) | Writing tests or deciding where a test file belongs |
| [Git Workflow Standard](../standards/git_workflow_standard.md) | Committing, branching, opening or reviewing a PR |
| [Credential Handling Standard](../standards/credential_handling_standard.md) | Adding a new API key or touching `.env` |
| [Logging Standard](../standards/logging_standard.md) | Adding `print()` to debug something (use `logging` instead) |
| [Environment Standard](../standards/environment_standard.md) | Adding a Python dependency or debugging an install problem |
| [Repository Layout Standard](../standards/repo_layout_standard.md) | Deciding where a new file belongs |

The standards index is at [`docs/standards/README.md`](../standards/README.md).

---

## Git workflow

### Branch names

Format: `<your-initials>/<short-description>`

```
rs/01-corpus-stats
rs/02-deskew-module
rs/03-binarize-module
```

Keep branches short-lived. Finish the work, open a PR, and delete the branch after merge.

### Commit message format

We use **conventional commit format**:

```
<type>(<scope>): <short summary>
```

The summary is lowercase, present tense, no period at the end.

**Types:**

| Type | Use for |
|------|---------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `chore` | Tooling, dependency, or configuration change |
| `refactor` | Code restructuring without behavior change |

**Examples:**

```bash
feat(notebooks): add corpus statistics histogram plots
fix(preprocessing): handle zero-height images in binarize step
docs(phase1): mark corpus inventory task complete
test(preprocessing): add edge case for all-white input image
chore(deps): add matplotlib to requirements.txt
```

### No AI attribution in commits

**Do not add "Co-Authored-By: Claude" or similar tags to commit messages.** This is a graded
deliverable inspected by the instructor. AI tooling is disclosed in the final report's
methodology section — that is the correct place. Commit history records human authorship only.

Commits that include AI attribution lines will need to be rewritten before the PR merges.

---

## Asking for help

Eric is the project lead. When you are stuck, contact Eric directly — Teams, email, or whatever
channel you both use.

**Do not stay stuck for hours.** A short message to Eric saves both of you time. Something like:

> "I am stuck on X. I tried Y and got error Z. Can you help?"

**Open a draft PR early.** You do not need to finish before opening a pull request. A draft PR
shows Eric your current state: what files exist, what the notebook contains so far, what errors
you are seeing. This is better than a long message describing the problem.

**If something in the plan seems wrong or unclear**, say so. The phase docs are our best
understanding of the work before we start it. If the actual work turns out to be different,
that is useful information, not a mistake.

---

## Practical tips

Small habits that prevent problems:

- **Always activate the venv before working.**
  ```bash
  source .venv/bin/activate
  ```
  If `python` points to the system Python, the venv is not active.

- **Run the fast tests before every push.**
  ```bash
  pytest -m "not slow and not api"
  ```
  If something breaks, better to find it before Eric sees it in the PR.

- **Run the linter before committing Python code.**
  ```bash
  ruff check src/
  ruff format --check src/
  ```
  The linter catches style problems that reviewers would otherwise comment on.

- **Never commit `.env`.**
  The `.env` file contains API keys. It is gitignored. If `git status` shows `.env` in the
  staged files, remove it immediately with `git reset HEAD .env` before committing.

- **Never commit `data/`.** The corpus is ~13 GB. It is gitignored. Notebooks can read from
  `data/` but never write to it during analysis — use `data/external/` for small derived
  artifacts like `corpus_stats.json`.

- **Check `data/external/corpus_stats.json` is committed.** This file is small metadata and
  IS tracked by git. Verify it appears in `git status` (not ignored) before pushing.

- **Keep notebook cells clean.** Before committing a notebook, restart the kernel and run
  all cells top-to-bottom. A notebook that requires running cells out of order is broken.

- **One logical change per commit.** If you fix a bug and add a new feature in the same
  session, commit them separately. This makes the PR easier to review and easier to revert
  if something goes wrong.

- **Rebase onto `main` before opening a PR.**
  ```bash
  git fetch origin
  git rebase origin/main
  ```
  This keeps the history clean and avoids merge conflicts in the PR.
