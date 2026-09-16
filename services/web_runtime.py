"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/web_runtime.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.web_runtime import *  # noqa: F401,F403
from services.system_config.web_runtime import (
    connect_web_db,
    db_path,
    log_web_action,
    optimistic_update_transfer,
    yeni_transfer_no,
)
