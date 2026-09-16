"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/mail_router.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı). `_apply_subscription_
filter`, report_mail_engine.py tarafından doğrudan içe aktarılır
(tests/test_mail_router_integration.py bu tam import satırının
report_mail_engine.py'nin KAYNAK METNİNDE var olduğunu da doğrular) —
bu yüzden açıkça yeniden dışa aktarılır.
"""
from services.reporting.mail_router import *  # noqa: F401,F403
from services.reporting.mail_router import (
    EVENT_SUBSCRIPTION_COLUMN,
    _apply_subscription_filter,
    resolve_recipients,
)
