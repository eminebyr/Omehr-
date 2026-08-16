"""KOTA UYGULAMASI — sube_kotasi ve kullanici_kotasi gerçekten uygulanıyor mu.

DÜZELTME: bu alanlar tenant_registry şemasında TANIMLIYDI ama hiçbir
kod yolunda KONTROL EDİLMİYORDU — bir kiracı sınırsız mağaza/kullanıcı
ekleyebiliyordu. Bu testler gerçek zorlama mantığını doğrular.
"""
from __future__ import annotations

import importlib
import sys

import pandas as pd
import pytest


@pytest.fixture
def kota_ortami(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    for mod in ("services.runtime_paths", "services.tenant_registry", "services.tenant_context", "services.security"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])

    from services.tenant_registry import create_tenant
    create_tenant("KUCUKFIRMA", "Küçük Firma A.Ş.", plan="deneme", sube_kotasi=2, kullanici_kotasi=1)

    yield tmp_path

    monkeypatch.undo()
    for mod in ("services.runtime_paths", "services.tenant_registry", "services.tenant_context", "services.security"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])


def test_kullanici_kotasi_asilinca_yeni_kullanici_reddedilir(kota_ortami):
    from services.security import set_password

    set_password("ilkkullanici", "GucluSifre!2026", tenant_id="KUCUKFIRMA")
    with pytest.raises(ValueError, match="kullanıcı"):
        set_password("ikincikullanici", "GucluSifre!2026", tenant_id="KUCUKFIRMA")


def test_ayni_kullanicinin_sifresini_sifirlamak_kotaya_takilmaz(kota_ortami):
    from services.security import set_password

    set_password("tekkullanici", "GucluSifre!2026", tenant_id="KUCUKFIRMA")
    # aynı kullanıcının şifresini TEKRAR ayarlamak (sıfırlama) kota
    # ihlali sayılmamalı — zaten var olan bir kullanıcı, yeni değil.
    set_password("tekkullanici", "YeniSifre!2027", tenant_id="KUCUKFIRMA")


def test_kota_tanimsiz_kiracida_kontrolsuz_calisir(kota_ortami):
    """Tenant registry'de kaydı olmayan (tek kiracılı/eski kurulum)
    bir kiracı için kota kontrolü atlanmalı — geriye dönük uyumluluk."""
    from services.security import set_password

    set_password("kullanici1", "GucluSifre!2026", tenant_id="KAYITSIZ_FIRMA")
    set_password("kullanici2", "GucluSifre!2026", tenant_id="KAYITSIZ_FIRMA")
    set_password("kullanici3", "GucluSifre!2026", tenant_id="KAYITSIZ_FIRMA")


def test_sube_kotasi_asilinca_kayit_reddedilir(kota_ortami, tmp_path):
    from services.master_data_admin import save_tables, read_tables
    from pathlib import Path
    import shutil

    kaynak = Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    (tmp_path / "input").mkdir(exist_ok=True)
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copy2(kaynak, hedef)

    import os
    os.environ["BASDAS_TENANT"] = "KUCUKFIRMA"
    try:
        tables = read_tables(hedef)
        # KUCUKFIRMA kotası 2 mağaza — gerçek örnek veride 53 mağaza var,
        # bu yüzden olduğu gibi kaydetmeye çalışmak reddedilmeli.
        assert len(tables["Dim_Magaza"]) > 2
        with pytest.raises(ValueError, match="şube"):
            save_tables(tmp_path, hedef, tables, username="test")
    finally:
        os.environ.pop("BASDAS_TENANT", None)
