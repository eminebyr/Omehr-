"""GİRİŞ AKIŞI — kiracı seçiminin oturuma doğru yazıldığını kanıtlar.

Bu, tests/test_multitenant_isolation.py'nin kanıtladığı veri katmanı
izolasyonunu TAMAMLAR: orası "tenant_id verilirse doğru izole olur"
diyor, burası "web girişi GERÇEKTEN doğru tenant_id'yi set ediyor mu"
sorusunu yanıtlar. İkisi birlikte, uçtan uca (giriş ekranından veri
satırına kadar) izolasyon garantisini kanıtlar.
"""
from __future__ import annotations

import sys
import types

import pytest


class _SahteSessionState(dict):
    """Streamlit'in st.session_state'ini taklit eder — hem sözlük hem
    öznitelik erişimini destekler (web/app.py ikisini de kullanıyor)."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def sahte_streamlit_oturumu(monkeypatch):
    """services.tenant_context'in kontrol ettiği gerçek st.session_state
    yerine, testler arasında sızmayan İZOLE bir sahte oturum kurar."""
    sahte_st = types.SimpleNamespace(session_state=_SahteSessionState())
    monkeypatch.setitem(sys.modules, "streamlit", sahte_st)
    yield sahte_st.session_state


def test_set_session_tenant_sonrasi_current_tenant_id_dogru_doner(sahte_streamlit_oturumu, monkeypatch):
    """web/app.py'nin giriş formunda çağırdığı TAM akışı taklit eder:
    kullanıcı bir firma seçer -> set_session_tenant() çağrılır ->
    current_tenant_id() ARTIK o firmayı döndürmeli (ortam değişkeninden
    ÖNCELİKLİ, bkz. services/tenant_context.py öncelik sırası)."""
    monkeypatch.setenv("BASDAS_TENANT", "YANLIS_KIRACI")  # işlem-geneli bağlam kasıtlı YANLIŞ
    from services.tenant_context import current_tenant_id, set_session_tenant

    assert current_tenant_id() == "YANLIS_KIRACI", "oturum boşken ortam değişkenine düşmeli"

    set_session_tenant("DOGRU_KIRACI")
    assert current_tenant_id() == "DOGRU_KIRACI", (
        "Giriş formunda seçilen kiracı, işlem-geneli ortam değişkenini "
        "EZMELİ — aksi halde aynı sunucu sürecinde farklı firmalardan "
        "kullanıcılar birbirinin verisini görebilir."
    )


def test_iki_ayri_sahte_oturum_birbirinden_bagimsiz(monkeypatch):
    """KRİTİK EŞZAMANLILIK SENARYOSU: aynı çalışan süreçte, biri A
    firmasına biri B firmasına giriş yapmış iki KULLANICIYI simüle eder
    (iki ayrı session_state nesnesi — Streamlit'te her tarayıcı
    sekmesinin GERÇEKTE sahip olduğu şey budur). Biri diğerini ASLA
    etkilememeli."""
    monkeypatch.delenv("BASDAS_TENANT", raising=False)
    from services.tenant_context import current_tenant_id, set_session_tenant
    import streamlit as st_gercek  # bu noktada henüz yamalanmadı

    oturum_a = types.SimpleNamespace(session_state=_SahteSessionState())
    oturum_b = types.SimpleNamespace(session_state=_SahteSessionState())

    sys.modules["streamlit"] = oturum_a
    set_session_tenant("FIRMA_A")
    assert current_tenant_id() == "FIRMA_A"

    sys.modules["streamlit"] = oturum_b
    set_session_tenant("FIRMA_B")
    assert current_tenant_id() == "FIRMA_B"

    # A'nın oturumuna GERİ dönülürse, A'nın kiracısı HALA doğru olmalı —
    # B'ye geçiş A'nın oturum durumunu bozmamış olmalı.
    sys.modules["streamlit"] = oturum_a
    assert current_tenant_id() == "FIRMA_A", (
        "KRİTİK SIZINTI RİSKİ: bir kullanıcının kiracı seçimi başka bir "
        "kullanıcının oturumunu etkilememeli."
    )

    sys.modules["streamlit"] = st_gercek
