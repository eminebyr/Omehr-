from __future__ import annotations

"""CI architecture guardrails.

Hard boundaries intentionally start small and enforceable:
- web/ may not import src/ directly; UI must call services/.
- web/ may not persist Excel files directly (Workbook.save / DataFrame.to_excel).
Read-only pandas/openpyxl use is temporarily allowed and can be reduced safely.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def violations(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for path in sorted((root / "web").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        rel = path.relative_to(root)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "src" or alias.name.startswith("src."):
                        problems.append(f"{rel}:{node.lineno}: web -> src direct import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "src" or module.startswith("src."):
                    problems.append(f"{rel}:{node.lineno}: web -> src direct import: {module}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"save", "to_excel"}:
                    problems.append(f"{rel}:{node.lineno}: UI persistence call '.{node.func.attr}()' is forbidden")
    return problems


def main() -> int:
    problems = violations()
    if problems:
        print("ARCHITECTURE VIOLATIONS")
        print("\n".join(problems))
        return 1
    print("Architecture boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
