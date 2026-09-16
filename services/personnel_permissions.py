"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/personnel/personnel_permissions.py

services/personnel/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Personel Yaşam Döngüsü" alanı). Bu dosya, mevcut
`from services.personnel_permissions import X` şeklindeki tüm çağıranların
hiçbir değişiklik gerektirmeden çalışmaya devam etmesi için bırakılmıştır.
"""
from services.personnel.personnel_permissions import *  # noqa: F401,F403
from services.personnel.personnel_permissions import (
    DEFAULTS,
    PERMISSIONS,
    can,
    load_permissions,
    permissions_for,
    save_user_permissions,
)
