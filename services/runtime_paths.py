"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/runtime_paths.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.runtime_paths import *  # noqa: F401,F403
from services.system_config.runtime_paths import code_root, runtime_root, tenant_code
