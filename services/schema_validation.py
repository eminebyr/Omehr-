"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/schema_validation.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.schema_validation import *  # noqa: F401,F403
from services.data_access.schema_validation import (
    REQUIRED_COLUMNS,
    DogrulamaSonucu,
    SchemaValidationError,
    validate,
)
