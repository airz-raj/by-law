"""Fail the build if the dependency arrows ever turn outward.

``app/core`` is the pure domain: it must import nothing else from the app
and no framework or I/O library. ``app/api`` must reach adapters only
through ``dependencies.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.paths import APP_ROOT

CORE_MUST_NOT_IMPORT = frozenset(
    {
        "app.api",
        "app.services",
        "app.adapters",
        "app.security",
        "app.observability",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "google",
        "httpx",
        "pypdf",
    }
)

API_MUST_NOT_IMPORT = frozenset({"app.adapters"})

CORE_MUST_NOT_CALL = frozenset({"open", "print", "input"})


def imported_modules(path: Path) -> list[str]:
    """Return every module name *path* imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def offending(path: Path, banned: frozenset[str]) -> list[str]:
    """Return the banned imports *path* makes."""
    return [
        name
        for name in imported_modules(path)
        if any(name == b or name.startswith(f"{b}.") for b in banned)
    ]


def core_files() -> list[Path]:
    return sorted((APP_ROOT / "core").rglob("*.py"))


def api_files() -> list[Path]:
    return sorted(p for p in (APP_ROOT / "api").rglob("*.py") if p.name != "dependencies.py")


def test_the_core_package_is_not_empty() -> None:
    assert core_files()


@pytest.mark.parametrize("path", core_files(), ids=lambda p: p.name)
def test_core_imports_nothing_outward(path: Path) -> None:
    assert not offending(path, CORE_MUST_NOT_IMPORT)


@pytest.mark.parametrize("path", api_files(), ids=lambda p: p.name)
def test_api_reaches_adapters_only_through_dependencies(path: Path) -> None:
    assert not offending(path, API_MUST_NOT_IMPORT)


@pytest.mark.parametrize("path", core_files(), ids=lambda p: p.name)
def test_core_does_no_io(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called & CORE_MUST_NOT_CALL


@pytest.mark.parametrize("path", core_files(), ids=lambda p: p.name)
def test_core_never_reads_the_clock(path: Path) -> None:
    """Callers pass ``today``, so core stays testable at fixed dates."""
    source = path.read_text(encoding="utf-8")
    assert "date.today()" not in source
    assert "datetime.now(" not in source


@pytest.mark.parametrize("path", sorted(APP_ROOT.rglob("*.py")), ids=lambda p: p.name)
def test_no_module_leaves_debug_statements_behind(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for marker in ("TODO", "FIXME", "breakpoint()"):
        assert marker not in source, f"{path.name} contains {marker}"
