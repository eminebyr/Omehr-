from __future__ import annotations

"""RELEASE_MANIFEST.json çift kayıt hatası — regresyon testi.

Kaynak dizinde ESKİ bir RELEASE_MANIFEST.json (ör. önceki bir
verify_release.py --write-manifest çalıştırmasından kalma) varsa,
build_clean_zip() bunu HEM normal dosya taramasında HEM DE kendi
ürettiği YENİ manifestle AYRI olarak yazıyordu — ZIP içinde aynı isimli
2 girdi oluşuyordu (hangisinin okunacağı belirsiz).
"""


def test_stale_manifest_in_source_does_not_create_duplicate_entry(tmp_path):
    from tools.build_clean_package import build_clean_zip

    kaynak = tmp_path / "kaynak"
    kaynak.mkdir()
    (kaynak / "eski_manifest_taklidi.py").write_text("# gerçek bir dosya\n", encoding="utf-8")
    (kaynak / "RELEASE_MANIFEST.json").write_text('{"eski_kalinti_belirteci": "ESKI_VERI_XYZ"}', encoding="utf-8")

    hedef = tmp_path / "paket.zip"
    build_clean_zip(kaynak, hedef, verification={"status": "PASS"})

    import zipfile
    with zipfile.ZipFile(hedef) as z:
        isimler = z.namelist()
        adet = isimler.count("RELEASE_MANIFEST.json")
        assert adet == 1, f"REGRESYON: RELEASE_MANIFEST.json pakette {adet} kez var, 1 olmalı."
        # ve içeriği ESKİ kalıntı değil, YENİ üretilen olmalı
        icerik = z.read("RELEASE_MANIFEST.json").decode("utf-8")
        assert "ESKI_VERI_XYZ" not in icerik
        assert "PASS" in icerik
