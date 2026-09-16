"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/powerbi_push.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı). `_satirlari_json_
uyumlu_yap`, tests/test_powerbi_push.py tarafından doğrudan içe
aktarılır — bu yüzden açıkça yeniden dışa aktarılır.
"""
from services.reporting.powerbi_push import *  # noqa: F401,F403
from services.reporting.powerbi_push import (
    AUTHORITY_URL_TEMPLATE,
    MAX_ROWS_PER_REQUEST,
    POWERBI_API_BASE,
    POWERBI_SCOPE,
    PowerBIConfig,
    _satirlari_json_uyumlu_yap,
    dataset_definition,
    ensure_dataset,
    get_access_token,
    push_table,
    push_to_powerbi,
    table_schema,
)
