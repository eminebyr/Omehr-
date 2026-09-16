"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/dashboard_model.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.dashboard_model import *  # noqa: F401,F403
from services.system_config.dashboard_model import (
    CONTROL_FILENAME,
    DISPLAY_ROLE,
    ROLE_ALIASES,
    STORE_ALIASES,
    active_people,
    build_dashboard_model,
    reconcile_store_net,
    role_key,
    store_key,
    text_key,
)
