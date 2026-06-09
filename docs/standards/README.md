# Standards

This directory holds the project's working standards. They define **how we work**: how the repo is organized, how code is written, how tests are structured, how documentation flows, how secrets are handled, and how the team coordinates via git.

Standards are referenced from the root [`CLAUDE.md`](../../CLAUDE.md) so they are loaded into Claude's working context when relevant to a task.

## Index

| Standard | What it covers | Read when |
|----------|---------------|-----------|
| [Documentation Standard](./documentation_standard.md) | Where docs live, naming conventions, markdown style, roadmap and phase doc patterns, loose-ends convention | Adding or modifying any documentation |
| [Repository Layout Standard](./repo_layout_standard.md) | Top-level directory structure and what each folder holds | Adding a new file or deciding where something belongs |
| [Python Code Standard](./python_code_standard.md) | Style (PEP 8 + ruff), type hints, docstrings, naming, module organization, error handling | Writing or modifying Python code |
| [Testing Standard](./testing_standard.md) | pytest conventions, test placement, naming, markers, what to test, coverage targets | Writing tests, deciding test scope, running the suite |
| [Git Workflow Standard](./git_workflow_standard.md) | Branch strategy, commit message format, rebasing, PR conventions, authorship rules | Committing, branching, opening or reviewing PRs |
| [Credential Handling Standard](./credential_handling_standard.md) | How API keys are stored in `.env`, loaded in code, kept out of git, rotated on leak | Adding a new API integration or touching anything secret |
| [Logging Standard](./logging_standard.md) | Python `logging` module conventions, levels, structured JSON format, log file destination | Adding logging to a new module or debugging a pipeline run |
| [Environment Standard](./environment_standard.md) | venv + Docker hybrid setup, no-sudo discipline, project-local model caches, bootstrap workflow | Setting up the project for the first time, adding a dependency, debugging an install problem |

## How standards work in this repo

- **Standards are binding.** If a PR violates a standard, the standard wins — fix the PR, or update the standard explicitly and get team agreement.
- **Standards are linked, not duplicated.** When CLAUDE.md, the README, or a phase doc references a rule, it links here rather than restating it.
- **Standards evolve with intent.** Changing a standard is a deliberate act. The change goes through a normal PR, the commit message explains why, and downstream references (CLAUDE.md, related docs) are updated in the same PR.

## Adding a new standard

1. Pick a clear, specific topic. One concept per file.
2. Follow the structure of the existing standards (status, scope, the rules, examples).
3. Add an entry to the table above.
4. Link it from `CLAUDE.md` under the relevant section.
5. Mention it in the PR description so reviewers see the new rule.
