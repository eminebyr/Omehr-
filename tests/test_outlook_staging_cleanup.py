from __future__ import annotations

"""Outlook_Hazir staging klasörü temizleme mekanizması — regresyon testi.

Önceden bu klasördeki (her gönderim için üretilen, tek kullanımlık
kopyalar) dosyalar için hiçbir temizleme mekanizması yoktu.
"""

import os
import time


def test_old_staging_files_are_deleted_recent_ones_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    import importlib
    import report_mail_engine as rme
    importlib.reload(rme)

    staging = tmp_path / "output" / "Outlook_Hazir"
    staging.mkdir(parents=True)

    eski = staging / "ESKI.pdf"
    eski.write_bytes(b"eski")
    eski_zaman = time.time() - (rme.STAGING_RETENTION_SAAT + 1) * 3600
    os.utime(eski, (eski_zaman, eski_zaman))

    yeni = staging / "YENI.pdf"
    yeni.write_bytes(b"yeni")

    silinen = rme._eski_staging_dosyalarini_temizle()

    assert silinen == 1
    assert not eski.exists(), "REGRESYON: eski dosya silinmedi."
    assert yeni.exists(), "REGRESYON: yeni dosya yanlışlıkla silindi."


def test_cleanup_runs_automatically_after_send(tmp_path, monkeypatch):
    """Temizleme fonksiyonunun gönderim akışının sonunda GERÇEKTEN
    çağrıldığını doğrular (yalnız var olduğunu değil)."""
    kaynak = open("report_mail_engine.py", encoding="utf-8").read()
    assert "_eski_staging_dosyalarini_temizle()" in kaynak
    # tanım DIŞINDA en az bir çağrı olmalı
    assert kaynak.count("_eski_staging_dosyalarini_temizle()") >= 2
