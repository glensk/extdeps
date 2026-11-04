"""External-dependency registry + resolver for CLI tool repos.

A repo that shells out to another repo's script (``browser.py``, ``nocodb.py``)
or a system executable (``age``, ``op``, ``glab``, …) declares each such
dependency as a :class:`Dep` in its own ``EXTERNAL_DEPS`` registry — consumer-
owned data, kept next to the code that uses it — and resolves it through this
package:

  - ``resolve(dep) -> str | None``      — find a path; never raises (degrade/fallback).
  - ``require(dep, needed_for=...) -> str`` — resolve or raise MissingExternalDependency.
  - ``MissingExternalDependency``       — caught at the CLI boundary → message + exit 3.
  - ``exit_on_missing(exc)``            — the standard boundary handler.
  - ``is_noninteractive()``             — True in CI / no-TTY (interactive deps fail fast).

Resolution chain: explicit env override → ``$PATH`` → conventional sibling
path(s) relative to ``Dep.root`` (the consumer's repo root — an installed
package cannot derive it, so the registry passes it explicitly).

Checks are capability-scoped: run them only for the feature the user actually
invoked, after argument parsing — never at import, never before ``-h``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

__version__ = "0.1.0"

__all__ = [
    "Dep",
    "MissingExternalDependency",
    "exit_on_missing",
    "is_noninteractive",
    "require",
    "resolve",
]


class MissingExternalDependency(Exception):
    """A dependency a chosen feature genuinely needs could not be resolved.

    Raised by `require()`, caught at the CLI boundary (`exit_on_missing`) which
    prints a standardized, actionable message and exits with code 3 — distinct
    from ordinary errors so callers / CI can tell "unmet dependency" apart.
    """

    EXIT_CODE = 3

    def __init__(self, dep: "Dep", needed_for: str, detail: str = "") -> None:
        self.dep = dep
        self.needed_for = needed_for
        self.detail = detail
        super().__init__(self.message())

    def message(self) -> str:
        """The standardized, actionable error text printed at the CLI boundary."""
        out = [
            f"❌ Missing dependency '{self.dep.name}' — needed for: {self.needed_for}."
        ]
        if self.detail:
            out.append(f"   {self.detail}")
        if self.dep.env:
            out.append(
                f"   Fix: set {self.dep.env}=<path> in .env (see .env.example), or —"
            )
        out.append(f"   {self.dep.install_hint}")
        return "\n".join(out)


@dataclass(frozen=True)
class Dep:  # pylint: disable=too-many-instance-attributes  # flat config record
    """One external dependency. `name`/`install_hint` are required; the rest tune
    how it is resolved and probed.

    Resolution order (see `resolve`): env override → $PATH → conventional sibling.
    Relative `siblings` entries are resolved against `root` (the consuming repo's
    root directory) — declaring one without `root` is a registry bug and raises
    at construction time.
    """

    name: str  # logical id, e.g. "browser.py"
    install_hint: str  # how to obtain it (clone/brew/uv/pip …)
    env: str = (
        ""  # per-user override var, e.g. "BROWSER_PY_BIN" / "..._ROOT" / "..._PATH"
    )
    command: str = ""  # $PATH command; set = executable dep (candidates need X_OK)
    siblings: tuple[str, ...] = ()  # candidate paths, relative to `root` or absolute
    root: Path | None = None  # base dir for relative siblings (consumer repo root)
    interactive: bool = False  # needs TTY/GUI/Touch-ID → forbidden in CI / no-TTY
    requires_subcommand: str = (
        ""  # in-house capability probe: must appear in `<dep> -h`
    )

    def __post_init__(self) -> None:
        """Reject a registry bug early: relative siblings without a root."""
        if self.root is None and any(
            not Path(os.path.expanduser(rel)).is_absolute() for rel in self.siblings
        ):
            raise ValueError(
                f"Dep '{self.name}': relative sibling paths need root= "
                "(the consuming repo's root directory)."
            )


def is_noninteractive() -> bool:
    """True in CI or without a controlling TTY. Interactive deps must fail fast
    here (never hang waiting for a human, a browser, or Touch ID)."""
    if os.environ.get("CI"):
        return True
    try:
        return not sys.stdin.isatty()
    except (ValueError, OSError):
        return True


def resolve(dep: "Dep") -> str | None:
    """Resolve `dep` to a filesystem path, or None. NEVER raises — use this for
    `degrades` / `preferred_with_fallback` deps and branch on the result.

    Chain: (1) explicit env override → (2) $PATH (`shutil.which`) → (3) a
    conventional sibling candidate (per the side-by-side clone layout).

    A dep with `command` set is an executable: a candidate must also pass
    `os.access(path, os.X_OK)`, else it counts as missing (a non-executable
    override → None; a non-executable sibling → try the next one). Deps without
    `command` (directories, data files) only need to exist.
    """
    override = os.environ.get(dep.env) if dep.env else None
    if override:
        p = Path(os.path.expanduser(override))
        return str(p) if _usable(p, dep) else None
    if dep.command:
        found = shutil.which(dep.command)
        if found:
            return found
    for rel in dep.siblings:
        rel_path = Path(os.path.expanduser(rel))
        cand = rel_path if rel_path.is_absolute() else (dep.root or Path()) / rel_path
        if _usable(cand, dep):
            return str(cand.resolve())
    return None


def _usable(path: Path, dep: "Dep") -> bool:
    """A candidate counts only if it exists — and, for a command dep, is
    executable (a non-executable script would fail at launch, not here)."""
    if not path.exists():
        return False
    return not dep.command or os.access(path, os.X_OK)


#: Seconds the capability probe (`<dep> -h`) may take before it counts as
#: timed out — a slow start is reported as such, never as an outdated tool.
PROBE_TIMEOUT_S: float = 15


def _probe_problem(path: str, dep: "Dep") -> str:
    """Cheap capability probe for in-house deps: the required subcommand must
    appear in `<dep> -h`. ``""`` when it does (or `requires_subcommand` is
    empty), else the detail for `MissingExternalDependency` — a probe that
    timed out or could not start is named as such, so a slow `-h` is never
    misreported as a missing subcommand."""
    if not dep.requires_subcommand:
        return ""
    try:
        res = subprocess.run(  # noqa: S603
            [path, "-h"],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (
            f"found at {path}, but its capability probe `{Path(path).name} -h` "
            f"timed out after {PROBE_TIMEOUT_S:g} s — probe timed out (the "
            f"'{dep.requires_subcommand}' subcommand was not checked); retry, or "
            "check why it starts so slowly."
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (
            f"found at {path}, but its capability probe `{Path(path).name} -h` "
            f"could not run: {exc}"
        )
    if dep.requires_subcommand in (res.stdout + res.stderr):
        return ""
    return (
        f"found at {path}, but it lacks the required "
        f"'{dep.requires_subcommand}' subcommand — likely an outdated version."
    )


def _probe_ok(path: str, dep: "Dep") -> bool:
    """Whether the capability probe passed (see :func:`_probe_problem`)."""
    return not _probe_problem(path, dep)


def require(dep: "Dep", *, needed_for: str) -> str:
    """Resolve `dep` or raise `MissingExternalDependency`. Use for deps a feature
    genuinely REQUIRES. Enforces the interactive→CI guard and the capability probe.
    """
    if dep.interactive and is_noninteractive():
        raise MissingExternalDependency(
            dep,
            needed_for,
            detail="needs an interactive terminal/GUI; refusing in CI / no-TTY.",
        )
    path = resolve(dep)
    if not path:
        raise MissingExternalDependency(dep, needed_for)
    problem = _probe_problem(path, dep)
    if problem:
        raise MissingExternalDependency(dep, needed_for, detail=problem)
    return path


def exit_on_missing(exc: "MissingExternalDependency") -> None:
    """Standard CLI-boundary handler: print the message and exit 3.

    Usage in `__main__` (or wrap `main()`):
        try:
            main()
        except MissingExternalDependency as exc:
            exit_on_missing(exc)
    """
    print(exc.message(), file=sys.stderr)
    sys.exit(MissingExternalDependency.EXIT_CODE)
