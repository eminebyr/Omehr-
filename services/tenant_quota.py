"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/tenant_quota.py"""
from services.multitenant.tenant_quota import *  # noqa: F401,F403
from services.multitenant.tenant_quota import KotaAsimiHatasi, enforce_for_sheet, check_branch_quota
