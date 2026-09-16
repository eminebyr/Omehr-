"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/app_settings.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.app_settings import *  # noqa: F401,F403
from services.system_config.app_settings import (
    FEATURE_LABELS,
    get_feature_flags,
    get_settings,
    input_file_info,
    set_feature_flags,
    update_settings,
)
