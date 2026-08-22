from __future__ import annotations

"""KRİTİK GÜVENLİK REGRESYON TESTİ #2.

reference/lo_profile/ (LibreOffice'in geliştirme ortamında oluşturduğu,
ürünle ilgisiz bir profil dizini — 37 dosya, 564KB, ÖNCEKİ TÜM paketlere
sızmıştı) ve reference/GUNCEL_NORM_KADRO_KONTROL.xlsx +
KONTROL_NORM_KADRO_24_07_2026.xlsx (gerçek telefon numaraları, gerçek
fiziksel adresler, gerçek görünen bölge sorumlusu isimleri içeriyordu)
artık paketten hariç tutuluyor.
"""

import zipfile


def test_lo_profile_and_control_files_excluded_from_package(tmp_path):
    from tools.build_clean_package import build_clean_zip
    from pathlib import Path

    kaynak = Path(__file__).resolve().parents[1]
    hedef = tmp_path / "test_paket.zip"
    build_clean_zip(kaynak, hedef)

    with zipfile.ZipFile(hedef) as z:
        isimler = z.namelist()

    lo_profile_dosyalari = [n for n in isimler if n.startswith("reference/lo_profile/")]
    assert lo_profile_dosyalari == [], (
        f"REGRESYON (GÜVENLİK): reference/lo_profile/ içindeki dosyalar "
        f"pakete sızmış: {lo_profile_dosyalari[:5]}"
    )

    kontrol_dosyalari = [
        n for n in isimler
        if n.endswith("GUNCEL_NORM_KADRO_KONTROL.xlsx") or n.endswith("KONTROL_NORM_KADRO_24_07_2026.xlsx")
    ]
    assert kontrol_dosyalari == [], (
        f"REGRESYON (KRİTİK GÜVENLİK): gerçek telefon/adres içeren kontrol "
        f"dosyaları pakete sızmış: {kontrol_dosyalari}"
    )


def test_main_py_works_without_optional_control_files(tmp_path, monkeypatch):
    """Çıkarılan kontrol dosyalarının GERÇEKTEN opsiyonel olduğunu,
    main.py'nin bunlar olmadan da doğru KPI ürettiğini doğrular."""
    import subprocess
    import sys
    import os
    import shutil

    from pathlib import Path
    proje_kok = Path(__file__).resolve().parents[1]

    calisma_dizini = tmp_path / "calisma"
    for d in ("input", "templates", "reference", "assets/fonts"):
        (calisma_dizini / d).mkdir(parents=True)
    shutil.copyfile(
        proje_kok / "ORNEK_TEST_VERISI" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx",
        calisma_dizini / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx",
    )
    for f in (proje_kok / "templates").glob("*.docx"):
        shutil.copyfile(f, calisma_dizini / "templates" / f.name)
    for f in (proje_kok / "assets" / "fonts").glob("*.ttf"):
        shutil.copyfile(f, calisma_dizini / "assets" / "fonts" / f.name)
    shutil.copyfile(
        proje_kok / "reference" / "NORM_KAPSAM_BAZI.json",
        calisma_dizini / "reference" / "NORM_KAPSAM_BAZI.json",
    )
    # BİLEREK: GUNCEL_NORM_KADRO_KONTROL.xlsx kopyalanmıyor

    env = dict(os.environ)
    env["OMEHR_RUNTIME_ROOT"] = str(calisma_dizini)
    env["OMEHR_MAIL_DRY_RUN"] = "1"

    sonuc = subprocess.run(
        [sys.executable, "main.py"], cwd=proje_kok, env=env,
        capture_output=True, text=True, timeout=280,
    )
    assert sonuc.returncode == 0, f"main.py başarısız: {sonuc.stderr[-2000:]}"
    assert '"Aktif Mevcut": 596' in sonuc.stdout
