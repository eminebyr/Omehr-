"""EXCEL OKUMA KÖPRÜSÜ (shim) — pandas.read_excel'i, GİRDİ dosyasına
yapılan çağrılar için şeffaf biçimde veritabanına yönlendirir.

NEDEN BU YAKLAŞIM: Kod tabanında 30'dan fazla dosya, input Excel'ini
DOĞRUDAN `pd.read_excel(INPUT, sheet_name=...)` ile okuyor (src/
data_loading.py::load() üzerinden DEĞİL). Bunların hepsini tek tek
değiştirmek yerine (yüksek hata riski, haftalarca sürer), TEK bir
merkezi noktadan `pandas.read_excel`'in kendisi sarmalanır. Python'da
`import pandas as pd; pd.read_excel(...)` deseni (kod tabanındaki TEK
desen — `from pandas import read_excel` hiçbir yerde kullanılmıyor,
doğrulandı) fonksiyonu HER ÇAĞRIDA `pandas` modülünün GÜNCEL
`read_excel` özniteliğinden okur; bu da modül düzeyinde bir maymun-yama
(monkeypatch) ile TÜM 30+ çağrı noktasını, HİÇBİRİNİ değiştirmeden
düzeltmeyi mümkün kılar.

GÜVENLİ AYIRT ETME: Yalnızca dosya adı OMEHR_AI_NORM_TRANSFER_INPUT.xlsx
İLE EŞLEŞEN çağrılar yönlendirilir. Üretilen ÇIKTI dosyalarını
(V19_AI_Norm_Sonuclari.xlsx, OMEHR_Yonetici_Raporu.xlsx, tahmin
sonuçları vb.) okuyan onlarca ayrı çağrı ETKİLENMEZ — bunlar zaten
Python motorunun ÜRETTİĞİ gerçek Excel dosyalarıdır ve girdi kaynağından
bağımsız olarak hep Excel olarak kalmaya devam eder (rapor/Power BI/
paylaşım formatı olarak).

KURULUM: main.py, web/app.py, worker.py gibi giriş noktalarının EN
BAŞINDA `install()` çağrılmalıdır (services/input_data_access henüz
import edilmeden önce fark etmez — kritik olan pd.read_excel'in İLK
GERÇEK ÇAĞRIDAN önce sarmalanmış olmasıdır).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

_ORIJINAL_READ_EXCEL = pd.read_excel
_KURULU = False

_GIRDI_DOSYA_ADI = "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"


def _girdi_dosyasi_mi(io) -> bool:
    try:
        if isinstance(io, (str, Path)):
            return Path(io).name == _GIRDI_DOSYA_ADI
    except Exception:
        return False
    return False


def _db_modu_aktif() -> bool:
    return os.getenv("OMEHR_INPUT_SOURCE", "excel").strip().lower() == "db"


def _yamali_read_excel(io, sheet_name=0, **kwargs):
    if _db_modu_aktif() and _girdi_dosyasi_mi(io):
        from services.input_data_access import read_sheet, read_all_sheets

        if sheet_name is None:
            return read_all_sheets()
        if isinstance(sheet_name, str):
            return read_sheet(sheet_name)
        if isinstance(sheet_name, (list, tuple)):
            return {s: read_sheet(s) for s in sheet_name}
        # int/diğer indeks türleri şu an desteklenmiyor — kod tabanında
        # input dosyası için hiçbir yerde kullanılmadığı doğrulandı
        # (yalnız sheet_name=None veya sheet_name=str). Yine de bir
        # gün eklenirse ORİJİNAL Excel okumaya sessizce düşer (veri
        # kaybı yerine en azından çalışır durum korunur).
    return _ORIJINAL_READ_EXCEL(io, sheet_name=sheet_name, **kwargs)


def install() -> None:
    """pandas.read_excel'i sarmalar. Birden çok kez çağrılması güvenlidir
    (yalnız ilk çağrıda gerçekten yamalar)."""
    global _KURULU
    if _KURULU:
        return
    pd.read_excel = _yamali_read_excel
    _KURULU = True


def uninstall() -> None:
    """Yalnızca testlerde orijinal davranışa dönmek için kullanılır."""
    global _KURULU
    pd.read_excel = _ORIJINAL_READ_EXCEL
    _KURULU = False
