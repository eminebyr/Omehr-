"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/input_data_access.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.input_data_access import *  # noqa: F401,F403
from services.data_access.input_data_access import (
    ensure_schema,
    input_source,
    read_all_sheets,
    read_sheet,
    tenant_content_version,
    write_sheet,
)
