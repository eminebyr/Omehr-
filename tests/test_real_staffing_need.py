from __future__ import annotations

import pandas as pd

from services.real_staffing_need import build_real_staffing_need


def _detail() -> pd.DataFrame:
    return pd.DataFrame([
        {"Mağaza": "BALÇOVA", "Bölge Sorumlusu": "BATI", "Unvan": "KASİYER", "Norm Kadro": 10, "Aktif Mevcut": 7, "Norm Eksiği": 3, "Norm Fazlası": 0},
        {"Mağaza": "BASMANE", "Bölge Sorumlusu": "MERKEZ", "Unvan": "KASİYER", "Norm Kadro": 6, "Aktif Mevcut": 8, "Norm Eksiği": 0, "Norm Fazlası": 2},
    ])


def test_low_history_never_publishes_a_certain_hiring_decision():
    sheets = {
        "Günlük Operasyon": pd.DataFrame([
            {"Tarih": "2026-09-01", "Mağaza": "BALÇOVA", "İş Yükü Endeksi": 90},
            {"Tarih": "2026-09-02", "Mağaza": "BALÇOVA", "İş Yükü Endeksi": 92},
        ])
    }

    rows, kpis = build_real_staffing_need(_detail(), sheets=sheets)

    bal = rows.loc[rows["Mağaza"].eq("BALÇOVA")].iloc[0]
    assert bal["Norm Eksiği"] == 3
    assert bal["Transferle Kapatılabilir"] == 2
    assert bal["Karar"].startswith("VERİ YETERSİZ")
    assert bal["Güven Düzeyi"] == "Düşük"
    assert kpis["Norm Eksiği"] == 3
    assert kpis["Transferle Kapatılabilir"] == 2
    assert kpis["Sınıflandırılan Açık"] == 3


def test_sufficient_history_and_pressure_produce_explainable_hiring_need():
    daily = pd.DataFrame([
        {"Tarih": f"2026-08-{day:02d}", "Mağaza": "BALÇOVA", "İş Yükü Endeksi": 85}
        for day in range(1, 32)
    ])
    sheets = {
        "Günlük Operasyon": daily,
        "Fazla Mesai": pd.DataFrame([{"Ay": "2026-08", "Mağaza": "BALÇOVA", "Fazla Mesai Saat": 45}]),
    }

    rows, kpis = build_real_staffing_need(_detail(), sheets=sheets)

    bal = rows.loc[rows["Mağaza"].eq("BALÇOVA")].iloc[0]
    assert bal["Transferle Kapatılabilir"] == 2
    assert bal["Gerçek İşe Alım İhtiyacı"] == 1
    assert bal["Karar"] == "İŞE ALIM"
    assert "fazla mesai" in bal["Neden"].lower()
    assert bal["Güven Düzeyi"] in {"Orta", "Yüksek"}
    assert kpis["Gerçek İşe Alım İhtiyacı"] == 1


def test_classification_parts_never_exceed_the_norm_gap():
    rows, _ = build_real_staffing_need(_detail(), sheets={})
    bal = rows.loc[rows["Mağaza"].eq("BALÇOVA")].iloc[0]
    parts = (
        bal["Transferle Kapatılabilir"]
        + bal["Geçici Operasyonel Açık"]
        + bal["Norm Revizyonu Adayı"]
        + bal["Gerçek İşe Alım İhtiyacı"]
        + bal["Kararsız Veri Açığı"]
    )
    assert parts == bal["Norm Eksiği"]


def test_latest_operational_row_is_selected_by_period_not_excel_order():
    sheets = {
        "Günlük Operasyon": pd.DataFrame([
            {"Tarih": f"2026-09-{day:02d}", "Mağaza": "BALÇOVA"}
            for day in range(1, 31)
        ]),
        "Fazla Mesai": pd.DataFrame([
            {"Ay": "2026-09", "Mağaza": "BALÇOVA", "Fazla Mesai Saat": 45},
            {"Ay": "2026-08", "Mağaza": "BALÇOVA", "Fazla Mesai Saat": 0},
        ]),
    }

    rows, _ = build_real_staffing_need(_detail(), sheets=sheets)

    bal = rows.loc[rows["Mağaza"].eq("BALÇOVA")].iloc[0]
    assert bal["Gerçek İşe Alım İhtiyacı"] == 1
    assert "45" in bal["Neden"]


def test_sales_pressure_is_derived_from_separate_target_sheet():
    sheets = {
        "Aylık Operasyon KPI": pd.DataFrame([
            {"Ay": "2026-07", "Mağaza": "BALÇOVA", "Aylık Ciro": 80_000},
            {"Ay": "2026-08", "Mağaza": "BALÇOVA", "Aylık Ciro": 105_000},
            {"Ay": "2026-09", "Mağaza": "BALÇOVA", "Aylık Ciro": 110_000},
        ]),
        "Satış Hedefi": pd.DataFrame([
            {"Ay": "2026-07", "Mağaza": "BALÇOVA", "Hedef Ciro": 100_000},
            {"Ay": "2026-08", "Mağaza": "BALÇOVA", "Hedef Ciro": 100_000},
            {"Ay": "2026-09", "Mağaza": "BALÇOVA", "Hedef Ciro": 100_000},
        ]),
    }

    rows, _ = build_real_staffing_need(_detail(), sheets=sheets)

    bal = rows.loc[rows["Mağaza"].eq("BALÇOVA")].iloc[0]
    assert bal["Gerçek İşe Alım İhtiyacı"] == 1
    assert "Satış hedef gerçekleşmesi %110" in bal["Neden"]
