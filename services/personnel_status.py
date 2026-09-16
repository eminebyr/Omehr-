"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/personnel/personnel_status.py

services/personnel/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Personel Yaşam Döngüsü" alanı). Bu dosya, mevcut `from services.personnel_status
import X` şeklindeki tüm çağıranların hiçbir değişiklik gerektirmeden
çalışmaya devam etmesi için bırakılmıştır.
"""
from services.personnel.personnel_status import *  # noqa: F401,F403
from services.personnel.personnel_status import (
    EXIT_COLUMNS,
    active_people,
    exit_is_recorded,
    first_exit_column,
    row_is_active,
)
