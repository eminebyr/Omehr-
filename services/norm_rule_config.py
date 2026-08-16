from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from services.runtime_paths import runtime_root

_DEFAULTS = {
    'mode':'family',
    'family_aliases':{},
    'separate_roles':[],
    'assistant_balance':{'enabled':True,'minimum_main_current':1,'pairs':{}},
}


@lru_cache(maxsize=8)
def _load_norm_rules_cached(path_text: str, mtime_ns: int) -> dict:
    p = Path(path_text)
    if not p.exists():
        return _DEFAULTS
    try:
        raw=json.loads(p.read_text(encoding='utf-8'))
        return {**_DEFAULTS, **raw}
    except Exception:
        return _DEFAULTS


def load_norm_rules() -> dict:
    """DÜZELTME (kritik test-izolasyon + çok kiracılı risk — AYNI hata
    sınıfı services/feature_flags.py'de bulunup düzeltilmişti): önceden
    @lru_cache(maxsize=1) PARAMETRESİZ olduğu için, İLK çağrının sonucu
    (hangi kiracının config_norm_rules.json'u olursa olsun) SONSUZA DEK
    önbellekleniyordu. Bu, family_balance.py'nin 'minimum_main_current'
    güvenlik kuralını (0 ana personelle norm ASLA kapanmaz) YANLIŞ bir
    kiracının/testin ayarına göre uygulamasına yol açabilirdi. Artık
    dosya yolu+mtime'a göre anahtarlanır."""
    p = runtime_root() / 'config_norm_rules.json'
    if not p.exists():
        return _load_norm_rules_cached(str(p), -1)
    return _load_norm_rules_cached(str(p), p.stat().st_mtime_ns)


load_norm_rules.cache_clear = _load_norm_rules_cached.cache_clear  # geriye dönük uyumluluk
