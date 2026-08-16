"""src.feature_flags — arıza durumunda güvenli (fail-closed) varsayılanlar.

Kod incelemesinde yakalanan gerçek bir tutarsızlık: config_features.json
BOZULURSA (var ama okunamıyorsa) sistem eskiden TÜM AI özelliklerini
(ai_enabled, demand_forecast_enabled, cost_roi_enabled...) sessizce AÇIK
bırakıyordu — kod yorumu "güvenli varsayılanlar" dese de gerçek davranış
tam tersiydi. Bu testler iki farklı durumu ayırt eder:
  1. Dosya hiç YOK (ilk kurulum) -> her şey açık kalması makul.
  2. Dosya VAR ama bozuk (arıza) -> karar üreten özellikler KAPALI,
     izleme/raporlama özellikleri AÇIK kalmalı.
"""
from __future__ import annotations


def test_fresh_install_no_config_file_defaults_to_all_enabled(isolated_root):
    """config_features.json hiç yoksa (taze kurulum), ürünün temel değer
    önerisi olan AI özellikleri varsayılan olarak açık olmalı."""
    from src.feature_flags import all_features

    all_features.cache_clear()
    f = all_features()
    assert f["ai_enabled"] is True
    assert f["demand_forecast_enabled"] is True


def test_corrupted_config_file_fails_closed_on_decision_features(isolated_root):
    """REGRESYON testi: config_features.json VAR ama bozuksa, karar üreten
    (öneri/tahmin üreten) özellikler KAPALI olmalı — eskiden hepsi AÇIK
    kalıyordu, bu ciddi bir tutarsızlıktı."""
    from src.feature_flags import all_features

    (isolated_root / "config_features.json").write_text("{bozuk json!!!", encoding="utf-8")
    all_features.cache_clear()

    f = all_features()
    assert f["ai_enabled"] is False
    assert f["demand_forecast_enabled"] is False
    assert f["cost_roi_enabled"] is False
    assert f["transfer_optimization_enabled"] is False


def test_corrupted_config_file_keeps_observability_features_enabled(isolated_root):
    """Bozuk config'de dahi izleme/raporlama özellikleri (otonom karar
    üretmezler) açık kalmalı — 'her şeyi kapat' değil, 'yalnız karar
    üreten özellikleri kapat' ilkesi."""
    from src.feature_flags import all_features

    (isolated_root / "config_features.json").write_text("{bozuk json!!!", encoding="utf-8")
    all_features.cache_clear()

    f = all_features()
    assert f["model_drift_enabled"] is True
    assert f["data_quality_report_enabled"] is True
    assert f["operational_kpi_enabled"] is True


def test_valid_config_file_values_take_precedence_over_defaults(isolated_root):
    """Dosya GEÇERLİYSE, içindeki değerler (kısmi olsa bile) varsayılanların
    önüne geçmeli — yazılmayan anahtarlar için varsayılan kullanılmalı."""
    from src.feature_flags import all_features
    import json

    (isolated_root / "config_features.json").write_text(
        json.dumps({"ai_enabled": False}), encoding="utf-8"
    )
    all_features.cache_clear()

    f = all_features()
    assert f["ai_enabled"] is False  # dosyadan
    assert f["demand_forecast_enabled"] is True  # dosyada yok, varsayılan


def test_getter_functions_reflect_corrupted_config_fallback(isolated_root):
    """Ham all_features() sözlüğü değil, dışa açık getter fonksiyonlarının
    (ai_features_enabled, demand_forecast_enabled) da doğru davrandığı
    doğrulanır — bunlar gerçek kod tabanında çağrılan fonksiyonlardır."""
    from src.feature_flags import all_features, ai_features_enabled, demand_forecast_enabled, model_drift_enabled

    (isolated_root / "config_features.json").write_text("{bozuk!!!", encoding="utf-8")
    all_features.cache_clear()

    assert ai_features_enabled() is False
    assert demand_forecast_enabled() is False
    assert model_drift_enabled() is True
