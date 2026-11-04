"""Behavior matrix for the extdeps engine — every consumer relies on these
semantics, so they are pinned here once instead of re-tested per repo."""

# pylint: disable=missing-function-docstring  # test names ARE the docstrings

import os
import stat
from pathlib import Path

import pytest

import extdeps
from extdeps import (
    Dep,
    MissingExternalDependency,
    exit_on_missing,
    is_noninteractive,
    require,
    resolve,
)


def _make_executable(path: Path, help_text: str = "usage: tool") -> Path:
    path.write_text(f'#!/bin/sh\necho "{help_text}"\n')
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


# --- env override -----------------------------------------------------------


def test_env_override_hit_wins_over_path(tmp_path, monkeypatch):
    target = _make_executable(tmp_path / "mytool")
    monkeypatch.setenv("MYTOOL_BIN", str(target))
    # command would also resolve via $PATH — the override must win
    dep = Dep(name="mytool", install_hint="x", env="MYTOOL_BIN", command="sh")
    assert resolve(dep) == str(target)


def test_env_override_set_but_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTOOL_BIN", str(tmp_path / "nope"))
    # a set-but-broken override must NOT silently fall through to $PATH
    dep = Dep(name="mytool", install_hint="x", env="MYTOOL_BIN", command="sh")
    assert resolve(dep) is None


def test_env_override_expands_user(tmp_path, monkeypatch):
    target = _make_executable(tmp_path / "mytool")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MYTOOL_BIN", "~/mytool")
    dep = Dep(name="mytool", install_hint="x", env="MYTOOL_BIN")
    assert resolve(dep) == str(target)


# --- $PATH ------------------------------------------------------------------


def test_path_resolution(tmp_path, monkeypatch):
    target = _make_executable(tmp_path / "mytool")
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    dep = Dep(name="mytool", install_hint="x", command="mytool")
    assert resolve(dep) == str(target)


# --- siblings / root --------------------------------------------------------


def test_sibling_resolution_relative_to_root(tmp_path):
    repo = tmp_path / "category" / "consumer"
    repo.mkdir(parents=True)
    dep_repo = tmp_path / "category" / "other-repo" / "bin"
    dep_repo.mkdir(parents=True)
    target = _make_executable(dep_repo / "tool.py")
    dep = Dep(
        name="tool.py",
        install_hint="x",
        siblings=("../other-repo/bin/tool.py",),
        root=repo,
    )
    assert resolve(dep) == str(target.resolve())


def test_sibling_first_existing_candidate_wins(tmp_path):
    (tmp_path / "b").mkdir()
    target = _make_executable(tmp_path / "b" / "tool")
    dep = Dep(
        name="tool",
        install_hint="x",
        siblings=("a/tool", "b/tool"),
        root=tmp_path,
    )
    assert resolve(dep) == str(target.resolve())


def test_absolute_sibling_works_without_root(tmp_path):
    target = _make_executable(tmp_path / "tool")
    dep = Dep(name="tool", install_hint="x", siblings=(str(target),))
    assert resolve(dep) == str(target.resolve())


def test_relative_sibling_without_root_raises_at_construction():
    with pytest.raises(ValueError, match="need root="):
        Dep(name="tool", install_hint="x", siblings=("../other/tool",))


def _make_plain_file(path: Path) -> Path:
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(0o644)
    return path


# --- executability (command deps) ---------------------------------------------


def test_command_dep_non_executable_sibling_not_resolved(tmp_path):
    _make_plain_file(tmp_path / "tool")
    dep = Dep(
        name="tool",
        install_hint="x",
        command="definitely-not-a-real-command-xyz",
        siblings=("tool",),
        root=tmp_path,
    )
    assert resolve(dep) is None


def test_command_dep_non_executable_sibling_falls_through_to_next(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _make_plain_file(tmp_path / "a" / "tool")
    target = _make_executable(tmp_path / "b" / "tool")
    dep = Dep(
        name="tool",
        install_hint="x",
        command="definitely-not-a-real-command-xyz",
        siblings=("a/tool", "b/tool"),
        root=tmp_path,
    )
    assert resolve(dep) == str(target.resolve())


def test_command_dep_executable_sibling_resolved(tmp_path):
    target = _make_executable(tmp_path / "tool")
    dep = Dep(
        name="tool",
        install_hint="x",
        command="definitely-not-a-real-command-xyz",
        siblings=("tool",),
        root=tmp_path,
    )
    assert resolve(dep) == str(target.resolve())


def test_command_dep_non_executable_env_override_returns_none(tmp_path, monkeypatch):
    target = _make_plain_file(tmp_path / "mytool")
    monkeypatch.setenv("MYTOOL_BIN", str(target))
    # treated like a set-but-missing override: no silent fall-through to $PATH
    dep = Dep(name="mytool", install_hint="x", env="MYTOOL_BIN", command="sh")
    assert resolve(dep) is None


def test_command_dep_non_executable_raises_on_require(tmp_path):
    _make_plain_file(tmp_path / "tool")
    dep = Dep(
        name="tool",
        install_hint="x",
        command="definitely-not-a-real-command-xyz",
        siblings=("tool",),
        root=tmp_path,
    )
    with pytest.raises(MissingExternalDependency):
        require(dep, needed_for="--x")


def test_non_command_dep_data_file_resolves_without_exec_bit(tmp_path):
    target = _make_plain_file(tmp_path / "data.json")
    dep = Dep(name="data", install_hint="x", siblings=("data.json",), root=tmp_path)
    assert resolve(dep) == str(target.resolve())


def test_non_command_dep_env_override_resolves_without_exec_bit(tmp_path, monkeypatch):
    target = _make_plain_file(tmp_path / "data.json")
    monkeypatch.setenv("DATA_PATH", str(target))
    dep = Dep(name="data", install_hint="x", env="DATA_PATH")
    assert resolve(dep) == str(target)


def test_non_command_dep_directory_resolves(tmp_path):
    (tmp_path / "other-repo").mkdir()
    dep = Dep(name="repo", install_hint="x", siblings=("other-repo",), root=tmp_path)
    assert resolve(dep) == str((tmp_path / "other-repo").resolve())


def test_unresolvable_returns_none(tmp_path):
    dep = Dep(
        name="ghost",
        install_hint="x",
        env="GHOST_BIN",
        command="definitely-not-a-real-command-xyz",
        siblings=("nowhere/ghost",),
        root=tmp_path,
    )
    assert resolve(dep) is None


# --- require / probe / exit-3 boundary ---------------------------------------


def test_require_raises_with_actionable_message(tmp_path):
    dep = Dep(
        name="ghost",
        install_hint="Clone ghost-repo and put it on $PATH.",
        env="GHOST_BIN",
        siblings=("nowhere/ghost",),
        root=tmp_path,
    )
    with pytest.raises(MissingExternalDependency) as exc_info:
        require(dep, needed_for="--some-feature")
    msg = exc_info.value.message()
    assert "ghost" in msg
    assert "--some-feature" in msg
    assert "GHOST_BIN" in msg
    assert "Clone ghost-repo" in msg
    assert MissingExternalDependency.EXIT_CODE == 3


def test_probe_failure_reports_outdated(tmp_path, monkeypatch):
    target = _make_executable(tmp_path / "mytool", help_text="usage: old version")
    monkeypatch.setenv("MYTOOL_BIN", str(target))
    dep = Dep(
        name="mytool",
        install_hint="x",
        env="MYTOOL_BIN",
        requires_subcommand="newfeature",
    )
    with pytest.raises(MissingExternalDependency, match="outdated"):
        require(dep, needed_for="--flag")


def test_probe_timeout_is_reported_as_a_timeout_not_outdated(tmp_path, monkeypatch):
    target = tmp_path / "slowtool"
    target.write_text("#!/bin/sh\nexec sleep 5\n")
    target.chmod(target.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("SLOWTOOL_BIN", str(target))
    monkeypatch.setattr(extdeps, "PROBE_TIMEOUT_S", 0.2)
    dep = Dep(
        name="slowtool",
        install_hint="x",
        env="SLOWTOOL_BIN",
        requires_subcommand="prompt",
    )
    with pytest.raises(MissingExternalDependency) as exc_info:
        require(dep, needed_for="--flag")
    msg = exc_info.value.message()
    assert "probe timed out" in msg
    assert "lacks the required" not in msg
    assert "outdated" not in msg


def test_probe_success(tmp_path, monkeypatch):
    target = _make_executable(tmp_path / "mytool", help_text="usage: ... newfeature")
    monkeypatch.setenv("MYTOOL_BIN", str(target))
    dep = Dep(
        name="mytool",
        install_hint="x",
        env="MYTOOL_BIN",
        requires_subcommand="newfeature",
    )
    assert require(dep, needed_for="--flag") == str(target)


def test_interactive_dep_refused_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "1")
    dep = Dep(name="gui-tool", install_hint="x", interactive=True)
    with pytest.raises(MissingExternalDependency, match="no-TTY"):
        require(dep, needed_for="--login")


def test_exit_on_missing_exits_3(capsys):
    dep = Dep(name="ghost", install_hint="get it")
    exc = MissingExternalDependency(dep, needed_for="--x")
    with pytest.raises(SystemExit) as exit_info:
        exit_on_missing(exc)
    assert exit_info.value.code == 3
    assert "ghost" in capsys.readouterr().err


# --- CI guard ----------------------------------------------------------------


def test_is_noninteractive_under_ci(monkeypatch):
    monkeypatch.setenv("CI", "1")
    assert is_noninteractive() is True
