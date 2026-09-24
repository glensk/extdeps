# Reusable Python CI

`.github/workflows/python-ci.yml` is a reusable (`workflow_call`) workflow for
the owner's Python repos. extdeps is its first caller (`.github/workflows/ci.yml`).

It runs two jobs:

- **lint** (always on `ubuntu-latest`): `uvx ruff@<ruff-version> check` and
  `uvx ruff@<ruff-version> format --check`, optional shellcheck, and a gitleaks
  secret scan of the checkout.
- **test** (one job per Python version, on `os`): install, test, and optional mypy.

When a step fails, the job summary lists which steps failed.

## Caller snippet

Put this in `.github/workflows/ci.yml` in the calling repo:

```yaml
name: ci
on: { push: { branches: [main] }, pull_request: {}, schedule: [{ cron: "17 5 * * 1" }] }
permissions: { contents: read }
jobs:
  ci: { uses: glensk/extdeps/.github/workflows/python-ci.yml@<tag-or-sha> }
```

Pin `@<tag-or-sha>` to a release tag (or a full commit SHA). Don't use `@main`:
a change to this workflow would then reach every caller without review. Pass
inputs with `with:`:

```yaml
jobs:
  ci:
    uses: glensk/extdeps/.github/workflows/python-ci.yml@<tag-or-sha>
    with:
      python-versions: '["3.12","3.13"]'
      mypy: uv run --frozen mypy .
      shellcheck: true
```

## Inputs

| Input | Type | Default | Meaning |
|---|---|---|---|
| `python-versions` | string (JSON list) | `["3.11","3.12"]` | Test matrix |
| `os` | string | `ubuntu-latest` | Runner for the test job (e.g. `macos-latest`); lint always runs on Ubuntu |
| `working-directory` | string | `.` | Directory holding the Python project |
| `install` | string | *(empty)* | Install command. Empty: `uv sync --frozen --all-groups`, or `uv sync --all-groups` if there is no `uv.lock`. Repos with only `requirements.txt` pass their own, e.g. `uv venv && uv pip install -r requirements.txt` |
| `test` | string | *(empty)* | Test command. Empty: `uv run --frozen pytest -q` (without `--frozen` if there is no `uv.lock`) |
| `ruff-version` | string | `0.16.2` | ruff version, run via `uvx` |
| `ruff-args` | string | *(empty)* | Arguments for `ruff check`. Empty: the repo's own ruff config, or, if the repo has none, the owner fallback `--isolated --select E,F,W,I --ignore E501 --target-version py310`. `ruff format --check` always uses the repo config, or `--isolated` if there is none |
| `mypy` | string | *(empty = skip)* | Full mypy command, run after install (e.g. `uv run --frozen mypy .`) |
| `shellcheck` | boolean | `false` | shellcheck every tracked `*.sh` file |
| `gitleaks` | boolean | `true` | gitleaks secret scan of the checkout (a checksum-pinned release binary) |

A repo "has ruff config" when it has `ruff.toml`, `.ruff.toml`, or a
`[tool.ruff…]` table in `pyproject.toml` inside `working-directory`.

Command inputs are passed to the scripts through `env:` and run with `eval`.
They are trusted in the same way as the caller's own workflow file.

## How a private repo opts in

1. Add the caller snippet above as `.github/workflows/ci.yml`. No secrets are
   needed, and `permissions: contents: read` is enough.
2. Nothing needs to change in extdeps: GitHub lets any repository call a
   reusable workflow from a **public** repository.
3. Add `with:` inputs the repo needs (see below), push, and check the first run.
4. Remove the scheduled LLM check-up for that repo. The weekly `schedule`
   trigger replaces it.

Typical inputs for different kinds of repo:

- uv project with a lockfile and pytest: no inputs needed.
- No tests yet: `test: "true"`.
- Typed code: `mypy: uv run --frozen mypy .`
- Shell scripts: `shellcheck: true`
- macOS-only tools: `os: macos-latest`
- Monorepo subfolder: `working-directory: path/to/pkg`
