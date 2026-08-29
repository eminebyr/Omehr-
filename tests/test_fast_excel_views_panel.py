from pathlib import Path

from openpyxl import Workbook

from services.fast_excel_views import clear, forecast_payload


def test_forecast_payload_reads_all_panel_values_in_one_pass(tmp_path):
    path = tmp_path / "forecast.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Verimlilik_Operasyon_Tahmini"
    ws.append(["Toplam Ciro (TL) (Tahmin)", 10, 20, 30, 40])
    ws.append(["İş Yükü Endeksi (Ciro Tahmininden Türetilmiş)", 1, 2, 3, 4])
    ws.append(["Fazla Mesai (Tahmin)", 5, 6, 7, 8])
    accuracy = wb.create_sheet("Tahmin_Dogruluk_Testi")
    accuracy.append(["Metrik", None, None, None, None, None, None, "MAPE"])
    accuracy.append(["Fazla Mesai", None, None, None, None, None, None, 12.34])
    wb.save(path)

    clear()
    payload = forecast_payload(path)

    assert payload["ciro"] == [10, 20, 30, 40]
    assert payload["isyuku"] == [1, 2, 3, 4]
    assert payload["tahmin_satirlari"] == [("Fazla Mesai", [5, 6, 7, 8])]
    assert payload["dogruluk_satirlari"] == [("Fazla Mesai", 12.3)]
    assert forecast_payload(path) is payload


def test_forecast_pages_use_fast_payload_not_cached_workbook():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "web/tab_modules/verimlilik_gorselleri.py",
        "web/tab_modules/operasyon_gorselleri.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "forecast_payload" in source
        assert "read_workbook_cached" not in source
