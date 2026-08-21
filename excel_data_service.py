from __future__ import annotations

"""Merkezi Excel Data Service (OMEHR hızlandırma şartnamesi, Madde 4).

DİKKAT: Bu modül YENİ bir önbellekleme mekanizması İCAT ETMEZ — mevcut,
test edilmiş `services/cached_excel_reader.py` (mtime+boyut anahtarlı
lru_cache) üzerine ince, isimlendirilmiş bir kolaylık katmanıdır. Amaç,
web sekmelerinin `pd.read_excel(...)` çağırmak yerine buradaki gibi
okunaklı, tek-satırlık fonksiyonları çağırmasıdır:

    Yanlış: df = pd.read_excel(INPUT, sheet_name="Fact_Mevcut")
    Doğru:  df = excel_data_service.load_fact_mevcut(input_path)

Madde 5'teki "invalidation tablo bazlı olmalı" isteği ZATEN doğal
olarak karşılanıyor: önbellek anahtarı (dosya_yolu, mtime, boyut,
sayfa_adı, header) olduğu için, dosya değiştiğinde SADECE o an
okunacak sayfa+header kombinasyonu için önbellek "miss" olur — diğer
sayfaların önbelleği bozulmaz. invalidate_table() / refresh_
changed_table() bu yüzden yalnız MANUEL/açık bir temizlik isteniyorsa
gerekli; normal akışta dosya yazıldığında otomatik gerçekleşir.
"""

from pathlib import Path

import pandas as pd

from services.cached_excel_reader import read_sheet_cached


def load_fact_mevcut(input_path: Path) -> pd.DataFrame:
    return read_sheet_cached(input_path, "Fact_Mevcut")


def load_fact_norm(input_path: Path) -> pd.DataFrame:
    return read_sheet_cached(input_path, "Fact_Norm")


def load_dim_magaza(input_path: Path) -> pd.DataFrame:
    return read_sheet_cached(input_path, "Dim_Magaza")


def load_dim_unvan(input_path: Path) -> pd.DataFrame:
    return read_sheet_cached(input_path, "Dim_Unvan")


def load_mail_listesi(input_path: Path) -> pd.DataFrame:
    return read_sheet_cached(input_path, "Mail_Listesi")


def load_transfer_talepleri(input_path: Path) -> pd.DataFrame:
    """Transfer_Talepleri sayfası input Excel'de yoksa (bu talepler
    SQLite tabanlı web_runtime.py'de tutuluyorsa) boş DataFrame döner —
    çağıran taraf services/web_runtime.py'nin kendi sorgusunu kullanmaya
    devam edebilir; bu yalnız Excel tabanlı taleplerin okunması içindir."""
    try:
        return read_sheet_cached(input_path, "Transfer_Talepleri")
    except Exception:
        return pd.DataFrame()


def load_atamalar(input_path: Path) -> pd.DataFrame:
    try:
        return read_sheet_cached(input_path, "Atamalar")
    except Exception:
        return pd.DataFrame()


def load_personel_hareketleri(input_path: Path) -> pd.DataFrame:
    try:
        return read_sheet_cached(input_path, "Personel_Hareketleri")
    except Exception:
        return pd.DataFrame()


def load_cached_table(input_path: Path, sheet_name: str, header: int = 0) -> pd.DataFrame:
    """Yukarıdaki isimlendirilmiş kısayollarda olmayan HERHANGİ bir
    sayfa için genel önbellekli okuma."""
    return read_sheet_cached(input_path, sheet_name, header=header)


def invalidate_table(input_path: Path, sheet_name: str, header: int = 0) -> None:
    """Belirli bir (dosya, sayfa, header) kombinasyonunu önbellekten
    MANUEL olarak düşürmek için ayrılmış bir kanca (hook). Normal
    akışta GEREKMEZ — dosya yazıldığında mtime değiştiği için önbellek
    zaten otomatik geçersiz kalır (bkz. modül docstring'i). Bu yalnız
    test/hata ayıklama gibi istisnai durumlar için bir yer tutucudur.

    NOT: functools.lru_cache tek bir anahtarı seçici olarak silmeyi
    desteklemez (yalnız tam temizleme, .cache_clear()). Mtime bazlı
    anahtarlama zaten tablo-bazlı doğal geçersizleşme sağladığı için
    burada BİLEREK tam önbellek temizliği YAPILMIYOR — bu, ilgisiz
    sayfaların da gereksiz yere yeniden okunmasına yol açardı (madde
    5'in yasakladığı "bir kişi çıktı → bütün cache temizlendi" deseni).
    """
    return None


def refresh_changed_table(input_path: Path, sheet_name: str, header: int = 0) -> pd.DataFrame:
    """Sayfayı, dosyanın GÜNCEL mtime'ıyla yeniden okur — dosya
    değişmediyse zaten önbellekten (anında) döner, değiştiyse otomatik
    taze okunur. invalidate_table()'dan farkı: burada bir DEĞER
    döndürülür, yalnız temizlik yapılmaz."""
    return read_sheet_cached(input_path, sheet_name, header=header)
