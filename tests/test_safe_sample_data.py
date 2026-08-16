from __future__ import annotations

"""ORNEK_VERI_GUVENLI/ — güvenli örnek veri regresyon testi.

Bu klasördeki dosya, GERÇEKTEN tamamen uydurma isim/e-posta/şifre
içermesi GARANTİ edilmesi gereken, kullanıcıya sunulan TEK örnek
veridir (eski ORNEK_TEST_VERISI/ gerçek veri içerdiği için paketten
kalıcı olarak hariç tutuldu). Bu test, ileride biri bu dosyayı
yanlışlıkla gerçek veriyle DEĞİŞTİRİRSE bunu HEMEN fark eder.
"""

import pandas as pd


def test_safe_sample_data_contains_no_real_looking_names():
    df = pd.read_excel("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", sheet_name="Fact_Mevcut")
    bilinen_gercek_isimler = {"ŞEYMA ASLAN", "KEVSER ARSLAN", "BİLGE AKŞİT", "EVİN MEN"}
    bulunan = bilinen_gercek_isimler.intersection(set(df["İsim Soyisim"].astype(str)))
    assert not bulunan, f"REGRESYON: güvenli örnek veride GERÇEK isimler bulundu: {bulunan}"

    bilinen_gercek_bolgeler = {"ALİ ÇELİK", "DERYA YARDIMCI", "ERTAN TEKİ"}
    bulunan_bolge = bilinen_gercek_bolgeler.intersection(set(df["Bölge Sorumlusu"].astype(str)))
    assert not bulunan_bolge, f"REGRESYON: güvenli örnek veride GERÇEK bölge müdürü isimleri bulundu: {bulunan_bolge}"


def test_safe_sample_data_contains_no_real_domain():
    df = pd.read_excel("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", sheet_name="Mail_Listesi")
    assert not df["E-posta"].astype(str).str.contains("basdasmarket", case=False).any(), (
        "REGRESYON: güvenli örnek veride gerçek şirket domaini bulundu."
    )


def test_safe_sample_data_produces_correct_kpis():
    import sys
    sys.path.insert(0, ".")
    from src.state_engine import state
    from src.kpi_engine import kpis

    sheets = pd.read_excel("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", sheet_name=None)
    st, detail = state(sheets["Fact_Norm"], sheets["Fact_Mevcut"], sheets)
    kp = kpis(st)
    assert kp["Aktif Mevcut"] == 596
    assert kp["Toplam Norm"] == 607
    assert kp["Norm Eksiği"] == 49
    assert kp["Norm Fazlası"] == 23


def test_safe_sample_data_is_shipped_but_real_data_is_not(tmp_path):
    from tools.build_clean_package import build_clean_zip
    from pathlib import Path
    import zipfile

    hedef = tmp_path / "test_paket.zip"
    build_clean_zip(Path("."), hedef)
    with zipfile.ZipFile(hedef) as z:
        isimler = z.namelist()

    assert any(n.startswith("ORNEK_VERI_GUVENLI/") for n in isimler), (
        "REGRESYON: güvenli örnek veri pakete dahil edilmiyor."
    )
    assert not any(n.startswith("input/") or n.startswith("ORNEK_TEST_VERISI/") for n in isimler), (
        "REGRESYON: GERÇEK veri içeren eski klasörler pakete sızmış."
    )
