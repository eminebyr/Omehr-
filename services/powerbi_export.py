"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/powerbi_export.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.powerbi_export import *  # noqa: F401,F403
from services.reporting.powerbi_export import (
    OUTPUT_FILE_NAME,
    build_powerbi_model,
    export_powerbi_workbook,
)
