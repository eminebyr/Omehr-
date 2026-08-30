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

# DÜZELTME (unvan kademelendirmesi genelleştirildi, 29 Ağustos 2026):
# family_aliases ve assistant_balance.pairs önceden YALNIZ config_norm_
# rules.json'da elle yazılı 4 aile (YÖNETİCİ/MANAV/KASAP/ŞARKÜTERİ) için
# çalışıyordu — yeni bir unvan (ör. Kasiyer) için "Uzman Kasiyer"/"Elit
# Kasiyer" kademesi ya da "Kasiyer Yardımcısı" eklense bile, kod
# değişmeden bu davranışa OTOMATİK kavuşamıyordu. Aşağıdaki iki fonksiyon
# (resolve_family_key, resolve_assistant_pairs) bu iki deseni GENELLEŞTİRİR:
#   1) "UZMAN X" / "ELİT X" -> otomatik olarak "X" ailesine sayılır.
#   2) "X YARDIMCISI" -> otomatik olarak "X" ile aile dengelemesine girer.
# config'deki elle yazılı family_aliases/pairs HER ZAMAN ÖNCELİKLİDİR —
# bu otomatik kural yalnız config'te açıkça tanımlanmamış unvanlar için
# bir tamamlayıcıdır (üzerine yazmaz). separate_roles'ta olan bir unvan
# bu otomatik kuraldan tamamen muaf tutulur (elle "dokunma" istisnası).
#
# ÖNEMLİ: normalize için src.text_utils._title_key/canon KASITLI olarak
# kullanılıyor — bu, src/state_engine.py'nin norm/personel eşleştirmesinde
# kullandığı BİREBİR AYNI anahtar üretimidir. Burada AYRI/BENZER bir
# normalize fonksiyonu yazmak (ör. yalnız büyük harfe çevirme), iki
# tarafın farklı anahtar ürettiği ve sessizce eşleşmediği bir sınıf
# hataya yol açardı — services/family_balance.py'nin ÖNCEDEN kendi ayrı
# _key() fonksiyonuyla yaşadığı senkronizasyon riskiyle aynısı.
from src.text_utils import _title_key as _norm_title_key


def resolve_family_key(real_title: object, rules: dict) -> str | None:
    """"UZMAN X"/"ELİT X" -> "X" otomatik kademe birleştirmesi.

    Yalnız unvan TAM OLARAK "uzman " veya "elit " ile BAŞLIYORSA eşleşir
    (ör. "MANAV TERAZİ" gibi başka bir kelimeyle başlayan/biten unvanlar
    ASLA yanlışlıkla yakalanmaz — sadece prefix kontrolü, "içeriyor mu"
    değil). Eşleşme yoksa None döner (çağıran, mevcut family_aliases/
    Departman mantığına düşer). Dönüş değeri _title_key formatındadır —
    çağıran ek normalize YAPMAMALIDIR.
    """
    separate = {_norm_title_key(v) for v in (rules.get('separate_roles') or [])}
    key = _norm_title_key(real_title)
    if not key or key in separate:
        return None
    for prefix in ('uzman ', 'elit '):
        if key.startswith(prefix):
            base = key[len(prefix):].strip()
            if base and base not in separate:
                return base
    return None


def resolve_assistant_pairs(rules: dict, known_titles: set[str] | None = None) -> dict:
    """assistant_balance.pairs sözlüğünü, config'te açıkça YAZILMAMIŞ her
    "X YARDIMCISI" unvanı için otomatik "X" -> "X YARDIMCISI" eşleşmesiyle
    genişletir. Config'teki elle yazılı çiftler her zaman aynen korunur ve
    ÖNCELİKLİDİR (bu fonksiyon onların üzerine yazmaz, yalnız eksik olanı
    ekler). known_titles verilmezse yalnız config'teki çiftler döner
    (otomatik genişletme için normx/staffx'teki gerçek unvan listesi
    gerekir — çağıran bunu sağlar). Anahtarlar/değerler _title_key
    formatındadır — çağıran ek normalize YAPMAMALIDIR.
    """
    balance = rules.get('assistant_balance') or {}
    explicit = {
        _norm_title_key(k): _norm_title_key(v)
        for k, v in (balance.get('pairs') or {}).items()
    }
    separate = {_norm_title_key(v) for v in (rules.get('separate_roles') or [])}
    result = dict(explicit)
    if not known_titles:
        return result
    already_assistants = set(explicit.values())
    suffix = _norm_title_key('YARDIMCISI')
    for title in known_titles:
        key = _norm_title_key(title)
        if not key.endswith(' ' + suffix) or key in separate:
            continue
        if key in already_assistants:
            continue  # config'te zaten başka bir ana unvana bağlanmış
        main = key[: -(len(suffix) + 1)].strip()
        if not main or main in separate or main in result:
            continue  # config'te bu ana unvan için zaten elle bir eşleşme var
        result[main] = key
    return result


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
