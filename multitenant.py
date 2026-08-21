from __future__ import annotations

from services.runtime_paths import tenant_code
from services.tenant_manager import initialize_tenant, registry, run_tenant, tenant_status


def get_companies() -> dict:
    return registry().get("tenants", {})


def active_company() -> str:
    return tenant_code()


def switch_company(code: str) -> dict:
    """Global durum değiştirmez; tenant alanını hazırlar ve çalıştırma bilgisini döndürür."""
    path = initialize_tenant(code)
    company = get_companies()[code.strip().upper()].copy()
    company["runtime_root"] = str(path)
    return company


__all__ = [
    "get_companies", "active_company", "switch_company",
    "initialize_tenant", "run_tenant", "tenant_status",
]
