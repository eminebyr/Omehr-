"""Birleşik ürün ayarları — Ayarlar ekranının (web/tab_modules/ayarlar.py) arka
ucu.

Bu modül, ÖNCEDEN dağınık duran üç ayrı kaynağı TEK bir okuma/yazma API'si
altında toplar:
  - config_web.json   (services.management_center.ensure_config/save)
  - config_features.json (src.feature_flags — AI/özellik anahtarları)
  - services.settings (ana input dosyasının adı — salt bilgi amaçlı gösterim)

Kasıtlı olarak YAPILMAYANLAR (bilerek kapsam dışı bırakıldı):
  - "Rapor alıcıları": bunlar zaten input Excel'indeki Mail_Listesi
    sayfasında yönetiliyor. Burada AYRI bir JSON kopyası tutmak iki farklı
    "doğru kaynak" yaratır ve tutarsızlığa yol açar — bu yüzden bu ekran
    yalnız GÜNCEL listeyi salt-okunur gösterir, Excel'e yönlendirir.
  - AI güven eşiği / norm tavanı (%35 ağırlık, 1,20x tavan): bunlar
    src/ai_norm.py ve ai_operations_engine.py içinde P0 GÜVENLİK sınırı
    olarak belgelenmiş durumda. Kullanıcı arayüzünden serbestçe
    değiştirilebilir hale getirmek, bu güvenlik sınırının farkında
    olmadan gevşetilmesi riskini taşır — bu karar tek başına bir
    mühendislik kararı değil, ürün/risk kararıdır. Bu yüzden BURADA
    yalnız AÇIK/KAPALI özellik bayrakları (config_features.json)
    değiştirilebilir; sayısal güvenlik sınırları değil.
  - "Lisans bilgileri": kod tabanında hiçbir yerde gerçek bir lisanslama
    mekanizması (süre sınırı, kullanıcı sınırı, özellik kilidi vb.) yok.
    Var olmayan bir kavram için süs amaçlı bir form eklemek yanıltıcı
    olurdu — bu, önce bir ürün/lisanslama kararı gerektirir.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.exceptions import ConfigurationError
from services.runtime_paths import runtime_root

FEATURE_LABELS: dict[str, str] = {
    "ai_enabled": "AI norm önerileri",
    "executive_financial_operational_enabled": "Yönetici finansal/operasyonel analiz",
    "operational_kpi_enabled": "Operasyonel KPI görselleri",
    "cost_roi_enabled": "Maliyet / ROI analizleri",
    "demand_forecast_enabled": "Talep tahmini",
    "workload_enabled": "İş yükü endeksi",
    "transfer_optimization_enabled": "Transfer optimizasyonu",
    "model_drift_enabled": "Model drift izleme",
    "data_quality_report_enabled": "Veri kalitesi raporu",
}


def _features_path() -> Path:
    return runtime_root() / "config_features.json"


def get_feature_flags() -> dict[str, bool]:
    """config_features.json'ı DOĞRUDAN okur (feature_flags.all_features()'ın
    aksine, lru_cache kullanmaz) — Ayarlar ekranının, henüz yeniden
    başlatılmamış bir süreçte bile GÜNCEL değerleri göstermesi için."""
    from src.feature_flags import FRESH_INSTALL_DEFAULTS

    path = _features_path()
    defaults = {k: FRESH_INSTALL_DEFAULTS.get(k, True) for k in FEATURE_LABELS}
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {**defaults, **{str(k): bool(v) for k, v in raw.items() if k in FEATURE_LABELS}}
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigurationError(f"config_features.json okunamadı: {exc}") from exc


def set_feature_flags(flags: dict[str, bool]) -> None:
    """Yalnız BİLİNEN (FEATURE_LABELS'taki) anahtarları kabul eder —
    rastgele/yanlış yazılmış bir anahtarın sessizce hiçbir etkisi
    olmayan bir config satırı olarak kalmasını önler."""
    bilinmeyen = set(flags) - set(FEATURE_LABELS)
    if bilinmeyen:
        raise ConfigurationError(f"Bilinmeyen özellik anahtarı/anahtarları: {sorted(bilinmeyen)}")
    path = _features_path()
    guncel = get_feature_flags()
    guncel.update({k: bool(v) for k, v in flags.items()})
    try:
        path.write_text(json.dumps(guncel, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"config_features.json yazılamadı: {exc}") from exc

    # ÖNEMLİ: src.feature_flags.all_features() sonuçları @lru_cache ile
    # SÜRESİZ önbelleğe alır. Burada yazdığımız değişikliğin AYNI süreç
    # içinde de hemen etkili olması için önbelleği temizliyoruz.
    try:
        from src.feature_flags import all_features
        all_features.cache_clear()
    except Exception:
        pass  # feature_flags henüz import edilmemiş olabilir; sorun değil


def get_settings() -> dict[str, Any]:
    """config_web.json içeriğini döndürür (company/security/power_bi/
    notifications/approval/backup). Eksik anahtarlar varsayılanla
    tamamlanır (bkz. management_center.ensure_config)."""
    from services.management_center import ensure_config

    return ensure_config()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """base'i patch ile İÇ İÇE (recursive) birleştirir — sadece en üst
    seviyede değil, her seviyede sadece verilen alanları değiştirir.

    Bu fonksiyon olmadan (düz {**base, **patch} ile) örn.
    {"notifications": {"smtp": {"host": "..."}}} gibi bir kısmi güncelleme,
    smtp sözlüğündeki port/username/enabled gibi DOKUNULMAYAN alanları
    silerdi — bu gerçek bir bug olarak testte yakalandı, bkz.
    tests/test_app_settings.py::test_partial_smtp_update_preserves_other_smtp_fields.
    """
    sonuc = dict(base)
    for anahtar, deger in patch.items():
        if isinstance(deger, dict) and isinstance(sonuc.get(anahtar), dict):
            sonuc[anahtar] = _deep_merge(sonuc[anahtar], deger)
        else:
            sonuc[anahtar] = deger
    return sonuc


def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    """config_web.json'a KISMİ bir güncelleme uygular (yalnız verilen
    alanları, HER SEVİYEDE, iç içe birleştirir — bkz. _deep_merge).
    "security" anahtarı BİLEREK yok sayılır — parola hash
    algoritması/iterasyon sayısı gibi güvenlik ayarları bu ekrandan
    değiştirilemez (bkz. management_center.ensure_config, zaten her
    çalıştırmada varsayılana sabitleniyor)."""
    from services.management_center import _config_path, ensure_config

    guncel = ensure_config()
    patch = {k: v for k, v in patch.items() if k != "security"}
    guncel = _deep_merge(guncel, patch)
    try:
        _config_path().write_text(json.dumps(guncel, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"config_web.json yazılamadı: {exc}") from exc
    return guncel


def input_file_info() -> dict[str, Any]:
    """Ana input dosyası hakkında SALT OKUNUR bilgi (Ayarlar ekranında
    gösterim için). Dosya adını değiştirmek services/settings.py'deki
    BASDAS_INPUT_FILE ortam değişkeni ile yapılır — bilerek bu ekrandan
    DEĞİL, çünkü çalışan bir sistemde dosya adını web panelinden anlık
    değiştirmek, motorun bir sonraki adımda dosyayı bulamamasına yol
    açabilir (ortam değişkeni + yeniden başlatma daha güvenli)."""
    from services.settings import input_file_name, input_path

    path = input_path(runtime_root())
    return {
        "file_name": input_file_name(),
        "full_path": str(path),
        "exists": path.is_file(),
    }
