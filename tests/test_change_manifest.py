from __future__ import annotations

"""MADDE 7 — Change Manifest testleri."""

import pandas as pd


def test_change_manifest_matches_specification_example():
    from services.change_manifest import build_change_manifest

    onceki = pd.DataFrame([
        {"İsim Soyisim": "ŞEYMA ASLAN", "Mağaza": "AKEVLER", "Unvan": "KASİYER", "İşten Çıkış": None},
    ])
    sonraki = pd.DataFrame([
        {"İsim Soyisim": "ŞEYMA ASLAN", "Mağaza": "AKEVLER", "Unvan": "KASİYER", "İşten Çıkış": "16.08.2026"},
    ])
    manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=onceki, after=sonraki)
    alan_kayitlari = {k["field"]: k for k in manifest}
    assert "İşten Çıkış" in alan_kayitlari
    kayit = alan_kayitlari["İşten Çıkış"]
    assert kayit["sheet"] == "Fact_Mevcut"
    assert kayit["key"] == "ŞEYMA ASLAN"
    assert kayit["new_value"] == "16.08.2026"
    assert kayit["magaza"] == "AKEVLER"
    assert kayit["unvan"] == "KASİYER"


def test_change_manifest_ignores_unchanged_fields():
    from services.change_manifest import build_change_manifest

    onceki = pd.DataFrame([{"İsim Soyisim": "A", "Mağaza": "X", "Unvan": "Y", "Alan1": "aynı", "Alan2": "eski"}])
    sonraki = pd.DataFrame([{"İsim Soyisim": "A", "Mağaza": "X", "Unvan": "Y", "Alan1": "aynı", "Alan2": "yeni"}])
    manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=onceki, after=sonraki)
    alanlar = {k["field"] for k in manifest}
    assert "Alan1" not in alanlar, "Değişmeyen alan manifest'e girmemeli."
    assert "Alan2" in alanlar


def test_change_manifest_detects_new_and_removed_keys():
    from services.change_manifest import build_change_manifest

    onceki = pd.DataFrame([{"İsim Soyisim": "Eski Kişi", "Mağaza": "X", "Unvan": "Y"}])
    sonraki = pd.DataFrame([{"İsim Soyisim": "Yeni Kişi", "Mağaza": "X", "Unvan": "Y"}])
    manifest = build_change_manifest(sheet="Fact_Mevcut", key_col="İsim Soyisim", before=onceki, after=sonraki)
    anahtarlar = {k["key"]: k["new_value"] for k in manifest}
    assert anahtarlar.get("Yeni Kişi") == "EKLENDİ"
    assert anahtarlar.get("Eski Kişi") is None  # kaldırılan anahtarın new_value'su None olmalı


def test_process_exit_writes_change_manifest_log(isolated_root):
    import shutil
    from pathlib import Path
    from datetime import date
    import json

    kaynak = Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    hedef_dizin = isolated_root / "input"
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    hedef = hedef_dizin / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copyfile(kaynak, hedef)

    from services.personnel_exit import load_personnel_view, process_exit
    staff, magaza, unvan, cikis_nedeni = load_personnel_view(hedef)
    kisi = staff[staff["İşten Çıkış"].isna()].iloc[0]
    neden = cikis_nedeni.iloc[0]
    process_exit(
        input_path=hedef, root=isolated_root, isim_soyisim=str(kisi["İsim Soyisim"]),
        magaza_id=str(kisi["MağazaID"]), staff_index=kisi.name, cikis_tarihi=date(2026, 8, 11),
        cikis_kodu=str(neden["CikisGrubu"]), cikis_nedeni_id=neden["CikisNedeniID"],
        cikis_nedeni_metni=str(neden["CikisNedeni"]), kullanici="test",
    )

    manifest_dosyasi = isolated_root / "logs" / "change_manifest.jsonl"
    assert manifest_dosyasi.exists(), "REGRESYON: change manifest dosyası hiç yazılmadı."
    with manifest_dosyasi.open(encoding="utf-8") as f:
        kayitlar = [json.loads(satir) for satir in f if satir.strip()]
    ilgili = [k for k in kayitlar if k["key"] == str(kisi["İsim Soyisim"]) and k["field"] == "İşten Çıkış"]
    assert len(ilgili) == 1, "REGRESYON: İşten Çıkış alanı değişikliği manifest'e girmemiş."
