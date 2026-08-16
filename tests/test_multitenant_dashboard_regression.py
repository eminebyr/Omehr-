from __future__ import annotations

"""KRİTİK ÇOK-KİRACILI REGRESYON TESTİ.

services/dashboard_model.py'nin active_people() ve detail tablosu
filtreleri, önceden orijinal firmanın 4 gerçek bölge sorumlusu ismini
(REGIONS sabiti) SERT bir izin listesi olarak kullanıyordu — başka
HERHANGİ bir kiracının personeli, kendi bölge sorumlusunun adı bu
listede olmadığı için SESSİZCE "aktif değil" sayılıyor, Genel Özet/
CEO Özeti panosundaki detay tablolarını boşaltıyordu. Bizzat kanıtlandı:
2 aktif kişiden 0'ı aktif sayılıyordu.

Bu test, GERÇEK, orijinal listede OLMAYAN bölge sorumlusu isimleriyle
çalışıp çalışmadığını doğrulayarak bu hatanın bir daha SESSİZCE geri
gelmesini engeller.
"""

import pandas as pd


def test_active_people_does_not_filter_by_hardcoded_region_names():
    from services.dashboard_model import active_people
    df = pd.DataFrame([
        {"İsim Soyisim": "Başka Firma Çalışanı 1", "Bölge Sorumlusu": "TAMAMEN FARKLI BİR MÜDÜR", "İşten Çıkış": None},
        {"İsim Soyisim": "Başka Firma Çalışanı 2", "Bölge Sorumlusu": "İKİNCİ FARKLI MÜDÜR", "İşten Çıkış": None},
    ])
    sonuc = active_people(df)
    assert len(sonuc) == 2, (
        f"REGRESYON: {len(sonuc)}/2 kişi aktif sayıldı — active_people() muhtemelen "
        "yeniden sabit bir bölge/isim listesine bağımlı hale gelmiş."
    )


def test_build_dashboard_model_works_for_tenant_with_unrelated_region_names():
    from services.dashboard_model import build_dashboard_model
    from pathlib import Path

    sheets = pd.read_excel(
        Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx",
        sheet_name=None,
    )
    for sheet in ("Fact_Mevcut", "Fact_Norm"):
        if "Bölge Sorumlusu" in sheets[sheet].columns:
            sheets[sheet]["Bölge Sorumlusu"] = "BAŞKA KİRACININ MÜDÜRÜ"

    fm, detail, stores, kpis = build_dashboard_model(
        sheets, Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "gecici_yok.json"
    )
    assert len(fm) > 500, (
        f"REGRESYON: farklı bölge sorumlusu isimleriyle aktif personel sayısı {len(fm)} "
        "(500'den fazla olmalıydı) — muhtemelen sabit bir isim listesi geri gelmiş."
    )
    assert not detail.empty, "REGRESYON: detay tablosu boş — muhtemelen sabit bölge filtresi geri gelmiş."


def test_dashboard_model_produces_identical_results_for_original_tenant():
    """Düzeltmenin ORİJİNAL (gerçek) kiracı için hiçbir regresyona yol
    açmadığını doğrular — yalnız BAŞKA kiracılar için değil."""
    from services.dashboard_model import build_dashboard_model
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sheets = pd.read_excel(root / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", sheet_name=None)
    fm, detail, stores, kpis = build_dashboard_model(sheets, root / "reference" / "NORM_KAPSAM_BAZI.json")
    assert kpis["Aktif Mevcut"] == 596
    assert kpis["Toplam Norm"] == 607
