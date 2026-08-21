"""KİRACI (tenant) ÇÖZÜMLEME — SaaS çok kiracılı temel.

Amaç: hangi kod yolundan çağrılırsa çağrılsın (web paneli, main.py toplu
çalıştırma, arka plan worker, testler), "şu an hangi firma için
çalışıyoruz" sorusuna TEK, tutarlı bir cevap vermek.

Öncelik sırası:
  1) Streamlit oturumunda GİRİŞ YAPMIŞ kullanıcının tenant_id'si
     (gerçek SaaS'ta beklenen: aynı çalışan sunucu, farklı kullanıcılar
     farklı firmalara ait olabilir — kiracı seçimi OTURUMA bağlıdır,
     sabit bir ortam değişkenine DEĞİL).
  2) OMEHR_TENANT ortam değişkeni (services/runtime_paths.py::tenant_code) —
     geriye dönük uyumluluk: main.py toplu çalıştırma, worker, testler
     ve "kiracı başına ayrı süreç" dağıtım modeli (services/tenant_manager.py)
     için hâlâ geçerlidir.
  3) Hiçbiri yoksa varsayılan tek-kiracı kodu: 'BASDAS'.

Bu modül BİLEREK ayrı tutulur (services/runtime_paths.py'yi BÜYÜTMEK
yerine) — dosya-yolu tabanlı izolasyon (runtime_root) ile veritabanı
satırı tabanlı izolasyon (tenant_id sütunu) KAVRAMSAL OLARAK farklıdır;
ikisi aynı anda, birbirini tamamlayarak kullanılabilir.
"""
from __future__ import annotations

import os

_VARSAYILAN_KIRACI = "BASDAS"

# Web oturumu bu modülü import ederken bir döngüsel bağımlılığa
# girmemesi için streamlit BURADA değil, fonksiyon içinde import edilir.


def _oturumdan_kiraci() -> str | None:
    try:
        import streamlit as st
    except Exception:
        return None
    try:
        if not hasattr(st, "session_state"):
            return None
        kullanici = st.session_state.get("basdas_kullanici")
        if kullanici and isinstance(kullanici, dict):
            tid = kullanici.get("tenant_id")
            if tid:
                return str(tid).strip().upper()
    except Exception:
        return None
    return None


def current_tenant_id() -> str:
    """Şu an aktif olan kiracı kodunu döner. Asla None dönmez."""
    oturum = _oturumdan_kiraci()
    if oturum:
        return oturum
    ortam = os.getenv("OMEHR_TENANT", "").strip().upper()
    if ortam:
        return ortam
    return _VARSAYILAN_KIRACI


def set_session_tenant(tenant_id: str) -> None:
    """Web girişinde, doğrulanan kullanıcının kiracısını oturuma yazar."""
    import streamlit as st
    if "basdas_kullanici" not in st.session_state or not isinstance(st.session_state.get("basdas_kullanici"), dict):
        st.session_state["basdas_kullanici"] = {}
    st.session_state["basdas_kullanici"]["tenant_id"] = str(tenant_id).strip().upper()
