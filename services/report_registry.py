"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/report_registry.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.report_registry import *  # noqa: F401,F403
from services.reporting.report_registry import build_key, find_existing, get_or_build, register
