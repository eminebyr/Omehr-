"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/outlook_adapter.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.outlook_adapter import *  # noqa: F401,F403
from services.system_config.outlook_adapter import send_outlook
