"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/tenant_manager.py

services/multitenant/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Çok Kiracılılık (Multi-tenant) / Faturalama"
alanı — bu alanın geri kalanı, burada belgelenen önceki başarısız
taşıma denemesinin nedenleri anlaşılıp aynı hatalar (git mv yerine
elle yeniden yazım, shim'siz taşıma) tekrarlanmadan bu kez
tamamlanmıştır).
"""
from services.multitenant.tenant_manager import *  # noqa: F401,F403
from services.multitenant.tenant_manager import (
    REGISTRY,
    ROOT,
    initialize_tenant,
    registry,
    run_tenant,
    tenant_status,
)
