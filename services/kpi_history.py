"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/kpi_history.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.kpi_history import *  # noqa: F401,F403
from services.reporting.kpi_history import load_history, log_kpi_snapshot, snapshot_n_days_ago
