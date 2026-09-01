import pandas as pd

from services.sales_root_cause import build_sales_root_cause


def _base_sheets():
    return {
        "Aylık Operasyon KPI": pd.DataFrame([
            {"Ay": "2026-08", "MagazaID": "M1", "Mağaza": "A", "Aylık Fiş": 1000, "Aylık Ciro": 100_000, "Ort. Sepet": 100},
            {"Ay": "2026-09", "MagazaID": "M1", "Mağaza": "A", "Aylık Fiş": 900, "Aylık Ciro": 90_000, "Ort. Sepet": 100},
        ]),
        "Fazla Mesai": pd.DataFrame([{"Ay": "2026-09", "MagazaID": "M1", "Fazla Mesai Saat": 10}]),
        "Devamsızlık": pd.DataFrame([{"Ay": "2026-09", "MagazaID": "M1", "Fiili Kayıp FTE": 1}]),
        "İş Yükü Endeksi": pd.DataFrame([{"MagazaID": "M1", "İş Yükü Endeksi": 80}]),
        "Fire ve İade": pd.DataFrame([{"MagazaID": "M1", "Fire Oranı %": 2}]),
        "Performans": pd.DataFrame([{"Ay": "2026-09", "MagazaID": "M1", "Yönetici Puanı": 70}]),
    }


def test_full_norm_cannot_be_blanked_as_personnel_shortage():
    stores = pd.DataFrame([{"MağazaID": "M1", "Mağaza": "A", "Norm": 10, "Mevcut": 10}])
    targets = [{"period": "2026-09", "store_id": "M1", "sales_target": 120_000}]
    result, latest, previous = build_sales_root_cause(sheets=_base_sheets(), stores=stores, targets=targets)
    row = result.iloc[0]
    assert (latest, previous) == ("2026-09", "2026-08")
    assert round(row["Hedef Gerçekleşme %"], 1) == 75.0
    assert row["Otomatik Kök Neden"] == "TAM KADRO / DÜŞÜK SATIŞ"
    assert row["Personel İddiası"] == "Desteklenmiyor"


def test_people_effect_requires_operational_evidence():
    stores = pd.DataFrame([{"MağazaID": "M1", "Mağaza": "A", "Norm": 10, "Mevcut": 9}])
    targets = [{"period": "2026-09", "store_id": "M1", "sales_target": 120_000}]
    result, _, _ = build_sales_root_cause(sheets=_base_sheets(), stores=stores, targets=targets)
    assert result.iloc[0]["Otomatik Kök Neden"] == "MÜŞTERİ TRAFİĞİ DÜŞÜŞÜ"
    assert result.iloc[0]["Personel İddiası"] == "Desteklenmiyor"
