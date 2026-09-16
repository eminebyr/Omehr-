"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/security_auth/region_access.py

services/security_auth/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Güvenlik / Kimlik Doğrulama" alanı). Bu dosya,
mevcut `from services.region_access import X` şeklindeki tüm
çağıranların hiçbir değişiklik gerektirmeden çalışmaya devam etmesi
için bırakılmıştır.
"""
from services.security_auth.region_access import *  # noqa: F401,F403
from services.security_auth.region_access import (
    is_global_scope,
    load_contacts,
    region_report_paths,
    safe_text,
    slug,
    yes,
)
