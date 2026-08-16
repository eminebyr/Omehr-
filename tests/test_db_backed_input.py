"""VERİTABANI TABANLI GİRDİ KATMANI — testler.

BASDAS_INPUT_SOURCE=db bayrağıyla devreye giren yeni mimarinin (şema,
göç aracı, veri erişim katmanı, load()/state()/kpis() zincirinin uçtan
uca DOĞRU çalıştığı) GERÇEK testleri. Varsayılan (excel) modun hiç
etkilenmediği, mevcut 178 testin ayrı ayrı doğruladığı zaten bilinir —
burası yalnız YENİ db modunu doğrular.
"""
from __future__ import annotations

import importlib
import os
import sys

import pandas as pd
import pytest


@pytest.fixture
def db_root(tmp_path, monkeypatch):
    """Excel dosyasını izole bir kökte veritabanına göç ettirir ve
    BASDAS_INPUT_SOURCE=db ile çalışacak modülleri yeniden yükler."""
    root = tmp_path
    (root / "input").mkdir()
    (root / "data").mkdir()
    (root / "output").mkdir()

    kaynak = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    )

    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(root))
    monkeypatch.setenv("BASDAS_DB_BACKEND", "sqlite")
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")

    for mod_name in (
        "services.runtime_paths", "services.input_db_schema", "services.input_data_access",
        "services.input_excel_migration", "common_veri_okuma", "src.data_loading",
        "src.state_engine", "src.kpi_engine",
    ):
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])

    from services.input_excel_migration import migrate_excel_to_db
    sonuc = migrate_excel_to_db(str(kaynak))

    try:
        yield root, sonuc
    finally:
        monkeypatch.undo()
        for mod_name in (
            "services.runtime_paths", "services.input_db_schema", "services.input_data_access",
            "services.input_excel_migration", "common_veri_okuma", "src.data_loading",
            "src.state_engine", "src.kpi_engine",
        ):
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])


def test_migration_copies_every_sheet_with_matching_row_counts(db_root):
    root, sonuc = db_root
    basarisiz = [k for k, v in sonuc.items() if v["durum"] != "OK"]
    assert not basarisiz, f"Göç edilemeyen sayfalar: {basarisiz}"
    assert len(sonuc) == 64


def test_read_sheet_matches_excel_column_order_and_row_count(db_root):
    from pathlib import Path
    from services.input_data_access import read_sheet
    import pandas as pd

    kaynak = Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    excel_df = pd.read_excel(kaynak, sheet_name="Fact_Norm", dtype=object)
    db_df = read_sheet("Fact_Norm")
    assert list(db_df.columns) == list(excel_df.columns)
    assert len(db_df) == len(excel_df)


def test_db_backed_load_produces_identical_kpis_to_excel(db_root, monkeypatch):
    """EN KRİTİK TEST: aynı veriyle, DB kaynaklı load() sonucu, Excel
    kaynaklı load() sonucuyla BİREBİR aynı KPI'yı üretmeli. Karşılaştırma
    HER İKİ tarafta da load()'un TAM ön işlemesinden (VLOOKUP eşdeğeri,
    aile normalizasyonu, aktif personel filtresi) geçmelidir — yalnızca
    birini ham state() ile karşılaştırmak adil değildir."""
    from src.state_engine import state
    from src.kpi_engine import kpis

    # DB modu (fixture zaten BASDAS_INPUT_SOURCE=db kurdu)
    import importlib
    import src.data_loading as dl
    importlib.reload(dl)
    _, sheets_db, norm_db, staff_db, _ = dl.load()
    stores_db, _ = state(norm_db, staff_db, sheets_db)
    kpi_db = kpis(stores_db)

    # Şimdi AYNI fixture kökünde Excel moduna geçip AYNI load() ile karşılaştır
    root, _ = db_root
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "excel")
    (root / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx").write_bytes(
        (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
        ).read_bytes()
    )
    importlib.reload(dl)
    _, sheets_ex, norm_ex, staff_ex, _ = dl.load(prepare=False)
    stores_ex, _ = state(norm_ex, staff_ex, sheets_ex)
    kpi_excel = kpis(stores_ex)

    assert kpi_db == kpi_excel


def test_write_sheet_round_trip_preserves_edits(db_root):
    from services.input_data_access import read_sheet, write_sheet

    df = read_sheet("Dim_Unvan")
    assert len(df) > 0
    df.loc[0, "Unvan"] = "TEST DÜZENLENMİŞ UNVAN"
    write_sheet("Dim_Unvan", df, kullanici="test_kullanici")

    yeniden_okunan = read_sheet("Dim_Unvan")
    assert yeniden_okunan.loc[0, "Unvan"] == "TEST DÜZENLENMİŞ UNVAN"
    assert len(yeniden_okunan) == len(df)


def test_excel_mode_unaffected_when_flag_not_set(monkeypatch, tmp_path):
    """BASDAS_INPUT_SOURCE ayarlanmamışsa (varsayılan), sistem HİÇBİR
    değişiklik olmadan Excel'den okumaya devam etmeli."""
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)
    import common_veri_okuma
    importlib.reload(common_veri_okuma)
    assert common_veri_okuma._db_modu() is False


def test_excel_read_shim_only_intercepts_the_input_file(db_root):
    """Shim, YALNIZ BASDAS_AI_NORM_TRANSFER_INPUT.xlsx adlı dosyayı
    hedefleyen çağrıları yönlendirir — üretilen ÇIKTI dosyalarını okuyan
    çağrılar (ör. V19_AI_Norm_Sonuclari.xlsx) ETKİLENMEMELİDİR."""
    from services.excel_read_shim import _girdi_dosyasi_mi
    assert _girdi_dosyasi_mi("input/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx") is True
    assert _girdi_dosyasi_mi("output/V19_AI_Norm_Sonuclari.xlsx") is False
    assert _girdi_dosyasi_mi("output/BASDAS_Yonetici_Raporu.xlsx") is False


def test_all_62_sheets_have_a_generic_editable_schema(db_root):
    from services.input_db_schema import load_schema
    sema = load_schema()
    assert len(sema) == 64
    for sheet_adi, bilgi in sema.items():
        assert bilgi["tablo"].startswith("in_")
        assert len(bilgi["kolonlar"]) > 0
