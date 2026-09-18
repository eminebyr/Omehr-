"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/tenant_quota.py

services/multitenant/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Çok Kiracılılık (Multi-tenant) / Faturalama"
alanı).
"""
from services.multitenant.tenant_quota import *  # noqa: F401,F403
from services.multitenant.tenant_quota import (
    QUOTA_KONTROLLU_SAYFALAR,
    KotaAsimiHatasi,
    check_branch_quota,
    check_user_quota,
    enforce_for_sheet,
)
