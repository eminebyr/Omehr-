"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/home_proximity.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.home_proximity import *  # noqa: F401,F403
from services.system_config.home_proximity import (
    NEW_COLUMNS,
    REQUIRED_PERSON_COLS,
    TOP_N,
    compute_home_proximity,
    maps_route,
    refresh_home_proximity,
)
