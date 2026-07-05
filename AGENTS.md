# AGENTS.md

Conventions for AI coding agents (and humans) working in this repo.

## What this is

`extdeps` — a tiny, pure-stdlib, pip/uv-installable package: declare → resolve →
fail-loud registry for external tool dependencies (sibling repos' scripts,
system executables). Consumer repos depend on it via
`extdeps @ git+https://github.com/glensk/extdeps` and keep their own
`EXTERNAL_DEPS` registry (data) next to their code. See `README.md`.

## Environment

- Python projects use **`uv`** (preferred over Homebrew/system installs):
  `uv sync` to install, `uv run <cmd>` to run, `uv tool install <tool>` for CLIs.
- No runtime dependencies — the package must stay pure standard library.
- Secrets live in `.env` (never commit). See `.env.example` (this library reads none).

## Build / test / lint

- Tests: `uv run pytest`
- Python: `ruff format . && ruff check . && mypy . && pylint extdeps tests`
- Pre-commit: `pre-commit run --all-files` (gitleaks secret scan)

## Conventions

- **API stability**: `Dep`, `resolve()`, `require()`, `MissingExternalDependency`
  (exit code 3), `exit_on_missing()`, `is_noninteractive()` are the public
  contract — multiple consumer repos float on `main`, so breaking changes need a
  version bump + tag, and consumers should then pin `@<tag>`.
- Behavior changes must be reflected in `tests/test_extdeps.py` (the single
  behavior matrix consumers rely on instead of per-repo tests).

## Where things live

- Design / roadmap: PLAN.md (if present)
- Private/local notes: CLAUDE.local.md (gitignored); CLAUDE.md is a gitignored
  shim that imports this file.
