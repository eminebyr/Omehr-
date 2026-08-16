from __future__ import annotations

"""Madde 15 — Toplu Çıkış hata izolasyonu (regresyon testi).

Kullanıcı kararı: her satır BAĞIMSIZ bir işlemdir. Önceden TEK bir
satırdaki hata (kod/neden uyuşmazlığı, geçersiz index) TÜM toplu
işlemi reddediyordu (tüm-ya-da-hiçbiri). Artık geçerli satırlar
kaydedilir, geçersiz olanlar diğerlerini etkilemeden ayrı raporlanır.
"""

import shutil
from datetime import date


def test_bulk_exit_partial_failure_does_not_cancel_valid_rows(tmp_path):
    from services.personnel_exit import load_personnel_view, process_exits_bulk

    (tmp_path / "input").mkdir()
    shutil.copyfile("ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx")
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"

    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    aktif = staff[staff["İşten Çıkış"].isna()]
    neden = cikis_nedeni.iloc[0]
    kisiler = aktif.iloc[:2]

    cikislar = [
        {"index": kisiler.index[0], "cikis_tarihi": date(2026, 8, 20), "cikis_kodu": str(neden["CikisGrubu"]),
         "cikis_nedeni_id": neden["CikisNedeniID"], "cikis_nedeni_metni": str(neden["CikisNedeni"])},
        {"index": kisiler.index[1], "cikis_tarihi": date(2026, 8, 20), "cikis_kodu": "GECERSIZ_KOD",
         "cikis_nedeni_id": neden["CikisNedeniID"], "cikis_nedeni_metni": str(neden["CikisNedeni"])},
    ]
    sonuc = process_exits_bulk(input_path=hedef, root=tmp_path, cikislar=cikislar, kullanici="test")

    assert sonuc["guncellenen_satir"] == 1, "REGRESYON: geçerli satır kaydedilmedi."
    assert sonuc["basarisiz_satir"] == 1, "REGRESYON: geçersiz satır fark edilmedi."
    assert sonuc["durum"] == "KISMEN_BASARILI"

    staff2, *_ = load_personnel_view(hedef)
    gecerli_isim = kisiler.iloc[0]["İsim Soyisim"]
    gecersiz_isim = kisiler.iloc[1]["İsim Soyisim"]
    assert str(staff2.loc[staff2["İsim Soyisim"] == gecerli_isim, "İşten Çıkış"].iloc[0]) != "nan", (
        "REGRESYON: geçerli satır GERÇEKTEN Excel'e yazılmamış — bir hata TÜM işlemi engellemiş olabilir."
    )
    assert str(staff2.loc[staff2["İsim Soyisim"] == gecersiz_isim, "İşten Çıkış"].iloc[0]) == "nan", (
        "REGRESYON: geçersiz satır YANLIŞLIKLA işlenmiş."
    )


def test_bulk_exit_all_valid_still_works_as_single_write(tmp_path):
    """Hiçbir hata yokken davranış aynı (verimli tek yazma) kalmalı."""
    from services.personnel_exit import load_personnel_view, process_exits_bulk

    (tmp_path / "input").mkdir()
    shutil.copyfile("ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx", tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx")
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"

    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    aktif = staff[staff["İşten Çıkış"].isna()]
    neden = cikis_nedeni.iloc[0]
    kisiler = aktif.iloc[:3]
    cikislar = [
        {"index": idx, "cikis_tarihi": date(2026, 8, 20), "cikis_kodu": str(neden["CikisGrubu"]),
         "cikis_nedeni_id": neden["CikisNedeniID"], "cikis_nedeni_metni": str(neden["CikisNedeni"])}
        for idx in kisiler.index
    ]
    sonuc = process_exits_bulk(input_path=hedef, root=tmp_path, cikislar=cikislar, kullanici="test")
    assert sonuc["durum"] == "OK"
    assert sonuc["guncellenen_satir"] == 3
    assert sonuc["basarisiz_satir"] == 0
