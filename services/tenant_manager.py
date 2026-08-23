from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from services.runtime_paths import code_root
from services.settings import input_path

ROOT = code_root()
REGISTRY = ROOT / "tenants.json"


def _code(value: str) -> str:
    import re
    result = re.sub(r"[^A-Z0-9_-]", "", value.strip().upper())
    if not result or result != value.strip().upper():
        raise ValueError("Şirket kodu yalnız A-Z, 0-9, _ ve - içerebilir.")
    return result


def registry() -> dict:
    if not REGISTRY.exists():
        # NOT: kiracı KODU ("OMEHR") canlı veritabanındaki mevcut kayıtların
        # anahtarıdır — kod değiştirilirse mevcut veri "kayıp" görünür.
        # Yalnız görüntü ADI genelleştirildi; kod aynı bırakıldı.
        return {"tenants": {"OMEHR": {"name": "Firma", "active": True}}}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def initialize_tenant(code: str, name: str = "") -> Path:
    code = _code(code)
    target = ROOT / "tenants" / code
    for folder in ("input", "output", "data", "logs", "archive", "backup", "reference", "assets"):
        (target / folder).mkdir(parents=True, exist_ok=True)
    copies = [
        (input_path(ROOT), input_path(target)),
        (ROOT / "reference" / "KONTROL_NORM_KADRO_24_07_2026.xlsx", target / "reference" / "KONTROL_NORM_KADRO_24_07_2026.xlsx"),
    ]
    for source, destination in copies:
        if source.exists() and not destination.exists():
            shutil.copy2(source, destination)
    for font in (ROOT / "assets" / "fonts").glob("*.ttf"):
        destination = target / "assets" / "fonts" / font.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(font, destination)
    data = registry()
    data.setdefault("tenants", {})[code] = {"name": name or code, "active": True}
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def run_tenant(code: str) -> subprocess.CompletedProcess:
    target = initialize_tenant(code)
    env = os.environ.copy()
    env.update(OMEHR_TENANT=_code(code), OMEHR_RUNTIME_ROOT=str(target), OMEHR_ISOLATED="1")
    return subprocess.run([sys.executable, str(ROOT / "main.py")], cwd=ROOT, env=env, text=True)


def tenant_status(code: str) -> dict:
    code = _code(code)
    path = ROOT / "tenants" / code / "logs" / "CURRENT_Runtime_Status.json"
    if not path.exists():
        return {"tenant": code, "status": "NOT_RUN"}
    result = json.loads(path.read_text(encoding="utf-8"))
    result["tenant"] = code
    return result
