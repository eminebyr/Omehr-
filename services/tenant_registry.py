"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/tenant_registry.py

Önceden bu dosya services/multitenant/tenant_registry.py'nin BİREBİR
KOPYASIYDI (iki ayrı kaynak, sessizce birbirinden ayrışma riski
taşıyordu — services/billing.py + services/multitenant/billing.py'nin
zaten doğru şekilde izole ettiği aynı desen burada uygulanmamıştı).
Artık tek kaynak services/multitenant/tenant_registry.py'dir.
"""
from services.multitenant.tenant_registry import *  # noqa: F401,F403
from services.multitenant.tenant_registry import (
    check_quota,
    create_tenant,
    ensure_schema,
    get_tenant,
    is_active,
    list_tenants,
    set_status,
)
