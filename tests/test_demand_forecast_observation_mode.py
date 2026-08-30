"""services.demand_forecast — gözlem modu sıkılaştırması.

Bağımsız bir değerlendirmede şu risk belirlendi: motor yalnız 3 aylık
veriyle devreye girebiliyordu, bu erken/yetersiz veride kullanıcıyı
yanıltabilirdi. Bu testler, eşiğin 6 aya çıkarıldığını ve çıktının artık
"gözlem modu, norma/transfere etkisi %0" bilgisini AÇIKÇA taşıdığını
doğrular.
"""
from __future__ import annotations

import pandas as pd

from services.demand_forecast import (
    FORECAST_MODE,
    MAXIMUM_NORM_EFFECT,
    MAXIMUM_TRANSFER_EFFECT,
    MINIMUM_HISTORY_MONTHS,
    OUTPUT_FILE_NAME,
    run,
)


def _aylik_veri(ay_sayisi: int, gozlem_sayisi: int | None = None) -> pd.DataFrame:
    gozlem_sayisi = gozlem_sayisi or max(ay_sayisi * 3, 8)
    tarihler = pd.date_range("2026-01-01", periods=gozlem_sayisi, freq=f"{max(1, (ay_sayisi * 30) // gozlem_sayisi)}D")
    return pd.DataFrame({"Tarih": tarihler, "Ciro": [10000 + i * 50 for i in range(gozlem_sayisi)]})


def test_minimum_history_is_now_six_months_not_three(isolated_root):
    """REGRESYON testi: eskiden 3 aylık veri yeterliydi (SUCCESS
    dönerdi); artık en az 6 ay gerekiyor."""
    df_3ay = _aylik_veri(3, gozlem_sayisi=10)
    sonuc = run({"Operasyon": df_3ay}, isolated_root / "output")

    assert sonuc["status"] == "SKIPPED"
    assert str(MINIMUM_HISTORY_MONTHS) in sonuc["reason"]


def test_six_months_of_data_still_produces_a_result(isolated_root):
    df_7ay = _aylik_veri(7, gozlem_sayisi=25)
    sonuc = run({"Operasyon": df_7ay}, isolated_root / "output")

    assert sonuc["status"] == "SUCCESS"
    assert sonuc["months"] >= MINIMUM_HISTORY_MONTHS


def test_result_declares_observation_mode_and_zero_effect(isolated_root):
    """Çıktı, kendi kapsamını (gözlem modu, norma/transfere sıfır etki)
    AÇIKÇA beyan etmeli — bu bilgi zımni değil, dönüş sözlüğünde var
    olmalı."""
    df = _aylik_veri(7, gozlem_sayisi=25)
    sonuc = run({"Operasyon": df}, isolated_root / "output")

    assert sonuc["forecast_mode"] == "observation_only" == FORECAST_MODE
    assert sonuc["maximum_norm_effect"] == 0.0 == MAXIMUM_NORM_EFFECT
    assert sonuc["maximum_transfer_effect"] == 0.0 == MAXIMUM_TRANSFER_EFFECT


def test_output_file_is_no_longer_named_like_a_personnel_forecast(isolated_root):
    """REGRESYON testi: dosya adı artık 'Talep_Tahmini' (personel talep
    tahminiyle karıştırılabilir) değil, kapsamı doğru yansıtan
    'Ciro_Kisa_Vadeli_Projeksiyonu'."""
    df = _aylik_veri(7, gozlem_sayisi=25)
    sonuc = run({"Operasyon": df}, isolated_root / "output")

    from pathlib import Path

    assert Path(sonuc["file"]).name == OUTPUT_FILE_NAME
    assert "Talep_Tahmini" not in OUTPUT_FILE_NAME
    assert "Ciro" in OUTPUT_FILE_NAME


def test_excel_output_contains_explicit_scope_disclaimer(isolated_root):
    """Web panelinde henüz bu çıktıya bir yüzey eklenmemiş olsa bile,
    Excel dosyasının KENDİSİ açılırsa yanlış anlaşılmamalı — 'Mod' ve
    'Not' sütunları açıkça uyarmalı."""
    df = _aylik_veri(7, gozlem_sayisi=25)
    sonuc = run({"Operasyon": df}, isolated_root / "output")

    df_out = pd.read_excel(sonuc["file"])
    assert "karar amaçlı kullanılmamalıdır" in df_out["Mod"].iloc[0]
    assert "personel talep tahmini" in df_out["Not"].iloc[0].lower()
    assert df_out["Norma Etkisi"].iloc[0] == 0.0
    assert df_out["Transfer Kararına Etkisi"].iloc[0] == 0.0


def test_still_skips_gracefully_with_insufficient_raw_observations(isolated_root):
    """Önceki davranış (8 gözlemden az veri -> SKIPPED) korunmalı."""
    df_az = pd.DataFrame({
        "Tarih": pd.date_range("2026-01-01", periods=5, freq="30D"),
        "Ciro": [10000, 11000, 10500, 12000, 11500],
    })
    sonuc = run({"Operasyon": df_az}, isolated_root / "output")
    assert sonuc["status"] == "SKIPPED"


def test_missing_operational_sheet_still_skips_gracefully(isolated_root):
    """Önceki davranış (uygun sayfa yoksa -> SKIPPED, uydurma tahmin
    yok) korunmalı."""
    sonuc = run({}, isolated_root / "output")
    assert sonuc["status"] == "SKIPPED"


def test_existing_monthly_operation_sheet_is_accepted(isolated_root):
    """Canlı inputtaki kurumsal başlık + gömülü kolon satırı biçimi doğrudan
    tarihsel kaynak olarak kullanılmalı; ayrı bir kopya sayfa gerekmemeli."""
    months = pd.date_range("2026-01-01", periods=7, freq="MS").strftime("%Y-%m")
    raw = pd.DataFrame([
        ["Ay", "MagazaID", "Mağaza", "Aylık Ciro"],
        *[[month, "M1", "TEST", 1000 + index * 100] for index, month in enumerate(months)],
    ], columns=["AYLIK OPERASYON KPI", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3"])

    sonuc = run({"Aylık Operasyon KPI": raw}, isolated_root / "output")

    assert sonuc["status"] == "SUCCESS"
    assert sonuc["source_sheet"] == "Aylık Operasyon KPI"
    assert sonuc["store_forecasts"] == 1
    workbook = pd.ExcelFile(sonuc["file"])
    assert workbook.sheet_names == ["Şirket Projeksiyonu", "Tarihsel Aylık Toplamlar", "Mağaza Projeksiyonu"]
