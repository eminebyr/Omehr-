"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/transfer/gecici_gorevlendirme.py

services/transfer/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Transfer / Atama / Rotasyon" alanı).
`NEDEN_SECENEKLERI`, web/tab_modules/onaylar.py tarafından da kullanılır.
"""
from services.transfer.gecici_gorevlendirme import *  # noqa: F401,F403
from services.transfer.gecici_gorevlendirme import (
    NEDEN_SECENEKLERI,
    create_temporary_assignment_documents,
    create_temporary_assignment_documents_and_notify,
)
