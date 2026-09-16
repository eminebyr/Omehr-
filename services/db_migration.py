"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/db_migration.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.db_migration import *  # noqa: F401,F403
from services.data_access.db_migration import migrate_database
