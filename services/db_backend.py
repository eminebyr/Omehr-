"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/db_backend.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
services/multitenant/billing.py ve tenant_registry.py (BAŞKA bir
bounded-context) bu modülü kullanır — bu yüzden flat yol korunur.
"""
from services.data_access.db_backend import *  # noqa: F401,F403
from services.data_access.db_backend import backend_name, connect, ddl_for_backend
