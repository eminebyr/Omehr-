"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/security_auth/security.py

services/security_auth/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Güvenlik / Kimlik Doğrulama" alanı). Alt paket
BİLEREK "security_auth" adını taşır, "security" değil — aksi halde bu
düz shim dosyası, aynı ada sahip bir alt paket tarafından Python'un
import çözümlemesinde SESSİZCE GÖLGELENİRDİ (paketler, aynı isimli düz
modüllerden önce çözülür; bizzat doğrulandı). Bu dosya, mevcut
`from services.security import X` şeklindeki tüm çağıranların hiçbir
değişiklik gerektirmeden çalışmaya devam etmesi için bırakılmıştır.
"""
from services.security_auth.security import *  # noqa: F401,F403
from services.security_auth.security import (
    ITERATIONS,
    LOCK_MINUTES,
    MAX_FAILURES,
    _db_path,
    _derive,
    authenticate,
    credential_exists,
    migrate_legacy_input,
    password_error,
    set_password,
)
