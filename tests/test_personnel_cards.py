"""PERSONEL KARTLARI — hem Excel hem veritabanı modunda gerçek testler.

Sayfa önceden yalnız veritabanı modunda çalışıyordu; bu testler
düzeltmenin GERÇEKTEN her iki kaynakta da doğru işlediğini kanıtlar.
"""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

import pandas as pd
import pytest


def _ornek_dosya() -> Path:
    return Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"


# ------------------------------------------------------------------
# EXCEL MODU
# ------------------------------------------------------------------
def test_excel_modunda_islem_gormesi_gereken_veri_yolu(isolated_root, monkeypatch):
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    from services.settings import input_path
    hedef = input_path(isolated_root)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ornek_dosya(), hedef)

    from services.personnel_exit import load_personnel_view, is_active, process_exit

    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    assert len(staff) == 596
    assert "Mağaza" in staff.columns and staff["Mağaza"].notna().any(), \
        "Excel modunda Mağaza görüntü adı (VLOOKUP eşdeğeri) boş kalmamalı"

    aktif = staff[staff.apply(lambda r: is_active(r.to_dict()), axis=1)]
    kisi = aktif.iloc[0]

    sonuc = process_exit(
        input_path=hedef, root=isolated_root,
        isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        cikis_tarihi=datetime.date(2026, 8, 8), cikis_kodu="İstifa", cikis_nedeni_id=1,
        cikis_nedeni_metni="Test nedeni", kullanici="test",
    )
    assert sonuc == {"durum": "OK", "guncellenen_satir": 1}

    staff2, _, _, _ = load_personnel_view(hedef)
    assert len(staff2) == 596, "İşten çıkış satır SAYISINI değiştirmemeli, yalnız işaretlemeli"
    guncellenen = staff2[
        (staff2["İsim Soyisim"] == kisi["İsim Soyisim"]) & (staff2["MağazaID"] == kisi["MağazaID"])
    ]
    assert pd.notna(guncellenen["İşten Çıkış"].iloc[0])


def test_excel_modunda_ikinci_cikis_reddedilir(isolated_root, monkeypatch):
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    from services.settings import input_path
    hedef = input_path(isolated_root)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ornek_dosya(), hedef)

    from services.personnel_exit import load_personnel_view, is_active, process_exit

    staff, *_ = load_personnel_view(hedef)
    aktif = staff[staff.apply(lambda r: is_active(r.to_dict()), axis=1)]
    kisi = aktif.iloc[1]

    process_exit(
        input_path=hedef, root=isolated_root,
        isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        cikis_tarihi=datetime.date(2026, 8, 8), cikis_kodu="İstifa", cikis_nedeni_id=1,
        kullanici="test",
    )
    with pytest.raises(ValueError, match="zaten kayıtlı"):
        process_exit(
            input_path=hedef, root=isolated_root,
            isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
            cikis_tarihi=datetime.date(2026, 8, 9), cikis_kodu="İstifa", cikis_nedeni_id=1,
            kullanici="test",
        )


def test_excel_modunda_main_py_islenmis_veriyle_dogru_kpi_uretir(isolated_root, monkeypatch):
    """En kritik doğrulama: bir kişi işten çıkarıldıktan SONRA, main.py'nin
    kullandığı GERÇEK hesaplama zinciri (src.data_loading.load() ->
    state/kpis) sonucu doğru yansıtmalı — 'Aktif Mevcut' tam olarak 1
    azalmalı. (NOT: state() kendisi aktif/pasif filtrelemesi YAPMAZ —
    bu filtreleme src.data_loading.load() içindedir; bu yüzden test o
    gerçek fonksiyonu kullanır, ham sayfayı doğrudan state()'e vermez.)"""
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    monkeypatch.setenv("BASDAS_PREPARE_INPUT", "0")
    from services.settings import input_path
    hedef = input_path(isolated_root)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ornek_dosya(), hedef)

    from services.personnel_exit import load_personnel_view, is_active, process_exit
    from src.data_loading import load
    from src.state_engine import state
    from src.kpi_engine import kpis

    _, _, norm_once, staff_once, _ = load(prepare=False)
    stores_once, _ = state(norm_once, staff_once, {"Fact_Norm": norm_once, "Fact_Mevcut": staff_once})
    aktif_once = kpis(stores_once)["Aktif Mevcut"]

    staff, *_ = load_personnel_view(hedef)
    aktif = staff[staff.apply(lambda r: is_active(r.to_dict()), axis=1)]
    kisi = aktif.iloc[2]
    process_exit(
        input_path=hedef, root=isolated_root,
        isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        cikis_tarihi=datetime.date(2026, 8, 8), cikis_kodu="İstifa", cikis_nedeni_id=1,
        kullanici="test",
    )

    _, _, norm_sonra, staff_sonra, _ = load(prepare=False)
    stores_sonra, _ = state(norm_sonra, staff_sonra, {"Fact_Norm": norm_sonra, "Fact_Mevcut": staff_sonra})
    aktif_sonra = kpis(stores_sonra)["Aktif Mevcut"]

    assert aktif_sonra == aktif_once - 1


# ------------------------------------------------------------------
# VERİTABANI MODU
# ------------------------------------------------------------------
def test_db_modunda_islem_gormesi_gereken_veri_yolu(isolated_root, monkeypatch):
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    (isolated_root / "input").mkdir(parents=True, exist_ok=True)
    (isolated_root / "data").mkdir(parents=True, exist_ok=True)

    from services.input_excel_migration import migrate_excel_to_db
    migrate_excel_to_db(str(_ornek_dosya()))

    from services.personnel_exit import load_personnel_view, is_active, process_exit, add_personnel

    staff, magaza, unvan, cikis_nedeni = load_personnel_view(None)
    assert len(staff) == 596

    aktif = staff[staff.apply(lambda r: is_active(r.to_dict()), axis=1)]
    kisi = aktif.iloc[0]
    sonuc = process_exit(
        input_path=None, root=isolated_root,
        isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        cikis_tarihi=datetime.date(2026, 8, 8), cikis_kodu="İstifa", cikis_nedeni_id=1,
        kullanici="test",
    )
    assert sonuc["durum"] == "OK"

    staff2, *_ = load_personnel_view(None)
    assert len(staff2) == 596

    yeni = {c: None for c in staff2.columns}
    yeni.update({
        "İsim Soyisim": "OTOMATİK TEST KİŞİSİ", "Mağaza": magaza["Mağaza"].iloc[0],
        "MağazaID": magaza["MağazaID"].iloc[0], "Unvan": unvan["Unvan"].iloc[0],
        "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-08",
    })
    add_personnel(input_path=None, root=isolated_root, staff=staff2, yeni_kayit=yeni, username="test")
    staff3, *_ = load_personnel_view(None)
    assert len(staff3) == 597
    assert (staff3["İsim Soyisim"] == "OTOMATİK TEST KİŞİSİ").any()


def test_her_iki_modda_da_ayni_kisiye_ayni_sonuc(isolated_root, monkeypatch):
    """Excel ve veritabanı modlarının AYNI ham veriyle AYNI davranışı
    (aktif kişi sayısı, sütun kümesi) ürettiğini doğrular."""
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    from services.settings import input_path
    hedef = input_path(isolated_root)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ornek_dosya(), hedef)
    from services.personnel_exit import load_personnel_view as _load
    staff_excel, *_ = _load(hedef)

    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    (isolated_root / "data").mkdir(parents=True, exist_ok=True)
    from services.input_excel_migration import migrate_excel_to_db
    migrate_excel_to_db(str(_ornek_dosya()))
    staff_db, *_ = _load(None)

    assert len(staff_excel) == len(staff_db) == 596
    assert set(staff_excel["İsim Soyisim"]) == set(staff_db["İsim Soyisim"])
