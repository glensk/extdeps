# extdeps

A tiny, pure-stdlib, pip/uv-installable Python package that lets CLI tools declare their external dependencies (sibling repo scripts, system executables) as data, resolve them through a fixed chain (env override → `$PATH` → sibling path), and fail loudly with actionable messages and exit code 3 instead of cryptic `FileNotFoundError`s.

Key tools: `extdeps/__init__.py` (public API: `Dep`, `resolve()`, `require()`, `exit_on_missing()`, `MissingExternalDependency`)

Stack: Python ≥3.10, hatchling build | Deps: none (pure stdlib)
