# Teammate Onboarding — Telugu OCR Project

Welcome, Rauf. This doc gets you from "I just got the email" to writing
code on the project, fast.

You will be doing your work on a Linux server that Eric has set up for
this project (we call it "the project VM"). You will connect to it from
your Windows laptop using VS Code's Remote-SSH feature. Once you are
connected, your VS Code editor on Windows is editing files that live on
the Linux server — exactly as if Eric and you were working on the same
machine.

**Please reach out as often as you need to.** Email, Teams, text —
whatever works. Quick questions are welcome; staying stuck silently is
not. Eric is happy to walk through anything in this repo with you.

---

## What this project is

We are building an end-to-end pipeline that extracts Unicode text from
scanned Telugu book images using vision-capable large language models.
The pipeline includes image preprocessing, OCR with multiple models,
and a validation framework that scores OCR quality without needing
manual ground-truth annotation.

This is a graded deliverable for CSCI/DASC 6020 (Machine Learning,
Summer 2026) at East Carolina University. The deadline is
**June 25, 2026 (Thursday, midnight)**. Full project details are in
the root [README.md](../../README.md).

---

## Step 1 — Generate an SSH key on your Windows laptop

SSH stands for "Secure Shell." It is the standard way to connect to a
Linux server over the network. It works using a **pair of keys**: a
private key (which never leaves your laptop) and a public key (which
the server is told to trust). When you connect, the server checks that
the public key on its side matches the private key on your side. No
password to type, no password to forget.

You only ever do this once per laptop. After this, every server you
need to access can be told to trust the same key.

### Check if you already have a key

Open **PowerShell** (Start menu → type `PowerShell` → click "Windows
PowerShell"). Run:

```powershell
ls ~\.ssh\
```

If you see a file called `id_ed25519.pub` or `id_rsa.pub`, you already
have a key. Skip to Step 2.

If you see "Cannot find path..." or no `.pub` file, you do not have a
key yet. Continue below.

### Make a key

In PowerShell, run:

```powershell
ssh-keygen -t ed25519 -C "rauf"
```

The `-t ed25519` part picks a modern, strong key type. The `-C "rauf"`
part is just a label so you can recognize the key later — it has no
security meaning.

You will be asked three questions:

1. **"Enter file in which to save the key"** — press Enter to accept
   the default location (`C:\Users\<your-name>\.ssh\id_ed25519`).
2. **"Enter passphrase"** — press Enter for no passphrase. (A passphrase
   adds an extra layer of security, but for a class project on a
   private server it is not needed.)
3. **"Enter same passphrase again"** — press Enter again.

When it finishes, you will have two files:

- `C:\Users\<your-name>\.ssh\id_ed25519` — **the private key, NEVER
  share this with anyone, ever**.
- `C:\Users\<your-name>\.ssh\id_ed25519.pub` — the public key, this is
  what you send to Eric.

---

## Step 2 — Send your public key to Eric

In PowerShell, display the contents of your public key:

```powershell
cat ~\.ssh\id_ed25519.pub
```

(Or `cat ~\.ssh\id_rsa.pub` if your existing key was the older RSA type.)

You will see a single line that looks like:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabcd1234...xyz= rauf
```

**Select that entire line, copy it, and paste it into a message to
Eric** (Teams, email, whatever). It is safe to share — that is what the
"public" in "public key" means. The whole reason it works is the
matching private key never leaves your machine.

Wait for Eric to confirm he has added it to the VM (should take 5
minutes). Then he will send you back the SSH connection details for
Step 3.

---

## Step 3 — Install the Remote-SSH extension in VS Code

You should already have VS Code installed on Windows. If not, install
it from https://code.visualstudio.com/ first.

Remote-SSH is a VS Code extension that lets the editor on your Windows
laptop work on files that live on a remote Linux server, as if they
were local. It is built and maintained by Microsoft. It is the
standard tool professional developers use for this exact scenario.

1. Open VS Code.
2. Click the **Extensions** icon in the left sidebar (it looks like
   four little squares).
3. In the search box at the top, type: `Remote - SSH`
4. Find the extension named **"Remote - SSH"** with the publisher
   **Microsoft**.
5. Click **Install**.

After install, you will see a small green icon in the **bottom-left
corner** of VS Code. That icon is how you start a remote session.

---

## Step 4 — Connect to the project VM

Eric will send you a one-line SSH command that looks like:

```
ssh rauf@some-hostname.example.com -p 22
```

To use it inside VS Code:

1. In VS Code, click the **green icon in the bottom-left corner**.
2. Choose **"Connect to Host..."** from the menu that appears.
3. Choose **"+ Add New SSH Host..."**.
4. Paste the entire `ssh rauf@...` command Eric sent and press Enter.
5. When asked which SSH config file to update, choose the first option
   (the one in your user folder, ending in `\.ssh\config`).
6. A small popup appears in the bottom-right corner — click
   **"Connect"**.

The first time you connect, VS Code will ask **"Are you sure you want
to continue connecting?"** — type `yes` and press Enter. That is your
laptop's first time seeing this server, so SSH wants you to confirm.
After this, it will not ask again.

A new VS Code window opens. The bottom-left corner should now say
something like **"SSH: some-hostname"**. You are now editing on the
Linux VM. Everything from here on is done in that VS Code window.

---

## Step 5 — Clone the project and set up your environment

The VM has Python, Git, and Docker pre-installed but the project repo
itself is not on it yet. In this step you clone the repo, install the
project's dependencies, and run the test suite to confirm everything
works. After this step you have a fully working development environment.

### Open the workspace in VS Code

1. In your remote VS Code window, choose **File → Open Folder...**
2. Type `/home/rauf/Repos` and press Enter. (The folder exists but is
   empty — that is fine; we are about to fill it.)
3. VS Code may ask **"Do you trust the authors of the files in this
   folder?"** — click **"Yes, I trust the authors."**
4. Open the integrated terminal: **View → Terminal** (or press
   **Ctrl+`** — the backtick key, top-left of the keyboard).

Your terminal prompt should look like `rauf@rauf-dev:~/Repos$`. If it
shows a different path, run `cd ~/Repos` first.

### Run these commands one at a time

Do not paste the whole block at once. Run each command, wait for it to
finish, glance at the output. If something prints a red error, **stop
and message Eric** before going further.

```bash
# 1. Clone the project repo. The repo is public, so no GitHub login
#    is needed for this command. After it finishes you will have a
#    new folder at ~/Repos/ml-class-project/ containing all the code.
#    IMPORTANT: the URL must start with "https://" — if you paste in
#    one that starts with "git@github.com:" the clone will fail with
#    "Permission denied". The SSH form (the "git@" version) would
#    require setting up SSH keys for GitHub; our HTTPS form works
#    without any setup because the repo is public.
git clone https://github.com/Pumapumapumas/ml-class-project.git
cd ml-class-project

# 2. Run the bootstrap script. This script does a LOT in one go:
#    creates a self-contained Python environment for the project,
#    installs every Python library we need, and builds the Docker
#    image that runs Tesseract. Expect 3-5 minutes; the first run
#    is the slowest because it pulls things from the internet.
scripts/setup_env.sh

# 3. Activate the project's Python environment. After this, any
#    "python" or "pip" command uses the project's private environment
#    instead of system Python. You will need to run this every time
#    you open a new terminal for this project. You can tell it
#    worked because the prompt now starts with "(.venv)".
source .venv/bin/activate

# 4. Make your private credentials file by copying the template.
#    Then open .env in VS Code (click it in the file explorer on the
#    left side panel) and paste in your Gemini API key. The .env
#    file holds secrets — it is automatically ignored by git, so you
#    cannot accidentally commit it. See the "API keys" section of
#    the root README.md for where to get a free Gemini key. Ping
#    Eric if you get stuck on this one.
cp .env.example .env

# 5. Download a small sample of the Telugu book images (~500 MB,
#    5 books). This pulls from HuggingFace and takes 1-2 minutes.
python scripts/download_dataset.py --subset 5

# 6. Run the fast test suite. All tests should pass — this is how
#    we know your environment is healthy end-to-end.
pytest -m "not slow and not api"
```

If `pytest` ends with something like `29 passed`, **you are done**.
You have a working development environment and you are ready to start
contributing. Move on to "What you will be working on" below.

If something fails, copy the error output and message Eric. Do not
spend more than a few minutes trying to fix it yourself — environment
issues are Eric's responsibility on the VM.

### About Jupyter notebooks

Some of your tasks involve creating and running Jupyter notebooks (`.ipynb`
files). You do NOT need to start any `jupyter lab` server. VS Code handles
notebooks natively: when you open a `.ipynb` file, VS Code runs the kernel
on the VM through your existing SSH connection and shows the notebook UI
right inside the editor. No browser, no separate server, no public URL.

---

## What you will be working on

The project is organized into five phases. Two documents describe the
plan:

- **[`docs/development/roadmap.md`](../development/roadmap.md)** — the
  high-level view. One paragraph per phase, status header, ownership
  table. Read this first so you understand the shape of the whole
  project.

- **Phase docs** (`docs/development/phase_N_*.md`) — one file per phase
  with detailed task lists, completion criteria, and open questions.
  These are your working documents while you are inside a phase.

The roadmap has a full ownership table. Your tasks at a glance:

| Phase | Your tasks |
|-------|-----------|
| 1 | Corpus statistics notebook, plots and tables |
| 2 | Deskew module, binarize module, before/after visualization notebook |
| 3 | Tesseract adapter (Surya was cut from scope) |
| 4 | Classical CER/WER scoring module and CLI |
| 5 | Error categorization tables and plots, figures for the report, slide visual content |

Eric owns the prose, prompt engineering, pipeline interfaces, and
orchestration. You own the numerical work, visualizations, and the
components listed above.

**The plan is deliberate but not rigid.** When something deviates from
the plan, document it in
[`docs/development/loose_ends.md`](../development/loose_ends.md). That
file is the single place for deferred items, open questions, and
discovered problems.

---

## Your first PR

Build the corpus statistics notebook: **Phase 1, Task 2** in
[`docs/development/phase_1_corpus_characterization.md`](../development/phase_1_corpus_characterization.md).

The data this notebook depends on already exists. Eric has finished
Phase 1 Task 1 and committed the inventory CSV to the repo, so after
your clone in Step 5 you will already have it at
`data/external/corpus_inventory.csv`.

### Step-by-step

**1. Create your branch**

Use your initials. For example:

```bash
git checkout main
git pull
git checkout -b rauf/01-corpus-stats
```

The branch naming convention is `<your-initials>/<short-description>`.
See [Git Workflow Standard](../standards/git_workflow_standard.md) for
the full convention.

**2. Create the notebook**

Create a new notebook at this exact path:

```
notebooks/01_corpus_characterization.ipynb
```

VS Code can create and run Jupyter notebooks directly. **File → New
File → Jupyter Notebook**, then save it to that path.

**3. What the notebook must produce**

The notebook loads `data/external/corpus_inventory.csv` and computes:

- Image dimension distribution (histogram of width × height)
- DPI estimate (if available in EXIF or estimated from image dimensions)
- Mean and median page text length in characters
- File-size distribution (proxy for scan quality variance)

Plus a JSON artifact at `data/external/corpus_stats.json` with the
headline numbers. Example structure:

```json
{
  "total_books": 5,
  "total_pages": 415,
  "median_image_width_px": 1500,
  "median_image_height_px": 2155,
  "mean_text_length_chars": 1823,
  "median_text_length_chars": 1712,
  "median_file_size_bytes": 412800
}
```

The exact field names are up to you — just make them clear and
consistent.

**4. Open a draft PR early**

You do not need to finish before opening a Pull Request. Open it as a
draft as soon as the notebook exists with any content. This lets Eric
see your progress and give early feedback.

```bash
git add notebooks/01_corpus_characterization.ipynb data/external/corpus_stats.json
git commit -m "feat(notebooks): add corpus characterization notebook with stats"
git push -u origin rauf/01-corpus-stats
# Then open the Pull Request on GitHub and mark it as Draft.
```

---

## Coding standards

The `docs/standards/` directory has one file per topic. You do not need
to read them all now — read the relevant one when a question comes up.

| Standard | Read when |
|----------|-----------|
| [Documentation Standard](../standards/documentation_standard.md) | Adding or modifying any doc file |
| [Python Code Standard](../standards/python_code_standard.md) | Writing Python code |
| [Testing Standard](../standards/testing_standard.md) | Writing tests |
| [Git Workflow Standard](../standards/git_workflow_standard.md) | Committing, branching, opening or reviewing a PR |
| [Credential Handling Standard](../standards/credential_handling_standard.md) | Adding a new API key or touching `.env` |
| [Logging Standard](../standards/logging_standard.md) | Adding logging to a script |
| [Environment Standard](../standards/environment_standard.md) | Adding a Python dependency |
| [Repository Layout Standard](../standards/repo_layout_standard.md) | Deciding where a new file belongs |

The index is at [`docs/standards/README.md`](../standards/README.md).

---

## Git workflow

### Branch names

Format: `<your-initials>/<short-description>` — e.g., `rauf/01-corpus-stats`.

Keep branches short-lived. Finish the work, open a PR, delete the
branch after merge.

### Commit messages

We use **conventional commit format**: `<type>(<scope>): <short summary>`

```bash
feat(notebooks): add corpus statistics histogram plots
fix(preprocessing): handle zero-height images
docs(phase1): mark corpus inventory task complete
test(preprocessing): add edge case for all-white input image
chore(deps): pin matplotlib version in requirements.txt
```

### No AI attribution in commits

**Do not add "Co-Authored-By: Claude" or similar tags to commit
messages.** This is a graded deliverable inspected by the instructor.
AI tooling use is disclosed in the final report's methodology section
— that is the correct place. Commit history records human authorship
only.

---

## Asking for help

Eric is the project lead. When you are stuck, contact Eric directly —
Teams, email, or whatever channel you both use.

**Do not stay stuck for hours.** A short message to Eric saves both of
you time:

> "I am stuck on X. I tried Y and got error Z. Can you help?"

**Open a draft PR early.** A draft PR shows Eric your current state:
what files exist, what the notebook contains so far, what errors you
are seeing. This is often better than a long message describing the
problem.

---

## Practical tips

- **Activate the venv every time you open a new terminal.** Without
  it, `python` points at the wrong interpreter.
  ```bash
  source .venv/bin/activate
  ```

- **Run the fast tests before every push.** If something breaks,
  better to find it before Eric sees it in the PR.
  ```bash
  pytest -m "not slow and not api"
  ```

- **Run the linter before committing Python code.** It catches style
  problems that reviewers would otherwise comment on.
  ```bash
  ruff check src/
  ruff format --check src/
  ```

- **Never commit `.env`.** It contains API keys. It is gitignored. If
  `git status` shows `.env` in the staged files, remove it immediately
  with `git restore --staged .env` before committing.

- **Never commit `data/`.** Same reason — too large, regenerated by
  scripts. Small derived files at the root of `data/external/` (CSV
  metadata, JSON stats) ARE tracked; check `git status` to see what
  git decided to include.

- **Keep notebook cells clean.** Before committing a notebook, restart
  the kernel and run all cells top-to-bottom. A notebook that requires
  running cells out of order is broken.

- **Rebase onto `main` before opening a PR.** Keeps the history clean
  and avoids merge conflicts.
  ```bash
  git fetch origin
  git rebase origin/main
  ```
