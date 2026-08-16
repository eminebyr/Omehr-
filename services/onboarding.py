"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/onboarding.py"""
from services.multitenant.onboarding import *  # noqa: F401,F403
from services.multitenant.onboarding import (
    validate_tenant_id, validate_password,
    register_tenant, register_first_admin, import_initial_data,
)
