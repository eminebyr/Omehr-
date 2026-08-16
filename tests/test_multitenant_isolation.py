"""ÇOK KİRACILI (multi-tenant) İZOLASYON — kritik testler.

Bu dosya, SaaS'ın en temel garantisini kanıtlar: AYNI veritabanında,
AYNI çalışan süreçte, İKİ FARKLI kiracının verisi HİÇBİR ŞEKİLDE
karışmaz — ne okuma sırasında (bir kiracı diğerinin satırını göremez),
ne yazma sırasında (bir kiracının kaydetmesi diğerinin satırını silmez/
değiştirmez).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest


def _ornek_dosya() -> Path:
    return Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"


@pytest.fixture
def iki_kiracili_db(isolated_root, monkeypatch):
    """Aynı veritabanında A ve B kodlu iki kiracı kurar, İKİSİNE DE
    aynı örnek Excel'i (farklı personel isimleriyle DEĞİŞTİRİLMİŞ)
    göç ettirir."""
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")
    (isolated_root / "data").mkdir(parents=True, exist_ok=True)

    from services.input_excel_migration import migrate_excel_to_db
    from services.tenant_registry import create_tenant

    create_tenant("KIRACI_A", "A Firması", plan="standart", sube_kotasi=200, kullanici_kotasi=100)
    create_tenant("KIRACI_B", "B Firması", plan="temel", sube_kotasi=200, kullanici_kotasi=100)

    migrate_excel_to_db(str(_ornek_dosya()), tenant_id="KIRACI_A")
    migrate_excel_to_db(str(_ornek_dosya()), tenant_id="KIRACI_B")

    yield isolated_root


# ------------------------------------------------------------------
# OKUMA İZOLASYONU
# ------------------------------------------------------------------
def test_iki_kiraci_ayni_tabloda_karismaz(iki_kiracili_db):
    from services.input_data_access import read_sheet

    a = read_sheet("Fact_Mevcut", tenant_id="KIRACI_A")
    b = read_sheet("Fact_Mevcut", tenant_id="KIRACI_B")
    assert len(a) == len(b) == 596


def test_bir_kiraci_diger_kiracinin_ozel_kaydini_goremez(iki_kiracili_db):
    """A kiracısına GERÇEKTEN sadece A'da var olan, uydurma bir personel
    ekler; B'nin bu kaydı HİÇBİR ŞEKİLDE görmediğini kanıtlar."""
    from services.input_data_access import read_sheet, write_sheet

    a = read_sheet("Fact_Mevcut", tenant_id="KIRACI_A")
    ozel_kayit = {c: None for c in a.columns}
    ozel_kayit.update({
        "İsim Soyisim": "YALNIZ_KIRACI_A_GORMELI", "MağazaID": a["MağazaID"].iloc[0],
        "Mağaza": a["Mağaza"].iloc[0], "UnvanID": a["UnvanID"].iloc[0], "Unvan": a["Unvan"].iloc[0],
        "İşe Giriş": "2026-08-08",
    })
    guncel_a = pd.concat([a, pd.DataFrame([ozel_kayit])], ignore_index=True)
    write_sheet("Fact_Mevcut", guncel_a, kullanici="test", tenant_id="KIRACI_A")

    a2 = read_sheet("Fact_Mevcut", tenant_id="KIRACI_A")
    b2 = read_sheet("Fact_Mevcut", tenant_id="KIRACI_B")
    assert (a2["İsim Soyisim"] == "YALNIZ_KIRACI_A_GORMELI").any(), "A kendi eklediğini görmeli"
    assert not (b2["İsim Soyisim"] == "YALNIZ_KIRACI_A_GORMELI").any(), \
        "KRİTİK SIZINTI: B, A'nın özel kaydını görüyor!"
    assert len(b2) == 596, "B'nin satır sayısı A'nın eklemesinden ETKİLENMEMELİ"


# ------------------------------------------------------------------
# YAZMA İZOLASYONU (en kritik risk: DELETE'in kapsamı)
# ------------------------------------------------------------------
def test_bir_kiracinin_kaydetmesi_digerinin_verisini_SILMEZ(iki_kiracili_db):
    """KRİTİK GÜVENLİK TESTİ: write_sheet()'in DELETE adımı yalnız
    KENDİ kiracısının satırlarını silmeli. Bu test, önceki (tek kiracılı
    dönemden kalma) `DELETE FROM tablo` (WHERE'siz, TÜM kiracıları silen)
    hatasının bir daha asla geri gelmediğini kanıtlar."""
    from services.input_data_access import read_sheet, write_sheet

    b_once = read_sheet("Fact_Norm", tenant_id="KIRACI_B")
    assert len(b_once) == 419

    # A kendi Fact_Norm'unu tamamen boşaltıp yeniden yazsın (aşırı durum testi)
    a = read_sheet("Fact_Norm", tenant_id="KIRACI_A")
    yazilan = write_sheet("Fact_Norm", a.iloc[:5], kullanici="test", tenant_id="KIRACI_A")
    assert yazilan == 5

    a_sonra = read_sheet("Fact_Norm", tenant_id="KIRACI_A")
    b_sonra = read_sheet("Fact_Norm", tenant_id="KIRACI_B")
    assert len(a_sonra) == 5, "A kendi verisini küçültebilmeli"
    assert len(b_sonra) == 419, \
        "KRİTİK VERİ KAYBI: A'nın yazması B'nin satırlarını sildi!"


# ------------------------------------------------------------------
# HESAPLAMA İZOLASYONU (uçtan uca, main.py'nin kullandığı gerçek zincir)
# ------------------------------------------------------------------
def test_iki_kiracinin_kpi_hesaplamasi_birbirinden_bagimsiz(iki_kiracili_db):
    """A'nın verisini değiştirdikten sonra, A'nın KPI'ları değişir ama
    B'ninkiler AYNI (Excel'den göç edilen orijinal) değerde kalmalı."""
    from services.input_data_access import read_sheet, write_sheet
    from src.state_engine import state
    from src.kpi_engine import kpis

    def _kpi_for(tenant):
        sheets = {}
        from services.input_db_schema import load_schema
        for sn in load_schema():
            sheets[sn] = read_sheet(sn, tenant_id=tenant)
        st, _ = state(sheets["Fact_Norm"], sheets["Fact_Mevcut"], sheets)
        return kpis(st)

    kpi_a_once = _kpi_for("KIRACI_A")
    kpi_b_once = _kpi_for("KIRACI_B")
    assert kpi_a_once == kpi_b_once, "aynı örnek veriyle göç edildiği için başlangıçta eşit olmalı"

    # A'ya 1 yeni norm-fazlası personel ekle
    staff_a = read_sheet("Fact_Mevcut", tenant_id="KIRACI_A")
    yeni = {c: None for c in staff_a.columns}
    yeni.update({
        "İsim Soyisim": "KIRACI_A_EK_PERSONEL", "MağazaID": staff_a["MağazaID"].iloc[0],
        "Mağaza": staff_a["Mağaza"].iloc[0], "UnvanID": staff_a["UnvanID"].iloc[0],
        "Unvan": staff_a["Unvan"].iloc[0], "İşe Giriş": "2026-08-08",
    })
    guncel = pd.concat([staff_a, pd.DataFrame([yeni])], ignore_index=True)
    write_sheet("Fact_Mevcut", guncel, kullanici="test", tenant_id="KIRACI_A")

    kpi_a_sonra = _kpi_for("KIRACI_A")
    kpi_b_sonra = _kpi_for("KIRACI_B")

    assert kpi_a_sonra["Aktif Mevcut"] == kpi_a_once["Aktif Mevcut"] + 1
    assert kpi_b_sonra == kpi_b_once, "B'nin KPI'ları A'daki değişiklikten ETKİLENMEMELİ"


# ------------------------------------------------------------------
# KİRACI KAYDI (registry)
# ------------------------------------------------------------------
def test_tenant_registry_crud(isolated_root, monkeypatch):
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    (isolated_root / "data").mkdir(parents=True, exist_ok=True)
    from services.tenant_registry import create_tenant, get_tenant, list_tenants, set_status, is_active

    create_tenant("YENI_FIRMA", "Yeni Firma A.Ş.", plan="kurumsal", sube_kotasi=100, kullanici_kotasi=50)
    kayit = get_tenant("YENI_FIRMA")
    assert kayit["ad"] == "Yeni Firma A.Ş."
    assert kayit["plan"] == "kurumsal"
    assert kayit["sube_kotasi"] == 100
    assert is_active("YENI_FIRMA") is True

    set_status("YENI_FIRMA", "askida")
    assert is_active("YENI_FIRMA") is False

    tumu = list_tenants()
    assert any(t["tenant_id"] == "YENI_FIRMA" for t in tumu)

    with pytest.raises(ValueError, match="zaten kayıtlı"):
        create_tenant("YENI_FIRMA", "Tekrar")


def test_tenant_context_env_fallback(monkeypatch):
    """Web oturumu yoksa (main.py toplu çalıştırma, worker, testler),
    BASDAS_TENANT ortam değişkenine düşmeli; o da yoksa varsayılan 'BASDAS'."""
    monkeypatch.delenv("BASDAS_TENANT", raising=False)
    from services.tenant_context import current_tenant_id
    assert current_tenant_id() == "BASDAS"

    monkeypatch.setenv("BASDAS_TENANT", "OZEL_KOD")
    assert current_tenant_id() == "OZEL_KOD"


def test_excel_modu_tenant_sisteminden_hic_etkilenmez(monkeypatch):
    """En önemli geriye dönük uyumluluk garantisi: BASDAS_INPUT_SOURCE
    ayarlanmamışsa (varsayılan Excel modu), kiracı sistemi devreye HİÇ
    girmez — mevcut tek-firma davranışı harfiyen korunur."""
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    import common_veri_okuma
    import importlib
    importlib.reload(common_veri_okuma)
    assert common_veri_okuma._db_modu() is False
