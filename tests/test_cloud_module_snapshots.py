from __future__ import annotations

import json

import pandas as pd

from services.cloud_module_snapshots import build_module_snapshots


def test_module_snapshots_are_json_safe_and_exclude_personal_address(tmp_path):
    staff = pd.DataFrame([{
        "İsim Soyisim": "Demo Personel",
        "Mağaza": "Demo Mağaza",
        "Unvan": "Kasiyer",
        "Ev Adresi": "paylaşılmamalı",
    }])
    detail = pd.DataFrame([{
        "Mağaza": "Demo Mağaza",
        "Unvan": "Kasiyer",
        "Norm Kadro": 2,
        "Aktif Mevcut": 1,
        "Norm Eksiği": 1,
        "Norm Fazlası": 0,
    }])

    modules = build_module_snapshots(
        sheets={"Fazla Mesai": pd.DataFrame([{"Saat": 2}])},
        staff=staff,
        store_title_detail=detail,
        scenarios={},
        output_dir=tmp_path,
    )

    personnel = modules["personnel"]["rows"][0]
    assert personnel["İsim Soyisim"] == "Demo Personel"
    assert "Ev Adresi" not in personnel
    assert modules["store_title"]["rows"][0]["Eksik"] == 1
    json.dumps(modules, ensure_ascii=False)


def test_transfer_snapshot_accepts_engine_frame_that_already_has_scenario_column(tmp_path):
    modules = build_module_snapshots(
        sheets={},
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={"Minimum Mesafe": pd.DataFrame([{
            "Senaryo": "Minimum Mesafe",
            "Kaynak Mağaza": "A",
            "Hedef Mağaza": "B",
        }])},
        output_dir=tmp_path,
    )

    assert modules["transfer"]["rows"][0]["Senaryo"] == "Minimum Mesafe"
