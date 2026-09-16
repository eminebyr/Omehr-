"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/mail_idempotency.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.mail_idempotency import *  # noqa: F401,F403
from services.reporting.mail_idempotency import (
    MAX_RETRIES_DEFAULT,
    build_key,
    compute_attachment_hash,
    send_idempotent,
    stats,
    yeni_mail_id,
)
