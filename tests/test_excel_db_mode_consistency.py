from __future__ import annotations

"""Excel modu / DB modu veri tutarlılığı — regresyon testleri.

Bizzat bulundu: "Tüm Sayfalar" ekranı (input_data_access.write_sheet)
HER ZAMAN veritabanına yazar, ama Excel modunda Genel Özet/CEO Özeti
(common_veri_okuma.read_all) DOĞRUDAN Excel dosyasından okur — bu
yüzden Excel modunda buradan yapılan bir değişiklik dashboard'a HİÇ
yansımıyordu (kullanıcı "kaydedildi" mesajı görse bile).
"""


def test_db_mode_write_is_visible_to_dashboard(tmp_path, monkeypatch):
    """DB modunda write_sheet ile yazılan bir değişikliğin, dashboard'un
    kullandığı common_veri_okuma.read_all() üzerinden GERÇEKTEN
    görünür olduğunu doğrular."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_INPUT_SOURCE", "db")
    monkeypatch.setenv("OMEHR_DB_BACKEND", "sqlite")
    (tmp_path / "data").mkdir()

    from services.input_excel_migration import migrate_excel_to_db
    migrate_excel_to_db("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", kullanici="kurulum")

    from services.input_data_access import read_sheet, write_sheet
    import pandas as pd

    fm = read_sheet("Fact_Mevcut")
    yeni_satir = fm.iloc[0].copy()
    yeni_satir["İsim Soyisim"] = "REGRESYON TEST KISI"
    fm_yeni = pd.concat([fm, pd.DataFrame([yeni_satir])], ignore_index=True)
    write_sheet("Fact_Mevcut", fm_yeni, kullanici="test")

    from common_veri_okuma import read_all
    sheets = read_all()
    assert (sheets["Fact_Mevcut"]["İsim Soyisim"] == "REGRESYON TEST KISI").any(), (
        "REGRESYON: DB modunda write_sheet ile yazılan değişiklik dashboard'a yansımıyor."
    )


def test_excel_mode_warns_before_data_editor_shown():
    """tum_sayfalar_veri_yonetimi.py'nin, Excel modunda çalışırken
    kullanıcıyı AÇIKÇA uyardığını (kod incelemesiyle) doğrular — bu
    olmadan kullanıcı, veritabanına yazılan ama dashboard'a hiç
    yansımayan bir değişikliği fark etmeden 'kaydedildi' sanabilirdi."""
    kaynak = open("web/tab_modules/tum_sayfalar_veri_yonetimi.py", encoding="utf-8").read()
    assert 'input_source() != "db"' in kaynak
    assert "YANSIMAZ" in kaynak


def test_ana_veri_yonetimi_excel_mode_write_is_visible_to_dashboard(tmp_path, monkeypatch):
    """ana_veri_yonetimi.py'nin (Excel dosyasına DOĞRUDAN yazan
    save_tables kullanımı) Excel modunda GERÇEKTEN tutarlı olduğunu
    doğrular — bu ekranın SORUNLU OLMADIĞINI kanıtlar."""
    import shutil
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("OMEHR_INPUT_SOURCE", raising=False)
    (tmp_path / "input").mkdir()
    yol = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copyfile("ORNEK_VERI_GUVENLI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", yol)

    from services.master_data_admin import read_tables, save_tables
    import pandas as pd

    tables = read_tables(yol)
    yeni_satir = tables["Fact_Mevcut"].iloc[0].copy()
    yeni_satir["İsim Soyisim"] = "ANA VERI REGRESYON TEST"
    tables["Fact_Mevcut"] = pd.concat([tables["Fact_Mevcut"], pd.DataFrame([yeni_satir])], ignore_index=True)
    save_tables(tmp_path, yol, tables, "test")

    from common_veri_okuma import read_all
    sheets = read_all(yol)
    assert (sheets["Fact_Mevcut"]["İsim Soyisim"] == "ANA VERI REGRESYON TEST").any()
