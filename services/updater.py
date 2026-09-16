"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/updater.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.updater import *  # noqa: F401,F403
from services.system_config.updater import (
    UPDATE_EXCLUDE_ALWAYS,
    UPDATE_INCLUDE,
    UpdateResult,
    apply_update,
    compare_versions,
    create_pre_update_snapshot,
    current_version,
    rollback,
)
