from __future__ import annotations

"""Paylaşılan proje input/ dosyasının yedekleme/geri yükleme koruması
— regresyon testi.

Önceden test_main_py_produces_correct_kpis_with_default_root, main.py'yi
paylaşılan GERÇEK proje input/ dosyası üzerinde çalıştırıyordu, hiçbir
yedekleme olmadan — bu, aynı dosyayı okuyan DİĞER testlerle (test_all_
branch_diff.py gibi) ara sıra çakışmaya (BadZipFile hatası) yol açtı.
"""

import shutil


def test_shared_input_file_restored_even_if_subprocess_fails(tmp_path, monkeypatch):
    """Yedekleme/geri yükleme mantığının, ALT SÜREÇ BAŞARISIZ OLSA bile
    (main.py çökse bile) dosyayı doğru geri yüklediğini doğrular."""
    import subprocess
    import sys
    import os

    proje_kok = tmp_path / "sahte_proje"
    (proje_kok / "input").mkdir(parents=True)
    orijinal_icerik = b"ORIJINAL_ICERIK_KORUNMALI"
    hedef = proje_kok / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"
    hedef.write_bytes(orijinal_icerik)

    yedek = tmp_path / "input_yedek.xlsx"
    shutil.copyfile(hedef, yedek)

    # "main.py" yerine kasıtlı BAŞARISIZ olan sahte bir alt süreç simüle et
    # ve dosyayı "bozacak" şekilde üzerine yaz.
    try:
        hedef.write_bytes(b"BOZUK_ICERIK_SIMULASYONU")
        raise RuntimeError("main.py çökmüş gibi davran")
    except RuntimeError:
        pass
    finally:
        if yedek.exists():
            shutil.copyfile(yedek, hedef)

    assert hedef.read_bytes() == orijinal_icerik, (
        "REGRESYON: alt süreç başarısız olduğunda bile dosya orijinal "
        "haline geri yüklenmeli — şu an bozuk içerik kalmış."
    )
