"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/multitenant/billing.py"""
from services.multitenant.billing import *  # noqa: F401,F403
from services.multitenant.billing import PLAN_KOTALARI, process_billing_event
