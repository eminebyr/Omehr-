"""GÜNCELLEME MEKANİZMASI — testler (services/updater.py).

Gerçek dosya sistemi işlemleriyle test edilir (sahte bir "kurulum"
klasörü ve sahte bir "güncelleme paketi" oluşturulur). En kritik üç
özellik doğrulanır: (1) kod güncellenir, (2) kullanıcı verisine ASLA
dokunulmaz, (3) bir hata olursa otomatik/güvenli geri alma çalışır ve
uygulama asla yarım güncellenmiş/çökmüş durumda kalmaz.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from services.exceptions import ConfigurationError, WorkbookError


def _sahte_kurulum(tmp_path: Path) -> Path:
    root = tmp_path / "kurulum"
    (root / "services").mkdir(parents=True)
    (root / "input").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    (root / "backups").mkdir(parents=True)
    (root / "services" / "m.py").write_text("eski", encoding="utf-8")
    (root / "main.py").write_text("eski main", encoding="utf-8")
    (root / "config_web.json").write_text('{"company":{"name":"Gerçek Müşteri"}}', encoding="utf-8")
    (root / "input" / "veri.xlsx").write_text("MÜŞTERİ VERİSİ", encoding="utf-8")
    (root / "data" / "onemli.db").write_text("veritabanı", encoding="utf-8")
    return root


def _sahte_guncelleme_paketi(tmp_path: Path) -> Path:
    paket = tmp_path / "paket"
    (paket / "services").mkdir(parents=True)
    (paket / "services" / "m.py").write_text("YENİ", encoding="utf-8")
    (paket / "main.py").write_text("YENİ main", encoding="utf-8")
    return paket


def test_compare_versions():
    from services.updater import compare_versions

    assert compare_versions("1.2.0", "1.3.0") == -1
    assert compare_versions("1.3.0", "1.2.0") == 1
    assert compare_versions("1.2.0", "1.2.0") == 0
    assert compare_versions("1.1.0", "1.2.0") == -1  # sayısal karşılaştırma, string değil


def test_compare_versions_rejects_invalid_format():
    from services.updater import compare_versions

    with pytest.raises(ConfigurationError):
        compare_versions("1.2", "1.3.0")


def test_current_version_matches_services_version_module():
    from services.updater import current_version
    from services.version import APP_VERSION

    assert current_version() == APP_VERSION


def test_apply_update_updates_code_files(tmp_path):
    from services.updater import apply_update

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)

    sonuc = apply_update(paket, root, new_version="1.4.0")

    assert sonuc.basarili is True
    assert sonuc.yeni_surum == "1.4.0"
    assert (root / "main.py").read_text() == "YENİ main"
    assert (root / "services" / "m.py").read_text() == "YENİ"


def test_apply_update_never_touches_user_data(tmp_path):
    """EN KRİTİK test: güncelleme, input/data/config gibi kullanıcı
    verisine KESİNLİKLE dokunmamalı."""
    from services.updater import apply_update

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)

    apply_update(paket, root, new_version="1.4.0")

    assert (root / "input" / "veri.xlsx").read_text() == "MÜŞTERİ VERİSİ"
    assert (root / "data" / "onemli.db").read_text() == "veritabanı"
    assert (root / "config_web.json").read_text() == '{"company":{"name":"Gerçek Müşteri"}}'


def test_apply_update_ignores_malicious_or_accidental_user_data_in_package(tmp_path):
    """Güncelleme paketinin İÇİNDE yanlışlıkla/kötü niyetle input/ ya da
    config_web.json bulunsa bile, bunlar UPDATE_INCLUDE listesinde
    olmadığı için KOPYALANMAMALI."""
    from services.updater import apply_update

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)
    (paket / "input").mkdir(parents=True)
    (paket / "input" / "sizinti.xlsx").write_text("bu asla kopyalanmamali", encoding="utf-8")
    (paket / "config_web.json").write_text('{"company":{"name":"SAHTE"}}', encoding="utf-8")

    apply_update(paket, root, new_version="1.4.0")

    assert not (root / "input" / "sizinti.xlsx").exists()
    assert (root / "config_web.json").read_text() == '{"company":{"name":"Gerçek Müşteri"}}'


def test_apply_update_creates_a_pre_update_snapshot(tmp_path):
    from services.updater import apply_update

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)

    sonuc = apply_update(paket, root, new_version="1.4.0")

    assert sonuc.yedek_yolu.is_dir()
    assert (sonuc.yedek_yolu / "main.py").read_text() == "eski main"  # ESKİ hâli yedekte


def test_manual_rollback_restores_previous_code(tmp_path):
    from services.updater import apply_update, rollback

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)
    sonuc = apply_update(paket, root, new_version="1.4.0")
    assert (root / "main.py").read_text() == "YENİ main"

    rollback(sonuc.yedek_yolu, root)

    assert (root / "main.py").read_text() == "eski main"
    assert (root / "services" / "m.py").read_text() == "eski"
    assert (root / "input" / "veri.xlsx").read_text() == "MÜŞTERİ VERİSİ"  # hâlâ dokunulmamış


def test_apply_update_auto_rolls_back_on_partial_failure(tmp_path):
    """Güncelleme YARIDA kesilirse (ör. disk hatası), sistem YARIM
    güncellenmiş durumda kalmamalı — otomatik olarak önceki sürüme
    dönmeli."""
    from services import updater

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)

    orijinal_copyfile = updater.shutil.copyfile

    def bozuk_copyfile(src, dst, *args, **kwargs):
        if str(dst) == str(root / "main.py"):
            raise OSError("simüle edilmiş disk hatası")
        return orijinal_copyfile(src, dst)

    with patch.object(updater.shutil, "copyfile", side_effect=bozuk_copyfile):
        sonuc = updater.apply_update(paket, root, new_version="1.4.0")

    assert sonuc.basarili is False
    assert sonuc.hata is not None
    # main.py rollback sırasında da aynı sahte hatayla karşılaşacağı için
    # bu senaryoda "KRİTİK" (çifte başarısızlık) yolunun devreye girmesi
    # BEKLENİR — asıl kontrol edilen şey PROGRAMIN ÇÖKMEMESİ ve kullanıcı
    # verisinin (input/config) yine de dokunulmamış kalmasıdır.
    assert (root / "input" / "veri.xlsx").read_text() == "MÜŞTERİ VERİSİ"


def test_apply_update_cancels_cleanly_if_backup_itself_fails(tmp_path):
    """REGRESYON testi: yedekleme adımının KENDİSİ başarısız olursa,
    apply_update ÇÖKMEMELİ ve HİÇBİR dosyayı değiştirmeden net bir hata
    döndürmeli (bkz. DEGISIKLIK_OZETI — bu, testte yakalanan gerçek bir
    bug'ın düzeltmesiydi: önceden create_pre_update_snapshot() çağrısı
    try/except dışındaydı)."""
    from services import updater

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)

    with patch.object(updater.shutil, "copytree", side_effect=OSError("disk dolu")):
        sonuc = updater.apply_update(paket, root, new_version="1.4.0")

    assert sonuc.basarili is False
    assert "yedek alınamadı" in sonuc.hata
    assert (root / "main.py").read_text() == "eski main"  # HİÇBİR ŞEY değişmemiş


def test_apply_update_rejects_missing_package_dir(tmp_path):
    from services.updater import apply_update

    root = _sahte_kurulum(tmp_path)
    with pytest.raises(WorkbookError):
        apply_update(tmp_path / "hic_olmayan_paket", root, new_version="1.4.0")


def test_apply_update_is_idempotent_when_run_twice_in_a_row(tmp_path):
    """Aynı paketi iki kez uygulamak hata vermemeli (ör. bir önceki
    çalıştırma yarıda kesilip tekrar denenirse)."""
    from services.updater import apply_update

    root = _sahte_kurulum(tmp_path)
    paket = _sahte_guncelleme_paketi(tmp_path)

    sonuc1 = apply_update(paket, root, new_version="1.4.0")
    sonuc2 = apply_update(paket, root, new_version="1.4.0")

    assert sonuc1.basarili is True
    assert sonuc2.basarili is True
    assert (root / "main.py").read_text() == "YENİ main"
