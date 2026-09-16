"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/excel_data_service.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı). Bu
modülün şu an hiçbir çağıranı yok (bizzat doğrulandı) — yine de
tutarlılık için diğer 13 dosyayla aynı şekilde taşındı/shim'lendi.
"""
from services.data_access.excel_data_service import *  # noqa: F401,F403
from services.data_access.excel_data_service import (
    invalidate_table,
    load_atamalar,
    load_cached_table,
    load_dim_magaza,
    load_dim_unvan,
    load_fact_mevcut,
    load_fact_norm,
    load_mail_listesi,
    load_personel_hareketleri,
    load_transfer_talepleri,
    refresh_changed_table,
)
