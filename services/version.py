"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/version.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.version import *  # noqa: F401,F403
from services.system_config.version import (
    APP_VERSION,
    CURRENT_OUTPUT_LABEL,
    MODEL_VERSION,
    REPORT_SCHEMA_VERSION,
)
