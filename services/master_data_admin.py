"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/master_data_admin.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
`EDITABLE_COLUMNS`, services/personnel/personnel_exit.py (BAŞKA bir
bounded-context) tarafından da kullanılır — bu yüzden açıkça yeniden
dışa aktarılır.
"""
from services.data_access.master_data_admin import *  # noqa: F401,F403
from services.data_access.master_data_admin import (
    EDITABLE_COLUMNS,
    read_tables,
    save_tables,
    validate_tables,
)
