"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/security_auth/session_guard.py

services/security_auth/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Güvenlik / Kimlik Doğrulama" alanı). Bu dosya,
mevcut `from services.session_guard import X` şeklindeki tüm
çağıranların (bkz. tests/test_session_idle_timeout.py::
test_web_app_actually_wires_idle_timeout_into_authenticated_flow —
web/app.py'nin KAYNAK METNİNDEKİ bu tam import satırını doğrular)
hiçbir değişiklik gerektirmeden çalışmaya devam etmesi için
bırakılmıştır.
"""
from services.security_auth.session_guard import *  # noqa: F401,F403
from services.security_auth.session_guard import idle_timeout_dakika, oturum_suresi_doldu_mu
