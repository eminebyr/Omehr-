"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/multi_pc_sync.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.multi_pc_sync import *  # noqa: F401,F403
from services.data_access.multi_pc_sync import (
    detect_changed_sheets,
    invalidate_local_reports_if_shared_input_changed,
    pd_hash_bytes,
)
