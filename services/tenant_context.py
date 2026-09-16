"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/tenant_context.py

services/multitenant/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Çok Kiracılılık (Multi-tenant) / Faturalama"
alanı).
"""
from services.multitenant.tenant_context import *  # noqa: F401,F403
from services.multitenant.tenant_context import current_tenant_id, set_session_tenant
