"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/excel_read_shim.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı). main.py,
web/app.py, worker.py bu dosyayı EN BAŞTA `install()` çağırmak için
import eder — bu shim o çağrının hiçbir değişiklik gerektirmeden
çalışmasını sağlar.
"""
from services.data_access.excel_read_shim import *  # noqa: F401,F403
from services.data_access.excel_read_shim import (
    _girdi_dosyasi_mi,  # tests/test_db_backed_input.py buna doğrudan erişir
    install,
    uninstall,
)
