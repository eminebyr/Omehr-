"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/multi_pc_excel.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.multi_pc_excel import *  # noqa: F401,F403
from services.data_access.multi_pc_excel import excel_transaction_lock, lock_path
