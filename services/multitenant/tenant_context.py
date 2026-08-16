"""OTURUM BAZLI KİRACI BAĞLAMI.

Hangi kiracının verisiyle çalışıldığını belirler — önce Streamlit
oturumundan (kullanıcının giriş sırasında seçtiği firma), yoksa
BASDAS_TENANT ortam değişkeninden (tek-kiracılı/eski kurulum için
geriye dönük uyumluluk) çözümlenir.
"""
from __future__ import annotations

import os


def current_tenant_id() -> str:
    try:
        import streamlit as st
        deger = st.session_state.get("_secili_kiraci")
        if deger:
            return str(deger).strip().upper()
    except Exception:
        pass
    return os.getenv("BASDAS_TENANT", "BASDAS").strip().upper()


def set_session_tenant(tenant_id: str) -> None:
    import streamlit as st
    st.session_state["_secili_kiraci"] = str(tenant_id).strip().upper()
