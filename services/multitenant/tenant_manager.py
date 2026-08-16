"""DOSYA TABANLI KİRACI YÖNETİMİ (tenants.json).

services/multitenant/tenant_registry.py (veritabanı tabanlı) gerçek
SaaS/plan/kota yönetimi için tercih edilen yoldur — bu modül, dosya/
süreç tabanlı dağıtım (her kiracının kendi runtime dizini) için geriye
dönük uyumluluk amacıyla korunur.
"""
from __future__ import annotations

import json
from pathlib import Path

from services.runtime_paths import code_root


def _registry_path() -> Path:
    return code_root() / "tenants.json"


def registry() -> dict:
    yol = _registry_path()
    if not yol.is_file():
        return {"tenants": {}}
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return {"tenants": {}}


def _kaydet(veri: dict) -> None:
    _registry_path().write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def initialize_tenant(code: str) -> Path:
    code = code.strip().upper()
    from services.runtime_paths import runtime_root
    veri = registry()
    if code not in veri.get("tenants", {}):
        veri.setdefault("tenants", {})[code] = {"code": code, "active": True}
        _kaydet(veri)
    return runtime_root()


def tenant_status(code: str) -> dict | None:
    return registry().get("tenants", {}).get(code.strip().upper())


def run_tenant(code: str):
    """Bir kiracının runtime dizinini hazırlar ve döner (initialize_tenant
    ile aynı işi yapar — dosya/süreç tabanlı dağıtımda çağıran kodun
    beklediği isimlendirme farklılığı için bir takma ad)."""
    return initialize_tenant(code)
