"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/personnel/personnel_notes.py

services/personnel/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Personel Yaşam Döngüsü" alanı). Bu dosya, mevcut `from services.personnel_notes
import X` şeklindeki tüm çağıranların hiçbir değişiklik gerektirmeden
çalışmaya devam etmesi için bırakılmıştır.
"""
from services.personnel.personnel_notes import *  # noqa: F401,F403
from services.personnel.personnel_notes import format_person_note, note_kind
