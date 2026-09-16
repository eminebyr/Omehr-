"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/pdf_compat.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.pdf_compat import *  # noqa: F401,F403
from services.system_config.pdf_compat import make_outlook_safe_pdf
