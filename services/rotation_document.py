"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/transfer/rotation_document.py

services/transfer/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Transfer / Atama / Rotasyon" alanı).
`_template`, tests/test_transfer_notification_recipients.py tarafından
doğrudan içe aktarılır — bu yüzden açıkça yeniden dışa aktarılır.
"""
from services.transfer.rotation_document import *  # noqa: F401,F403
from services.transfer.rotation_document import (
    _template,
    create_rotation_documents,
    create_rotation_documents_and_notify,
)
