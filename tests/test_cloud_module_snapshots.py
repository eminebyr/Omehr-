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


def test_embedded_report_header_replaces_unnamed_columns(tmp_path):
    performance = pd.DataFrame(
        [
            ["İsim Soyisim", "MağazaID", "Mağaza", "Unvan", "Devamlılık Puanı", "Sınıf"],
            ["Demo Personel", "M1", "Balçova", "Kasiyer", 92, "A"],
        ],
        columns=[
            "PERSONEL PERFORMANS ENDEKSİ (0-100)",
            "Unnamed: 1", "Unnamed: 2", "Unnamed: 3", "Unnamed: 4", "Unnamed: 5",
        ],
    )

    modules = build_module_snapshots(
        sheets={"Personel_Performans_Endeksi": performance},
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    rows = modules["performance"]["rows"]
    assert len(rows) == 1
    assert rows[0]["İsim Soyisim"] == "Demo Personel"
    assert rows[0]["Devamlılık Puanı"] == 92
    assert not any(column.startswith("Unnamed:") for column in rows[0])


def test_regular_data_with_one_unnamed_column_is_not_promoted(tmp_path):
    overtime = pd.DataFrame([
        {"Mağaza": "Balçova", "Saat": 2, "Unnamed: 2": "not"},
    ])

    modules = build_module_snapshots(
        sheets={"Fazla Mesai": overtime},
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    assert modules["overtime"]["rows"][0]["Mağaza"] == "Balçova"


def test_repeated_performance_note_is_shown_once_as_description(tmp_path):
    note = "Enflasyon oranı baz alınarak reel büyüme ölçülmüştür."
    performance = pd.DataFrame([
        {"İsim Soyisim": "Birinci Personel", "Performans Endeksi (0-100)": 80, "Not": note},
        {"İsim Soyisim": "İkinci Personel", "Performans Endeksi (0-100)": 70, "Not": note},
    ])

    modules = build_module_snapshots(
        sheets={"Personel_Performans_Endeksi": performance},
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    payload = modules["performance"]
    assert payload["description"] == note
    assert all("Not" not in row for row in payload["rows"])


def test_turnover_snapshot_uses_full_history_and_excludes_personal_fields(tmp_path):
    history = pd.DataFrame([
        {
            "PersonelID": index,
            "İsim Soyisim": f"Personel {index}",
            "MağazaID": "eşleşmeyen-id",
            "Mağaza": "Balçova",
            "İşe Giriş": "01.01.2026",
            "İşten Çıkış": "15.02.2026",
            "Çıkış Kodu": "03",
            "Çıkış Nedeni": "İstifa",
            "Kıdem (Gün)": 45,
            "Gerçek Unvan": "Kasiyer",
        }
        for index in range(1501)
    ])
    active_staff = history.iloc[:1].copy()
    active_staff["İşten Çıkış"] = None
    active_staff["Çıkış Nedeni"] = None
    store_dimension = pd.DataFrame([{
        "MağazaID": "M1",
        "Mağaza": "Balçova",
        "Bölge Sorumlusu": "Ege Bölge Müdürü",
    }])

    modules = build_module_snapshots(
        sheets={"Fact_Mevcut": history, "Dim_Magaza": store_dimension},
        staff=active_staff,
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    turnover_rows = modules["turnover_personnel"]["rows"]
    assert len(turnover_rows) == 1501
    assert turnover_rows[0]["Bölge Sorumlusu"] == "Ege Bölge Müdürü"
    assert turnover_rows[0]["Çıkış Nedeni"] == "İstifa"
    assert turnover_rows[0]["Kıdem (Gün)"] == 45
    assert turnover_rows[0]["Gerçek Unvan"] == "Kasiyer"
    assert turnover_rows[0]["İşten Çıkış"] == "15.02.2026"
    assert "İsim Soyisim" not in turnover_rows[0]
    assert len(modules["personnel"]["rows"]) == 1


def test_turnover_active_headcount_uses_all_fact_mevcut_roles_for_canonical_store(tmp_path):
    active_staff = pd.DataFrame([
        {
            "PersonelID": f"aktif-{index}",
            "İsim Soyisim": f"Aktif Personel {index}",
            "MağazaID": "T1",
            "Mağaza": "TORBALI 1",
            "Unvan": "Kasiyer" if index < 3 else "Reyon",
            "İşe Giriş": "01.01.2025",
            "İşten Çıkış": None,
        }
        for index in range(6)
    ])
    exited_staff = pd.DataFrame([
        {
            "PersonelID": f"ayrilan-{index}",
            "İsim Soyisim": f"Ayrılan Personel {index}",
            "MağazaID": "T1",
            "Mağaza": None,
            "Unvan": "Kasap",
            "İşe Giriş": "01.01.2025",
            "İşten Çıkış": "01.08.2026",
        }
        for index in range(5)
    ])
    history = pd.concat([active_staff, exited_staff], ignore_index=True)
    store_dimension = pd.DataFrame([{
        "MağazaID": "T1",
        "Mağaza": "TORBALI 1",
        "Bölge Sorumlusu": "AYŞE AVCU",
    }])

    modules = build_module_snapshots(
        sheets={"Fact_Mevcut": history, "Dim_Magaza": store_dimension},
        staff=active_staff,
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    turnover_rows = modules["turnover_personnel"]["rows"]
    torbali_rows = [row for row in turnover_rows if row["Mağaza"] == "TORBALI 1"]
    assert len(torbali_rows) == 11
    assert sum(row["İşten Çıkış"] is None for row in torbali_rows) == 6


def test_turnover_resolves_exited_employee_real_title_from_dim_unvan(tmp_path):
    history = pd.DataFrame([{
        "PersonelID": "ayrilan-1",
        "İsim Soyisim": "Ayrılan Personel",
        "MağazaID": "T1",
        "Mağaza": "TORBALI 1",
        "UnvanID": "U17",
        "Unvan": None,
        "İşe Giriş": "01.01.2026",
        "İşten Çıkış": "01.08.2026",
        "Çıkış Nedeni": "Ücret yetersizliği",
    }])
    modules = build_module_snapshots(
        sheets={
            "Fact_Mevcut": history,
            "Dim_Unvan": pd.DataFrame([{"UnvanID": "U17", "Unvan": "ELİT KASAP"}]),
        },
        staff=pd.DataFrame(),
        store_title_detail=pd.DataFrame(),
        scenarios={},
        output_dir=tmp_path,
    )

    row = modules["turnover_personnel"]["rows"][0]
    assert row["UnvanID"] == "U17"
    assert row["Gerçek Unvan"] == "ELİT KASAP"
