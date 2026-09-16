"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/exceptions.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.exceptions import *  # noqa: F401,F403
from services.system_config.exceptions import (
    AuthorizationError,
    ConfigurationError,
    MailDeliveryError,
    OmehrError,
    TransferConflictError,
    WorkbookError,
)
