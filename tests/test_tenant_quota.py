"""Kota uygulaması — gerçek testler.

services/tenant_registry.py'nin sube_kotasi/kullanici_kotasi
DEĞERLERİNİN, services/input_data_access.py::write_sheet() üzerinden
FİİLEN uygulandığını doğrular (önceden yalnız saklanıyordu, hiç
kontrol edilmiyordu).
"""
from __future__ import annotations

import importlib
import sys

import pandas as pd
import pytest


@pytest.fixture
def kota_ortami(tmp_path, monkeypatch):
    root = tmp_path
    (root / "input").mkdir()
    (root / "data").mkdir()
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(root))
    monkeypatch.setenv("OMEHR_DB_BACKEND", "sqlite")
    for mod_name in (
        "services.runtime_paths", "services.input_db_schema", "services.input_data_access",
        "services.tenant_registry", "services.tenant_quota", "services.tenant_context",
    ):
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
    try:
        yield root
    finally:
        monkeypatch.undo()
        for mod_name in (
            "services.runtime_paths", "services.input_db_schema", "services.input_data_access",
            "services.tenant_registry", "services.tenant_quota", "services.tenant_context",
        ):
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])


def test_sube_kotasi_asilinca_yazma_reddedilir(kota_ortami):
    from services.tenant_registry import create_tenant
    from services.input_data_access import ensure_schema, write_sheet
    from services.tenant_quota import KotaAsimiHatasi

    create_tenant("KUCUKFIRMA", "Küçük Firma A.Ş.", plan="deneme", sube_kotasi=2, kullanici_kotasi=5)
    ensure_schema()

    magaza_2 = pd.DataFrame([
        {"MağazaID": "M001", "Mağaza": "ŞUBE1"},
        {"MağazaID": "M002", "Mağaza": "ŞUBE2"},
    ])
    yazilan = write_sheet("Dim_Magaza", magaza_2, tenant_id="KUCUKFIRMA")
    assert yazilan == 2

    magaza_3 = pd.concat([magaza_2, pd.DataFrame([{"MağazaID": "M003", "Mağaza": "ŞUBE3"}])], ignore_index=True)
    with pytest.raises(KotaAsimiHatasi):
        write_sheet("Dim_Magaza", magaza_3, tenant_id="KUCUKFIRMA")

    # Kota aşımı reddedildiğinde, ÖNCEKİ 2 satırlık geçerli durum BOZULMAMALI.
    from services.input_data_access import read_sheet
    assert len(read_sheet("Dim_Magaza", tenant_id="KUCUKFIRMA")) == 2


def test_kullanici_kotasi_asilinca_yazma_reddedilir(kota_ortami):
    from services.tenant_registry import create_tenant
    from services.input_data_access import ensure_schema, write_sheet
    from services.tenant_quota import KotaAsimiHatasi

    create_tenant("KUCUKFIRMA2", "Küçük Firma B.Ş.", plan="deneme", sube_kotasi=10, kullanici_kotasi=1)
    ensure_schema()

    tek_kullanici = pd.DataFrame([{"Web Kullanıcı": "ik1", "Sorumlu": "TEST"}])
    write_sheet("Mail_Listesi", tek_kullanici, tenant_id="KUCUKFIRMA2")

    iki_kullanici = pd.DataFrame([
        {"Web Kullanıcı": "ik1", "Sorumlu": "TEST"},
        {"Web Kullanıcı": "ik2", "Sorumlu": "TEST2"},
    ])
    with pytest.raises(KotaAsimiHatasi):
        write_sheet("Mail_Listesi", iki_kullanici, tenant_id="KUCUKFIRMA2")


def test_kota_sinirinda_tam_dolu_yazma_kabul_edilir(kota_ortami):
    """Kota=3 iken tam 3 şube yazmak İZİN VERİLMELİ (sınırda hata olmamalı)."""
    from services.tenant_registry import create_tenant
    from services.input_data_access import ensure_schema, write_sheet, read_sheet

    create_tenant("TAMDOLU", "Tam Dolu A.Ş.", plan="temel", sube_kotasi=3, kullanici_kotasi=5)
    ensure_schema()
    magaza_3 = pd.DataFrame([
        {"MağazaID": f"M00{i}", "Mağaza": f"ŞUBE{i}"} for i in range(1, 4)
    ])
    yazilan = write_sheet("Dim_Magaza", magaza_3, tenant_id="TAMDOLU")
    assert yazilan == 3
    assert len(read_sheet("Dim_Magaza", tenant_id="TAMDOLU")) == 3


def test_kayitli_olmayan_kiracida_kota_uygulanmaz(kota_ortami):
    """tenant_registry'de HİÇ kaydı olmayan bir tenant_id (ör. tek kiracılı
    eski kurulum) için kota kontrolü SESSİZCE atlanmalı — geriye dönük
    uyumluluk. Sınırsız şube eklenebilmeli."""
    from services.input_data_access import ensure_schema, write_sheet

    ensure_schema()
    cok_magaza = pd.DataFrame([
        {"MağazaID": f"M{i:03d}", "Mağaza": f"ŞUBE{i}"} for i in range(1, 51)
    ])
    yazilan = write_sheet("Dim_Magaza", cok_magaza, tenant_id="KAYITSIZ_KIRACI")
    assert yazilan == 50


def test_farkli_kiracilarin_kotasi_birbirinden_bagimsiz(kota_ortami):
    """A firmasının kotasını doldurması, B firmasının kendi kotasını
    kullanmasını ENGELLEMEMELİ (kota kiracı bazlı, global değil)."""
    from services.tenant_registry import create_tenant
    from services.input_data_access import ensure_schema, write_sheet, read_sheet

    create_tenant("FIRMAA", "Firma A", sube_kotasi=1, kullanici_kotasi=5)
    create_tenant("FIRMAB", "Firma B", sube_kotasi=1, kullanici_kotasi=5)
    ensure_schema()

    write_sheet("Dim_Magaza", pd.DataFrame([{"MağazaID": "M001", "Mağaza": "A-ŞUBE"}]), tenant_id="FIRMAA")
    write_sheet("Dim_Magaza", pd.DataFrame([{"MağazaID": "M001", "Mağaza": "B-ŞUBE"}]), tenant_id="FIRMAB")

    assert len(read_sheet("Dim_Magaza", tenant_id="FIRMAA")) == 1
    assert len(read_sheet("Dim_Magaza", tenant_id="FIRMAB")) == 1
