from __future__ import annotations

"""Kurulum sırasında şifre taşıma hatası — regresyon testleri.

Önceden herhangi bir Mail_Listesi okuma sorunu (bozuk Excel, kilitli
dosya) INITIAL_PASSWORD_IMPORT.py üzerinden BASDAS_CURRENT_BASLAT.bat'ın
TÜM kurulum/başlatma sürecini "HATA: Kullanici guvenlik aktarimi
basarisiz oldu" mesajıyla DURDURMASINA yol açıyordu. Şifre taşıma
yalnız bir kolaylıktır (admin her zaman .env'deki varsayılan şifreyle
girebilir) — artık hiçbir koşulda kurulumu engellemez.
"""

import pandas as pd
import pytest


def test_corrupt_excel_file_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "input").mkdir()
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    hedef.write_bytes(b"GECERLI BIR EXCEL DOSYASI DEGIL")

    from services.security import migrate_legacy_input
    sonuc = migrate_legacy_input(hedef)
    assert sonuc == 0


def test_missing_mail_listesi_sheet_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "input").mkdir()
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    df = pd.DataFrame([{"X": 1}])
    with pd.ExcelWriter(hedef) as w:
        df.to_excel(w, sheet_name="BaskaSayfa", index=False)

    from services.security import migrate_legacy_input
    sonuc = migrate_legacy_input(hedef)
    assert sonuc == 0


def test_initial_password_import_main_never_returns_nonzero_on_migration_error(tmp_path, monkeypatch):
    """İkinci güvenlik katmanı: migrate_legacy_input BEKLENMEDİK bir
    istisna (ör. veritabanı hatası) fırlatsa bile, INITIAL_PASSWORD_
    IMPORT.py'nin main() fonksiyonu 0 dönmeli (kurulumu durdurmamalı)."""
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "input").mkdir()
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    df = pd.DataFrame([{"Web Kullanıcı": "test1", "Web Şifre": "GecicSifre123"}])
    with pd.ExcelWriter(hedef) as w:
        df.to_excel(w, sheet_name="Mail_Listesi", index=False)

    import services.security as sec

    def bozuk_migrate(*a, **k):
        raise RuntimeError("SIMÜLE EDİLMİŞ beklenmedik hata")

    monkeypatch.setattr(sec, "migrate_legacy_input", bozuk_migrate)

    import importlib
    import INITIAL_PASSWORD_IMPORT as ipi
    importlib.reload(ipi)
    monkeypatch.setattr(ipi, "migrate_legacy_input", bozuk_migrate, raising=False)

    sonuc = ipi.main()
    assert sonuc == 0, (
        "REGRESYON: şifre taşımadaki beklenmedik bir hata hâlâ kurulumu "
        "durduruyor (main() 0 dışında bir değer döndü)."
    )
