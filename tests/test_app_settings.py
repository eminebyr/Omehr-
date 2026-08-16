"""GERÇEK ÜRÜN AYAR EKRANI — arka uç testleri (services/app_settings.py).

web/tab_modules/ayarlar.py'nin kendisi Streamlit'e bağımlı olduğu için bu
sandbox'ta test edilemiyor (bkz. tests/README.md); ama arkasındaki tüm
okuma/yazma/doğrulama mantığı saf Python + dosya sistemi olduğu için
tam olarak test edilebiliyor ve ediliyor.
"""
from __future__ import annotations

import pytest

from services.exceptions import ConfigurationError


def test_get_settings_returns_documented_defaults(isolated_root):
    from services.app_settings import get_settings

    s = get_settings()
    assert s["company"] == {"name": "Başdaş Marketler", "logo_path": ""}
    assert s["backup"] == {"max_backups": 20}
    assert s["notifications"]["smtp"]["enabled"] is False


def test_update_settings_merges_without_touching_unrelated_sections(isolated_root):
    from services.app_settings import get_settings, update_settings

    before = get_settings()
    after = update_settings({"company": {"name": "Yeni Şirket A.Ş."}})

    assert after["company"]["name"] == "Yeni Şirket A.Ş."
    assert after["notifications"] == before["notifications"]
    assert after["approval"] == before["approval"]


def test_update_settings_persists_across_reads(isolated_root):
    from services.app_settings import get_settings, update_settings

    update_settings({"backup": {"max_backups": 7}})
    assert get_settings()["backup"]["max_backups"] == 7


def test_security_settings_cannot_be_changed_via_update_settings(isolated_root):
    """Parola/güvenlik ayarları bu ekrandan DEĞİŞTİRİLEMEMELİ — güvenlik
    kararı bilerek kod tarafında sabit tutuluyor."""
    from services.app_settings import get_settings, update_settings

    before = get_settings()["security"]["iterations"]
    update_settings({"security": {"iterations": 1}})
    after = get_settings()["security"]["iterations"]
    assert after == before == 600000


def test_partial_smtp_update_preserves_other_smtp_fields(isolated_root):
    from services.app_settings import update_settings

    update_settings({"notifications": {"smtp": {"host": "smtp.example.com"}}})
    from services.app_settings import get_settings

    smtp = get_settings()["notifications"]["smtp"]
    assert smtp["host"] == "smtp.example.com"
    assert smtp["port"] == 587  # dokunulmayan alan korunmuş olmalı


def test_feature_flags_round_trip(isolated_root):
    from services.app_settings import get_feature_flags, set_feature_flags

    assert get_feature_flags()["demand_forecast_enabled"] is True
    set_feature_flags({"demand_forecast_enabled": False})
    assert get_feature_flags()["demand_forecast_enabled"] is False


def test_feature_flags_reject_unknown_keys(isolated_root):
    from services.app_settings import set_feature_flags

    with pytest.raises(ConfigurationError):
        set_feature_flags({"var_olmayan_ozellik": True})


def test_feature_flag_cache_is_invalidated_after_write(isolated_root):
    """src.feature_flags.all_features() @lru_cache kullanıyor; bu testin
    amacı, set_feature_flags() sonrası AYNI süreç içinde eski (önbelleğe
    alınmış) değerin değil, GÜNCEL değerin görünmesini doğrulamak."""
    from src.feature_flags import demand_forecast_enabled
    from services.app_settings import set_feature_flags

    _ = demand_forecast_enabled()  # önbelleği doldur
    set_feature_flags({"demand_forecast_enabled": False})
    assert demand_forecast_enabled() is False


def test_input_file_info_reports_existence_correctly(isolated_root):
    from services.app_settings import input_file_info
    from services.settings import input_path

    info = input_file_info()
    assert info["exists"] is False  # henüz dosya yok

    path = input_path(isolated_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake")

    info2 = input_file_info()
    assert info2["exists"] is True
    assert info2["file_name"] == path.name


def test_backup_max_backups_reads_from_settings(isolated_root):
    """services/backup.py'nin artık sabit MAX_BACKUPS yerine Ayarlar
    ekranından yönetilen değeri kullandığının regresyon testi."""
    from services.app_settings import update_settings
    from services.backup import _max_backups, DEFAULT_MAX_BACKUPS

    assert _max_backups() == DEFAULT_MAX_BACKUPS == 20
    update_settings({"backup": {"max_backups": 3}})
    assert _max_backups() == 3


def test_backup_max_backups_falls_back_safely_on_invalid_value(isolated_root):
    from services.app_settings import update_settings
    from services.backup import _max_backups, DEFAULT_MAX_BACKUPS

    update_settings({"backup": {"max_backups": -5}})
    assert _max_backups() == DEFAULT_MAX_BACKUPS
