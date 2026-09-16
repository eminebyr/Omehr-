"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/personnel/personnel_exit.py

services/personnel/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Personel Yaşam Döngüsü" alanı). Bu dosya, mevcut `from services.personnel_exit
import X` şeklindeki tüm çağıranların hiçbir değişiklik gerektirmeden
çalışmaya devam etmesi için bırakılmıştır.
"""
from services.personnel.personnel_exit import *  # noqa: F401,F403
from services.personnel.personnel_exit import (
    add_personnel,
    add_personnel_bulk,
    aktif_personel_karti_verisi,
    cikis_nedenleri,
    is_active,
    load_personnel_view,
    process_exit,
    process_exits_bulk,
    undo_exit,
    update_personnel,
)
