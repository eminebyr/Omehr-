"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/fast_excel_views.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.fast_excel_views import *  # noqa: F401,F403
from services.data_access.fast_excel_views import clear, forecast_payload
