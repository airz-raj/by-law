import ast
from pathlib import Path

BANNED_IMPORTS_CORE = {
    "app.api",
    "app.services",
    "app.adapters",
    "app.security",
    "fastapi",
    "pydantic",
    "google",
    "httpx",
    "pypdf",
}

BANNED_IMPORTS_API = {
    "app.adapters",
}

def check_file(path: Path, banned_imports: set[str]) -> list[str]:
    violations = []
    with path.open("r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(path))
        except SyntaxError:
            return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                for banned in banned_imports:
                    if name.name == banned or name.name.startswith(f"{banned}."):
                        violations.append(f"Import of {name.name} is banned in {path}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for banned in banned_imports:
                    if node.module == banned or node.module.startswith(f"{banned}."):
                        violations.append(f"From {node.module} import is banned in {path}")
    return violations

def test_core_architecture():
    core_dir = Path("app/core")
    violations = []
    if core_dir.exists():
        for py_file in core_dir.rglob("*.py"):
            violations.extend(check_file(py_file, BANNED_IMPORTS_CORE))
    
    assert not violations, "\n".join(violations)

def test_api_architecture():
    api_dir = Path("app/api")
    violations = []
    if api_dir.exists():
        for py_file in api_dir.rglob("*.py"):
            # dependencies.py can import adapters
            if py_file.name == "dependencies.py":
                continue
            violations.extend(check_file(py_file, BANNED_IMPORTS_API))
            
    assert not violations, "\n".join(violations)
