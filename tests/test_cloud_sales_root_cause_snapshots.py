from pathlib import Path

import pandas as pd

from services.cloud_module_snapshots import build_module_snapshots


def test_sales_root_cause_sources_are_exported(tmp_path: Path) -> None:
    sheets = {
        "Aylık Operasyon KPI": pd.DataFrame([{"Ay": "2026-09", "MagazaID": "M1", "Aylık Ciro": 100}]),
        "Fire ve İade": pd.DataFrame([{"MagazaID": "M1", "Fire Oranı %": 2.5}]),
        "Performans": pd.DataFrame([{"Ay": "2026-09", "MagazaID": "M1", "Yönetici Puanı": 80}]),
        "Online Sipariş": pd.DataFrame([{"MagazaID": "M1", "Günlük Sipariş": 12}]),
        "Mal Kabul": pd.DataFrame([{"MagazaID": "M1", "Günlük Mal Kabul": 4}]),
    }

    result = build_module_snapshots(
        sheets=sheets,
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    assert result["operations"]["rows"][0]["Aylık Ciro"] == 100
    assert result["waste_returns"]["rows"][0]["Fire Oranı %"] == 2.5
    assert result["store_performance"]["rows"][0]["Yönetici Puanı"] == 80
    assert result["online_orders"]["rows"][0]["Günlük Sipariş"] == 12
    assert result["goods_receipt"]["rows"][0]["Günlük Mal Kabul"] == 4


def test_sales_target_and_inflation_sources_are_exported(tmp_path: Path) -> None:
    result = build_module_snapshots(
        sheets={
            "Satış Hedefi": pd.DataFrame([
                {"Ay": "2026-09", "MagazaID": "M1", "Hedef Ciro": 120_000},
            ]),
            "Enflasyon": pd.DataFrame([
                {"Dönem": "2026-09", "Enflasyon %": 2.5},
            ]),
        },
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    assert result["sales_targets"]["rows"][0]["Hedef Ciro"] == 120_000
    assert result["inflation"]["rows"][0]["Enflasyon %"] == 2.5
