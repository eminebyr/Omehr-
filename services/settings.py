"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/settings.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.settings import *  # noqa: F401,F403
from services.system_config.settings import DEFAULT_INPUT_FILE_NAME, input_file_name, input_path
