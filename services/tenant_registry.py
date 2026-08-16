"""GERİYE DÖNÜK UYUMLULUK SHIM'İ.

Bu modülün GERÇEK içeriği services/multitenant/tenant_registry.py'ye
taşındı (Madde 4 — bounded-context ayrımı). Bu dosya, mevcut TÜM
`from services.tenant_registry import X` şeklindeki import satırlarının
(kod tabanında 20+ yerde) hiçbir değişiklik gerektirmeden çalışmaya
devam etmesi için bırakılmıştır.
"""
from services.multitenant.tenant_registry import *  # noqa: F401,F403
from services.multitenant.tenant_registry import (
    ensure_schema, create_tenant, get_tenant, list_tenants,
    is_active, check_quota, set_status,
)
