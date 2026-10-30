"""The structure's own test: it reads every import and fails when one breaks the layering.

The rules (final_plan.md §4), checked over whatever exists so far — a phase that has not
moved its files yet simply has nothing here to check:

    main.py · jobs/            entry points: may import anything
          ↓
    forms/<key>/               the forms
          ↓
    modules/<module>/          business areas: each other only through __init__.py, never in a circle
          ↓
    integrations/daftra/       knows nothing about modules or forms
          ↓
    core/                      knows nothing above it

import-linter can check the levels but not "only through __init__", so this one test does all
three and needs no new tool.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

# Low to high. A file may import its own layer or a lower one, never a higher one.
LAYERS = {"core": 0, "integrations": 1, "modules": 2, "forms": 3, "jobs": 4}
ENTRY_LAYER = 4

# `modules/models.py` imports every module's models, for SQLAlchemy and Alembic: that is its job
MODELS_REGISTRY = "app.modules.models"


def _dotted(path: Path) -> str:
    """app/modules/clients/repo.py -> app.modules.clients.repo (a package -> its own name)."""
    parts = path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path) -> list[tuple[str, int]]:
    """Every `app.…` name this file imports, with the line it is on, relative ones resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    here = _dotted(path).split(".")
    package = here if path.name == "__init__.py" else here[:-1]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.lineno) for alias in node.names if alias.name.startswith("app.")]
        elif isinstance(node, ast.ImportFrom):
            if node.level:                                    # from .. import x
                base = package[: len(package) - node.level + 1]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            if not target.startswith("app"):
                continue
            # `from app.modules.catalog import repo` reaches into catalog's files just as
            # `from app.modules.catalog.repo import …` does, so read the names too — but only
            # those that are files. `from app.modules.catalog import products` names something
            # the `__init__` re-exports, which is the one legal way in.
            found.append((target, node.lineno))
            found += [(f"{target}.{alias.name}", node.lineno) for alias in node.names
                      if alias.name != "*" and _is_file(f"{target}.{alias.name}")]
    return found


def _is_file(dotted: str) -> bool:
    """Whether a dotted name is a module or package of its own, rather than a name inside one."""
    here = APP.parent / Path(*dotted.split("."))
    return here.with_suffix(".py").exists() or (here / "__init__.py").exists()


def _layer(dotted: str) -> int | None:
    """Which layer a name lives in; None for app itself and app.main (an entry point)."""
    parts = dotted.split(".")
    return LAYERS.get(parts[1]) if len(parts) > 1 else None


def _unit(dotted: str) -> str | None:
    """The thing that owns a name: a module, a form, a package. Imports inside one are its own business."""
    parts = dotted.split(".")
    if len(parts) >= 3 and parts[1] in ("modules", "forms", "integrations"):
        return ".".join(parts[:3])
    return ".".join(parts[:2]) if len(parts) >= 2 else None


def _files() -> list[Path]:
    return sorted(
        path for folder in LAYERS for path in (APP / folder).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def test_imports_never_go_up_a_level():
    """core knows nothing of integrations, which knows nothing of modules, and so on."""
    wrong = []
    for path in _files():
        mine = _dotted(path)
        here = _layer(mine)
        if here is None or here == ENTRY_LAYER:              # jobs/ may import anything
            continue
        for target, line in _imports(path):
            theirs = _layer(target)
            if theirs is not None and theirs > here:
                wrong.append(f"{path.relative_to(APP.parent)}:{line}  {mine} imports {target}")
    assert not wrong, "these imports reach up a layer:\n" + "\n".join(wrong)


def test_a_module_is_reached_only_through_its_init():
    """`from app.modules.catalog import products` — never `…catalog.repo`."""
    wrong = []
    for path in _files():
        mine = _dotted(path)
        if mine == MODELS_REGISTRY or _layer(mine) == ENTRY_LAYER:
            continue
        for target, line in _imports(path):
            unit = _unit(target)
            if unit is None or not unit.startswith("app.modules.") or unit == _unit(mine):
                continue
            if target != unit:                               # anything deeper than the package itself
                wrong.append(f"{path.relative_to(APP.parent)}:{line}  {mine} imports {target}, not {unit}")
    assert not wrong, "these imports reach inside another module instead of its __init__:\n" + "\n".join(wrong)


def test_no_two_modules_import_each_other():
    """Not directly, and not round a longer circle."""
    edges: dict[str, set[str]] = {}
    for path in _files():
        mine = _unit(_dotted(path))
        if mine is None or _layer(_dotted(path)) == ENTRY_LAYER or _dotted(path) == MODELS_REGISTRY:
            continue
        for target, _ in _imports(path):
            theirs = _unit(target)
            if theirs and theirs != mine:
                edges.setdefault(mine, set()).add(theirs)

    circles = []
    def walk(unit: str, seen: list[str]):
        for next_unit in sorted(edges.get(unit, ())):
            if next_unit in seen:
                circles.append(" → ".join(seen[seen.index(next_unit):] + [next_unit]))
            elif len(seen) < 12:
                walk(next_unit, seen + [next_unit])

    for unit in sorted(edges):
        walk(unit, [unit])
    assert not circles, "these import in a circle:\n" + "\n".join(sorted(set(circles)))
