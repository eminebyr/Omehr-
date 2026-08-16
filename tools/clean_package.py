"""Remove generated/cache files before producing a distributable ZIP."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SUFFIXES = {".pyc", ".pyo"}

for path in sorted(ROOT.rglob("*"), reverse=True):
    if path.is_dir() and path.name in DIRS:
        shutil.rmtree(path, ignore_errors=True)
    elif path.is_file() and path.suffix.lower() in SUFFIXES:
        path.unlink(missing_ok=True)
