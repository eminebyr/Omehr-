"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/personnel/personnel_notifications.py

services/personnel/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Personel Yaşam Döngüsü" alanı). Bu dosya, mevcut
`from services.personnel_notifications import X` şeklindeki tüm çağıranların
hiçbir değişiklik gerektirmeden çalışmaya devam etmesi için bırakılmıştır.
"""
from services.personnel.personnel_notifications import *  # noqa: F401,F403
from services.personnel.personnel_notifications import (
    personnel_event_recipients,
    selectable_extra_contacts,
    send_personnel_event_mail,
)
