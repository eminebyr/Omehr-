"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/report_pipeline.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.report_pipeline import *  # noqa: F401,F403
from services.reporting.report_pipeline import validate_report_schema, write_audit
