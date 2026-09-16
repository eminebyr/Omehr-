"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/file_lock.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.file_lock import *  # noqa: F401,F403
from services.data_access.file_lock import file_lock, is_locked
