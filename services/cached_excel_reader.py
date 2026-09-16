"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/cached_excel_reader.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).
"""
from services.data_access.cached_excel_reader import *  # noqa: F401,F403
from services.data_access.cached_excel_reader import (
    _dosyayi_gerekirse_yenile,  # tests/test_fast_cache_fingerprint.py monkeypatch.setattr ile buna erişir
    _SAYFA_ONBELLEGI,  # tests/test_fast_cache_fingerprint.py buna doğrudan erişir
    invalidate_table,
    load_cached_table,
    load_dim_magaza,
    load_dim_unvan,
    load_fact_mevcut,
    load_fact_norm,
    load_mail_listesi,
    load_transfer_talepleri,
    personel_alan_degisikligi,
    read_sheet_cached,
    read_workbook_cached,
    refresh_changed_table,
    son_degisen_sayfalar,
)
