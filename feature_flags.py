from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from services.runtime_paths import runtime_root

# İLK KURULUM varsayılanları: config_features.json hiç YOK ise kullanılır
# (ör. taze bir kurulum, henüz Ayarlar ekranından hiçbir şey kaydedilmemiş).
# Ürünün temel değer önerisi AI destekli olduğu için burada hepsi açık
# kalması makul bir başlangıçtır — kullanıcı isterse Ayarlar'dan kapatır.
FRESH_INSTALL_DEFAULTS = {
  'ai_enabled':True,'executive_financial_operational_enabled':True,
  'operational_kpi_enabled':True,'cost_roi_enabled':True,
  'demand_forecast_enabled':True,'workload_enabled':True,
  'transfer_optimization_enabled':True,'model_drift_enabled':True,
  'data_quality_report_enabled':True,
}

# ARIZA (config_features.json VAR ama okunamıyor/bozuk) varsayılanları:
# Bu, "dosya hiç yok" ile AYNI durum DEĞİLDİR — burada muhtemelen bir
# yönetici bilerek bir yapılandırma yapmıştı (belki bazı özellikleri
# BİLEREK kapatmıştı) ve o tercih artık okunamıyor. Bu belirsizlikte
# KARAR ÜRETEN özellikler (AI önerisi, talep tahmini, maliyet/ROI,
# transfer optimizasyonu) KAPALI kalır — sistem sessizce "her şey açık"
# durumuna dönmez. İzleme/raporlama özellikleri (model drift, veri
# kalitesi, KPI/yönetici raporları) AÇIK kalır; bunlar otonom bir karar
# üretmez, yalnız mevcut veriyi gösterir.
SAFE_FALLBACK_DEFAULTS = {
  'ai_enabled':False,'executive_financial_operational_enabled':True,
  'operational_kpi_enabled':True,'cost_roi_enabled':False,
  'demand_forecast_enabled':False,'workload_enabled':True,
  'transfer_optimization_enabled':False,'model_drift_enabled':True,
  'data_quality_report_enabled':True,
}

@lru_cache(maxsize=8)
def _all_features_cached(path_text: str, mtime_ns: int) -> dict:
    p = Path(path_text)
    if not p.exists(): return FRESH_INSTALL_DEFAULTS
    try:
        raw=json.loads(p.read_text(encoding='utf-8'))
        return {**FRESH_INSTALL_DEFAULTS, **{str(k):bool(v) for k,v in raw.items()}}
    except Exception as exc:
        from services.safe_exec import log_swallowed
        log_swallowed('config_features.json bozuk/okunamıyor; KARAR ÜRETEN özellikler güvenlik için KAPATILDI (izleme özellikleri açık kaldı)',exc,level='ERROR')
        return SAFE_FALLBACK_DEFAULTS


def all_features() -> dict:
    """DÜZELTME (kritik test-izolasyon + çok kiracılı risk): önceden hem
    ROOT hem de @lru_cache(maxsize=1) (PARAMETRESİZ) ilk çağrıda
    SONSUZA DEK sabitleniyordu — OMEHR_RUNTIME_ROOT değişse bile İLK
    kiracının/testin özellik bayrakları TÜM sonraki kiracılara/testlere
    uygulanmaya devam ederdi. Artık dosya yolu+mtime'a göre anahtarlanır."""
    p = runtime_root()/'config_features.json'
    if not p.exists():
        return _all_features_cached(str(p), -1)
    return _all_features_cached(str(p), p.stat().st_mtime_ns)


all_features.cache_clear = _all_features_cached.cache_clear  # geriye dönük uyumluluk

def feature_enabled(name:str, default:bool=False)->bool:
    return bool(all_features().get(name,default))
def ai_features_enabled(): return feature_enabled('ai_enabled',True)
def executive_analysis_enabled(): return feature_enabled('executive_financial_operational_enabled',True)
def demand_forecast_enabled(): return feature_enabled('demand_forecast_enabled',False)
def model_drift_enabled(): return feature_enabled('model_drift_enabled',True)
def data_quality_report_enabled(): return feature_enabled('data_quality_report_enabled',True)
