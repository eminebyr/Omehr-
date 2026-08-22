"""services/onboarding.py — kendi kendine kayıt akışı testleri."""
from __future__ import annotations

import importlib

import pytest


def _reload(*mod_names):
    import sys
    for name in mod_names:
        if name in sys.modules:
            importlib.reload(sys.modules[name])


def test_tam_kayit_akisi_uctan_uca(isolated_root, monkeypatch):
    """Firma kaydı -> ilk admin -> aynı bilgilerle giriş yapılabilmeli."""
    from services import onboarding, security, tenant_registry
    _reload("services.onboarding", "services.security", "services.tenant_registry")

    kayit = onboarding.register_tenant("YENIMARKET", "Yeni Market A.Ş.", plan="deneme")
    assert kayit["tenant_id"] == "YENIMARKET"
    assert tenant_registry.is_active("YENIMARKET")

    onboarding.register_first_admin("YENIMARKET", "admin", "GucluBirSifre2026")
    ok, msg, must_change = security.authenticate("admin", "GucluBirSifre2026", tenant_id="YENIMARKET")
    assert ok is True, msg
    assert must_change is False, "Kayıt sırasında kendi belirlediği şifre için değişim ZORUNLU olmamalı"


def test_zaten_alinmis_firma_kodu_reddedilir(isolated_root, monkeypatch):
    from services import onboarding
    _reload("services.onboarding", "services.tenant_registry")

    onboarding.register_tenant("CAKISMA", "İlk Firma")
    with pytest.raises(ValueError, match="zaten kullanılıyor"):
        onboarding.register_tenant("CAKISMA", "İkinci Firma")


def test_zayif_sifre_reddedilir(isolated_root, monkeypatch):
    from services import onboarding
    _reload("services.onboarding", "services.tenant_registry")

    onboarding.register_tenant("ZAYIFSIFRE", "Test Firma")
    with pytest.raises(ValueError, match="en az"):
        onboarding.register_first_admin("ZAYIFSIFRE", "admin", "kisa")


def test_gecersiz_firma_kodu_formati_reddedilir(isolated_root, monkeypatch):
    from services import onboarding
    _reload("services.onboarding", "services.tenant_registry")

    with pytest.raises(ValueError, match="Firma kodu"):
        onboarding.register_tenant("ab", "Test Firma")
    with pytest.raises(ValueError, match="Firma kodu"):
        onboarding.register_tenant("1BASLAR RAKAMLA", "Test Firma")


def test_kayitsiz_firmaya_admin_eklenemez(isolated_root, monkeypatch):
    from services import onboarding
    _reload("services.onboarding", "services.tenant_registry")

    with pytest.raises(ValueError, match="bulunamadı"):
        onboarding.register_first_admin("HICOLMAYAN", "admin", "GucluBirSifre2026")


def test_kayit_sonrasi_gercek_giris_akisi_mail_listesinde_bulunur(isolated_root, monkeypatch):
    """KRİTİK: yalnız security.authenticate değil, web/app.py'nin GERÇEK
    giriş akışının kullandığı accounts()/Mail_Listesi eşleşmesi de
    çalışmalı — aksi halde doğru şifreyle bile 'kullanıcı bulunamadı'
    hatası alınırdı."""
    from services import onboarding
    from services.input_data_access import read_sheet
    from web.accounts import accounts
    _reload("services.onboarding", "services.tenant_registry", "services.input_data_access")

    monkeypatch.setenv("OMEHR_INPUT_SOURCE", "db")
    onboarding.register_tenant("GERCEKGIRIS", "Gerçek Giriş Test A.Ş.")
    onboarding.register_first_admin("GERCEKGIRIS", "yonetici1", "GucluSifre2026x", e_posta="test@ornek.com")

    sheets = {"Mail_Listesi": read_sheet("Mail_Listesi", tenant_id="GERCEKGIRIS")}
    hesaplar = accounts(sheets)
    eslesen = hesaplar[hesaplar["Web Kullanıcı"].astype(str).str.strip().eq("yonetici1")]
    assert not eslesen.empty, "Kayıt sonrası kullanıcı Mail_Listesi'nde (accounts()) bulunamadı"
    assert eslesen.iloc[0]["Rol"] == "ADMIN"


def test_iki_ayri_kayit_birbirinden_izole(isolated_root, monkeypatch):
    """İki farklı firma AYNI kullanıcı adıyla kayıt olabilmeli, birbirini etkilememeli."""
    from services import onboarding, security
    _reload("services.onboarding", "services.security", "services.tenant_registry")

    onboarding.register_tenant("FIRMAX", "Firma X")
    onboarding.register_tenant("FIRMAY", "Firma Y")
    onboarding.register_first_admin("FIRMAX", "admin", "SifreX123456789")
    onboarding.register_first_admin("FIRMAY", "admin", "SifreY987654321")

    ok_x, _, _ = security.authenticate("admin", "SifreX123456789", tenant_id="FIRMAX")
    ok_y, _, _ = security.authenticate("admin", "SifreY987654321", tenant_id="FIRMAY")
    capraz, _, _ = security.authenticate("admin", "SifreX123456789", tenant_id="FIRMAY")
    assert ok_x is True
    assert ok_y is True
    assert capraz is False
