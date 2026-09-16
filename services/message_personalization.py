"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/message_personalization.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.message_personalization import *  # noqa: F401,F403
from services.reporting.message_personalization import (
    ai_enabled,
    is_company_owner,
    is_executive_audience,
    product_label,
    recipient_name,
    report_scope_text,
    salutation,
    text,
)
