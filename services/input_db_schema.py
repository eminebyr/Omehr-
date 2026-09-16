"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/input_db_schema.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı). Şema
JSON dosyası (input_db_schema_data.json) da AYNI alt pakete taşındı.
"""
from services.data_access.input_db_schema import *  # noqa: F401,F403
from services.data_access.input_db_schema import (
    create_table_ddl,
    create_tenant_index_ddl,
    load_schema,
)
