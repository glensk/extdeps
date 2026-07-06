# extdeps

## Purpose

`extdeps` provides a declare → resolve → fail-loud registry for external tool dependencies that CLI tools shell out to — sibling repo scripts (`browser.py`, `nocodb.py`) and system executables (`age`, `op`, `glab`). Consumer repos declare each dependency once as a `Dep` dataclass in their own `EXTERNAL_DEPS` dict, then resolve through a fixed chain (env override → `$PATH` → relative sibling path) instead of scattering bare `shutil.which()` calls and hard-coded paths. When a dependency is missing, `require()` raises `MissingExternalDependency` with an actionable message (what's missing, which feature needs it, how to install), and `exit_on_missing()` exits with code 3 so callers and CI can distinguish unmet dependencies from ordinary errors.

## Key Capabilities

- **Resolution chain**: env var override → `$PATH` lookup → sibling-relative paths, with broken overrides failing visibly instead of silently falling through
- **Hard vs soft deps**: `require()` raises on missing (for must-have features); `resolve()` returns `None` (for graceful degradation)
- **Capability probe**: `requires_subcommand` checks that an in-house dep actually supports the needed subcommand via `-h` — catches outdated copies before mid-run failures
- **CI / headless guard**: deps marked `interactive=True` are refused when `$CI` is set or stdin has no TTY — fail fast, never hang
- **Standardized exit**: exit code 3 for missing dependencies, distinct from ordinary errors

## Tech Stack

Python ≥3.10, pure standard library (zero runtime deps), hatchling build backend, pytest for tests

## Key Scripts / Files

| File                    | Purpose                                                                                      |
| :---------------------- | :------------------------------------------------------------------------------------------- |
| `extdeps/__init__.py`   | Entire public API: `Dep` dataclass, `resolve()`, `require()`, `exit_on_missing()`, helpers   |
| `tests/test_extdeps.py` | Single behavior matrix covering resolution, failure modes, CI guards, capability probes       |
| `pyproject.toml`        | Package metadata, build config (hatchling), dev deps (pytest)                                 |
| `.env.example`          | Documents per-user env var overrides for dependency paths                                     |
| `AGENTS.md`             | Public conventions for AI agents and humans: build/test/lint commands, API stability contract  |
