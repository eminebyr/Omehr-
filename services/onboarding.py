"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/onboarding.py

services/multitenant/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Çok Kiracılılık (Multi-tenant) / Faturalama"
alanı).
"""
from services.multitenant.onboarding import *  # noqa: F401,F403
from services.multitenant.onboarding import (
    import_initial_data,
    register_first_admin,
    register_tenant,
    validate_password,
    validate_tenant_id,
)
