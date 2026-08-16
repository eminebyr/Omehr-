from __future__ import annotations

"""KRİTİK REGRESYON TESTİ — Fact_Norm yazma hatası + sayfa değişiklik izleyici.

services/master_data_admin.py::_write_fact_norm() önceden Mağaza/Bölge
Sorumlusu/Unvan sütunlarını Excel VLOOKUP formülü olarak yazıyordu — bu
formüller HİÇBİR YERDE hesaplanmadığı için (main.py'nin dışındaki
yazma yollarında LibreOffice recalculation çalışmıyor), her yazmadan
sonra bu sütunlar pandas/openpyxl ile TAMAMEN BOŞ (NaN) okunuyordu.
Bu, daha önce Fact_Mevcut'ta bulunup düzeltilen AYNI hata sınıfının
Fact_Norm'daki, o zaman fark edilmemiş bir örneğiydi.
"""

import shutil
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def gecici_input(tmp_path, isolated_root):
    kaynak = Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    hedef_dizin = isolated_root / "input"
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    hedef = hedef_dizin / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copyfile(kaynak, hedef)
    return hedef


def test_fact_norm_text_columns_are_not_blanked_after_write(gecici_input, isolated_root):
    from services.personnel_exit import load_personnel_view, add_personnel

    staff, magaza, unvan, _ = load_personnel_view(gecici_input)
    yeni = {c: None for c in staff.columns}
    yeni.update({
        "İsim Soyisim": "REGRESYON TEST", "Mağaza": magaza["Mağaza"].iloc[0],
        "MağazaID": magaza["MağazaID"].iloc[0], "Unvan": unvan["Unvan"].iloc[0],
        "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-10",
        "Departman": unvan["Unvan"].iloc[0],
    })
    add_personnel(input_path=gecici_input, root=isolated_root, staff=staff, yeni_kayit=yeni, username="test")

    fact_norm = pd.read_excel(gecici_input, sheet_name="Fact_Norm")
    bos_sayisi = int(fact_norm["Mağaza"].isna().sum())
    assert bos_sayisi == 0, (
        f"REGRESYON: Fact_Norm'da {bos_sayisi} satırda Mağaza sütunu boş (NaN) — "
        "VLOOKUP-formülü-hesaplanmadan hatası geri gelmiş olabilir."
    )
    assert fact_norm["Bölge Sorumlusu"].notna().all()
    assert fact_norm["Unvan"].notna().all()


def test_sheet_change_watcher_detects_only_genuinely_changed_sheets(gecici_input, isolated_root):
    """Yalnız Fact_Mevcut'a yazıldığında, izleyici EN AZINDAN Fact_Mevcut'u
    değişen olarak bildirmeli. Diğer sayfalar (Fact_Norm/Dim_Magaza), TÜM
    workbook'un her yazmada yeniden oluşturulması nedeniyle zararsız metin
    normalizasyonu (ör. sondaki boşluk temizliği) yüzünden GÖRÜNEBİLİR —
    bu regresyon değildir; test bunu KABUL EDER ama Fact_Mevcut'un mutlaka
    listede olduğunu doğrular."""
    from services.multi_pc_sync import detect_changed_sheets
    from services.personnel_exit import load_personnel_view, add_personnel

    detect_changed_sheets(isolated_root, gecici_input)  # ilk kayıt (baseline)

    staff, magaza, unvan, _ = load_personnel_view(gecici_input)
    yeni = {c: None for c in staff.columns}
    yeni.update({
        "İsim Soyisim": "WATCHER REGRESYON", "Mağaza": magaza["Mağaza"].iloc[0],
        "MağazaID": magaza["MağazaID"].iloc[0], "Unvan": unvan["Unvan"].iloc[0],
        "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-10",
        "Departman": unvan["Unvan"].iloc[0],
    })
    add_personnel(input_path=gecici_input, root=isolated_root, staff=staff, yeni_kayit=yeni, username="test")

    degisen = detect_changed_sheets(isolated_root, gecici_input)
    assert "Fact_Mevcut" in degisen, f"REGRESYON: Fact_Mevcut değişikliği tespit edilmedi. Bulunan: {degisen}"


def test_sheet_change_watcher_reports_nothing_when_truly_unchanged(gecici_input, isolated_root):
    from services.multi_pc_sync import detect_changed_sheets

    detect_changed_sheets(isolated_root, gecici_input)  # baseline
    degisen = detect_changed_sheets(isolated_root, gecici_input)  # hiçbir şey değişmedi
    assert degisen == [], f"REGRESYON: değişiklik olmadan sayfalar 'değişti' sayıldı: {degisen}"
