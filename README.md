# extdeps

Declare → resolve → fail-loud registry for **external tool dependencies**: the
scripts of sibling repos and the system executables your CLI tool shells out to
(`browser.py`, `age`, `op`, `glab`, …). Pure standard library, zero runtime
dependencies.

A consumer repo declares each dependency once, as data it owns, then resolves it
through a fixed chain — instead of scattering bare `shutil.which()` calls and
hard-coded sibling paths that fail as cryptic `FileNotFoundError`s deep inside a
subprocess call.

## Install

```commands
uv add "extdeps @ git+https://github.com/glensk/extdeps"
# or
pip install "extdeps @ git+https://github.com/glensk/extdeps"
```

Or in a PEP 723 single-file script:

```python
# /// script
# dependencies = ["extdeps @ git+https://github.com/glensk/extdeps"]
# ///
```

## Usage

```python
from pathlib import Path

from extdeps import Dep, MissingExternalDependency, exit_on_missing, require, resolve

REPO_ROOT = Path(__file__).resolve().parent  # base for relative sibling paths

EXTERNAL_DEPS = {
    "browser.py": Dep(
        name="browser.py",
        command="browser.py",                 # $PATH lookup
        env="BROWSER_PY_BIN",                 # per-user override (document in .env.example)
        siblings=("../browser-login/bin/browser.py",),  # side-by-side clone layout
        root=REPO_ROOT,
        requires_subcommand="login",          # capability probe: must appear in `-h`
        install_hint="Clone browser-login and put its bin/ on $PATH.",
    ),
}

def download_bills():
    # hard requirement of THIS feature — resolves or raises with a useful message
    browser = require(EXTERNAL_DEPS["browser.py"], needed_for="--download-bills")
    ...

def enrich_output():
    # soft dependency — degrade gracefully
    browser = resolve(EXTERNAL_DEPS["browser.py"])
    if browser is None:
        return  # feature skipped, tool still works

if __name__ == "__main__":
    try:
        main()
    except MissingExternalDependency as exc:
        exit_on_missing(exc)  # standardized message, exit code 3
```

## Semantics

**Resolution chain** (`resolve()` returns the first hit, else `None`):

1. **Env override** — `Dep.env` (e.g. `BROWSER_PY_BIN=<path>`). A *set but
   broken* override returns `None` rather than silently falling through.
2. **`$PATH`** — `shutil.which(Dep.command)`.
3. **Siblings** — candidate paths, relative to `Dep.root` (the consuming repo's
   root; an installed package can't derive it, so the registry passes it).
   Declaring a relative sibling without `root` raises at construction time.

**Fail loud, fail useful**: `require()` raises `MissingExternalDependency`;
`exit_on_missing()` at the CLI boundary prints *what's missing, which feature
needs it, the override var, and how to get it*, then exits with code **3** —
distinct from ordinary errors so callers and CI can tell "unmet dependency"
apart.

**Capability probe**: for in-house deps, `requires_subcommand` makes `require()`
check that the subcommand appears in `<dep> -h` — an *outdated* copy fails
clearly instead of mid-run (existence ≠ compatibility).

**CI / headless guard**: deps marked `interactive=True` (browser windows,
Touch ID, `input()`) are refused by `require()` when `$CI` is set or stdin has
no TTY — fail fast, never hang.

**Capability-scoped checks**: resolve/require only for the subcommand the user
actually invoked, after argument parsing — never at import, never before `-h`.

## Development

```commands
uv sync
uv run pytest
```

## License

Apache-2.0
