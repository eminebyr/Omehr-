from __future__ import annotations

"""Oturum işlemsizlik (idle) zaman aşımı — saf, test edilebilir mantık.

web/app.py bu modülü çağırır; Streamlit'e bağımlı DEĞİLDİR, bu yüzden
gerçek bir Streamlit oturumu başlatmadan doğrudan test edilebilir.
"""

import os
from datetime import datetime


def idle_timeout_dakika() -> int:
    return int(os.getenv("BASDAS_SESSION_IDLE_TIMEOUT_MIN", "480"))


def oturum_suresi_doldu_mu(son_aktivite_iso: str | None, simdi: datetime | None = None) -> tuple[bool, float]:
    """(süresi_doldu_mu, geçen_dakika) döner.

    son_aktivite_iso None/boş ise (ör. henüz hiç aktivite kaydı yoksa)
    süresi DOLMAMIŞ sayılır — yeni giriş yapan bir kullanıcıyı anında
    dışarı atmamak için."""
    if not son_aktivite_iso:
        return False, 0.0
    simdi = simdi or datetime.now()
    try:
        son_aktivite = datetime.fromisoformat(son_aktivite_iso)
    except (ValueError, TypeError):
        return False, 0.0
    gecen_dakika = (simdi - son_aktivite).total_seconds() / 60
    return gecen_dakika > idle_timeout_dakika(), gecen_dakika
