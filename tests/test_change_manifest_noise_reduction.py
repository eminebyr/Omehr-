from __future__ import annotations

"""Change Manifest (Madde 7) gürültü giderme — regresyon testleri.

İki gerçek hata bulunup düzeltildi:
1. Fact_Mevcut'ta hâlâ Excel formülü olan sütunlar (Norm fazlası Norm
   eksiği, Kıdem Gün/Yıl) her okunduğunda boş/None döndüğü için HER
   yazma işleminde "değişti" görünüyordu — tek bir kişinin çıkışı 613
   sahte kayıt üretiyordu.
2. Anahtar sütunundaki (İsim Soyisim) boşluk farkı, aynı kişinin
   YANLIŞLIKLA "silindi + yeniden eklendi" görünmesine yol açıyordu.
"""

import pandas as pd


def test_known_formula_columns_excluded_from_manifest():
    from services.change_manifest import build_change_manifest, BILINEN_FORMUL_SUTUNLARI
    before = pd.DataFrame([
        {"İsim Soyisim": "A", "Norm fazlası Norm eksiği": None, "Kıdem (Gün)": None, "Mağaza": "X"},
    ])
    after = pd.DataFrame([
        {"İsim Soyisim": "A", "Norm fazlası Norm eksiği": "Norma Uygun", "Kıdem (Gün)": 120, "Mağaza": "X"},
    ])
    manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=before, after=after, ignore_columns=BILINEN_FORMUL_SUTUNLARI)
    assert manifest == [], f"REGRESYON: bilinen formül sütunları hâlâ manifest'e sızıyor: {manifest}"


def test_whitespace_only_key_difference_does_not_create_fake_add_delete():
    from services.change_manifest import build_change_manifest
    before = pd.DataFrame([{"İsim Soyisim": "ENES GÜN ", "Mağaza": "POLİGON"}])
    after = pd.DataFrame([{"İsim Soyisim": "ENES GÜN", "Mağaza": "POLİGON"}])
    manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=before, after=after)
    sahte = [m for m in manifest if m["field"] == "*"]
    assert sahte == [], f"REGRESYON: yalnız boşluk farkı olan aynı kişi silindi/eklendi olarak görünüyor: {sahte}"


def test_real_field_change_is_still_detected_correctly():
    """Gürültü giderme, GERÇEK değişiklikleri kaçırmamalı."""
    from services.change_manifest import build_change_manifest, BILINEN_FORMUL_SUTUNLARI
    before = pd.DataFrame([{"İsim Soyisim": "ŞEYMA ASLAN", "İşten Çıkış": None, "Mağaza": "TORBALI 1"}])
    after = pd.DataFrame([{"İsim Soyisim": "ŞEYMA ASLAN", "İşten Çıkış": "2026-08-16", "Mağaza": "TORBALI 1"}])
    manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=before, after=after, ignore_columns=BILINEN_FORMUL_SUTUNLARI)
    assert len(manifest) == 1
    assert manifest[0]["field"] == "İşten Çıkış"
    assert manifest[0]["new_value"] == "2026-08-16"


def test_end_to_end_exit_produces_small_actionable_manifest(tmp_path):
    """Gerçek process_exit() çağrısının artık makul boyutta (yüzlerce
    DEĞİL) bir manifest ürettiğini uçtan uca doğrular."""
    import shutil
    from services.personnel_exit import load_personnel_view, process_exit
    from datetime import date

    (tmp_path / "input").mkdir()
    shutil.copyfile("ORNEK_TEST_VERISI/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx", tmp_path / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx")
    hedef = tmp_path / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"

    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    neden = cikis_nedeni.iloc[0]
    process_exit(
        input_path=hedef, root=tmp_path, isim_soyisim=str(kisi["İsim Soyisim"]), magaza_id=str(kisi["MağazaID"]),
        staff_index=kisi.name, cikis_tarihi=date(2026, 8, 16), cikis_kodu=str(neden["CikisGrubu"]),
        cikis_nedeni_id=neden["CikisNedeniID"], cikis_nedeni_metni=str(neden["CikisNedeni"]), kullanici="test",
    )
    manifest_dosyasi = tmp_path / "logs" / "change_manifest.jsonl"
    satirlar = manifest_dosyasi.read_text(encoding="utf-8").strip().split("\n")
    assert len(satirlar) < 50, (
        f"REGRESYON: tek bir çıkış işlemi {len(satirlar)} manifest kaydı üretti "
        "(50'den az olmalıydı) — bilinen formül sütunu filtresi bozulmuş olabilir."
    )
