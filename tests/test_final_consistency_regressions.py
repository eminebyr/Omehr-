from __future__ import annotations

import pandas as pd


def test_scan_alerts_returns_only_new_rows(tmp_path, monkeypatch):
    import services.management_center as management

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    store = pd.DataFrame([
        {"Bölge Sorumlusu": "BÖLGE", "Mağaza": "TEST", "Norm Eksiği": 6},
    ])
    title = pd.DataFrame()

    first = management.scan_alerts(store, title)
    second = management.scan_alerts(store, title)

    assert len(first) == 1
    assert second.empty
    assert len(management.list_alerts()) == 1


def test_report_contract_includes_compact_report():
    from services.report_contract import required_report_paths

    paths = required_report_paths([f"BÖLGE {i}" for i in range(1, 7)])
    assert len(paths) == 33
    assert any(path.name == "OMEHR_Kompakt_Norm_Kadro_Listesi.xlsx" for path in paths)


def test_rotation_checker_initializes_empty_database(tmp_path, monkeypatch):
    import rotasyon_takili_kontrol as checker

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["rotasyon_takili_kontrol.py"])
    checker.main()

    from services.web_runtime import connect_web_db
    with connect_web_db() as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "transfers" in tables


def test_boxed_report_uses_state_distribution(tmp_path):
    from src.excel_report import build_boxed_manager_excel

    st = pd.DataFrame([{
        "Bölge Sorumlusu": "BÖLGE", "Mağaza": "TEST",
        "Aktif Mevcut": 2, "Norm Kadro": 2,
        "Norm Eksiği": 1, "Norm Fazlası": 1, "Net Fark": 0,
    }])
    norm = pd.DataFrame([
        {"Mağaza": "TEST", "Unvan": "YÖNETİCİ", "Norm Kadro": 1},
        {"Mağaza": "TEST", "Unvan": "YÖNETİCİ YARDIMCISI", "Norm Kadro": 1},
    ])
    staff = pd.DataFrame([
        {"Mağaza": "TEST", "Unvan": "YÖNETİCİ", "Departman": "YÖNETİCİ", "İsim Soyisim": "A"},
        {"Mağaza": "TEST", "Unvan": "YÖNETİCİ", "Departman": "YÖNETİCİ", "İsim Soyisim": "B"},
    ])
    # Ham hesap yeniden dengelenseydi eksik/fazla sıfırlanırdı. Resmî state
    # dağılımı ise yöneticide fazla 1, yardımcıda eksik 1 olarak korunmalı.
    tt = pd.DataFrame([
        {"Mağaza": "TEST", "Unvan": "YÖNETİCİ", "Aktif Mevcut": 2, "Norm Kadro": 1, "Norm Eksiği": 0, "Norm Fazlası": 1},
        {"Mağaza": "TEST", "Unvan": "YÖNETİCİ YARDIMCISI", "Aktif Mevcut": 0, "Norm Kadro": 1, "Norm Eksiği": 1, "Norm Fazlası": 0},
    ])
    out = build_boxed_manager_excel(st, norm, staff, output_path=tmp_path / "boxed.xlsx", tt=tt)
    raw = pd.read_excel(out, sheet_name="BÖLGE", header=None)
    text = raw.fillna("").astype(str)
    assert text.apply(lambda col: col.str.contains("TOPLAM").any()).any()
    # Özet kutularında state toplamı E=1 ve F=1 korunur.
    assert any("E\n1" in value for value in text.to_numpy().ravel())
    assert any("F\n1" in value for value in text.to_numpy().ravel())


def test_executive_report_does_not_rebalance_state_output(tmp_path, monkeypatch):
    from src.excel_report import executive_excel

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "output").mkdir()
    kpi = {"Aktif Mevcut": 2, "Toplam Norm": 2, "Norm Eksiği": 1, "Norm Fazlası": 1, "Net İhtiyaç": 0}
    st = pd.DataFrame([{
        "Bölge Sorumlusu": "BÖLGE", "MağazaID": "M1", "Mağaza": "TEST",
        "Aktif Mevcut": 2, "Norm Kadro": 2, "Norm Eksiği": 1, "Norm Fazlası": 1, "Net Fark": 0,
    }])
    tt = pd.DataFrame([
        {"Bölge Sorumlusu": "BÖLGE", "MağazaID": "M1", "Mağaza": "TEST", "Unvan": "YÖNETİCİ",
         "Aktif Mevcut": 2, "Norm Kadro": 1, "Norm Eksiği": 0, "Norm Fazlası": 1, "Net Fark": 1},
        {"Bölge Sorumlusu": "BÖLGE", "MağazaID": "M1", "Mağaza": "TEST", "Unvan": "YÖNETİCİ YARDIMCISI",
         "Aktif Mevcut": 0, "Norm Kadro": 1, "Norm Eksiği": 1, "Norm Fazlası": 0, "Net Fark": -1},
    ])
    out = executive_excel(kpi, st, tt, {}, pd.DataFrame(), "hash")
    report = pd.read_excel(out, sheet_name="Mağaza-Unvan Bazlı")
    values = report.set_index("Departman")[["Norm Eksiği", "Norm Fazlası"]]
    assert int(values.loc["YÖNETİCİ", "Norm Fazlası"]) == 1
    assert int(values.loc["YÖNETİCİ YARDIMCISI", "Norm Eksiği"]) == 1


def test_operation_sources_share_canonical_store_key(tmp_path):
    from src.excel_report import _executive_analysis_frames

    source = tmp_path / "input.xlsx"
    with pd.ExcelWriter(source) as writer:
        pd.DataFrame({"MağazaID": ["M1"], "Mağaza": ["BUCA"]}).to_excel(writer, sheet_name="Dim_Magaza", index=False)
        pd.DataFrame({
            "Ay": ["2026-08"], "MağazaID": ["M1"], "Mağaza": ["BUCA"],
            "Aylık Fiş": [100], "Aylık Ciro": [1000], "Ort. Sepet": [10],
            "Online Sipariş": [5], "Mal Kabul": [4],
        }).to_excel(writer, sheet_name="Aylık Operasyon KPI", index=False)
        pd.DataFrame({"MağazaID": ["M1"], "Mağaza": ["BUCA "], "Fire Oranı %": [4.44]}).to_excel(
            writer, sheet_name="Fire ve İade", index=False
        )
        pd.DataFrame({"MağazaID": ["M1"], "Mağaza": ["BUCA "], "İş Yükü Endeksi": [42.2]}).to_excel(
            writer, sheet_name="İş Yükü Endeksi", index=False
        )

    _executive_analysis_frames.cache_clear()
    _, _, operational = _executive_analysis_frames(source)
    assert len(operational) == 1
    assert operational.iloc[0]["Mağaza"] == "BUCA"
    assert float(operational.iloc[0]["Fire Oranı %"]) == 4.44
    assert float(operational.iloc[0]["İş Yükü Endeksi"]) == 42.2
