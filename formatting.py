from __future__ import annotations

"""
SAF YARDIMCI FONKSİYONLAR (P2 — engine_core.py/web/app.py modülerleştirme,
ikinci adım)
=====================================================================
Bu modüldeki fonksiyonlar TAMAMEN SAFTIR: Streamlit'e (st.*), oturum
durumuna (session_state) veya herhangi bir paylaşılan global duruma
bağımlı DEĞİLDİR — sadece girdi alıp çıktı üretirler. Bu, onları test
etmeyi ve web/app.py'den bağımsız olarak yeniden kullanmayı kolaylaştırır.

web/app.py bu fonksiyonları AYNI İSİMLERLE geri import eder
(`from web.formatting import norm_text, tr_number, ...`) — bu yüzden
dosya içindeki 70'ten fazla çağrı noktasının HİÇBİRİNİN değişmesi
gerekmedi.
"""

import math

import pandas as pd
from services.safe_exec import log_swallowed


def norm_text(v):
    return str(v or "").strip().upper().replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")


def tr_number(value, decimals=0, suffix=""):
    number=float(pd.to_numeric(pd.Series([value]),errors="coerce").fillna(0).iloc[0])
    rendered=f"{number:,.{decimals}f}".replace(",","X").replace(".",",").replace("X",".")
    return f"{rendered}{suffix}"


def tr_money_compact(value, suffix=" TL"):
    """Büyük TL tutarlarını (metric widget'ı taşırmaması için) Milyon/Milyar olarak kısaltır."""
    number=float(pd.to_numeric(pd.Series([value]),errors="coerce").fillna(0).iloc[0])
    if abs(number)>=1_000_000_000:
        return f"{tr_number(number/1_000_000_000,2)} Milyar{suffix}"
    if abs(number)>=1_000_000:
        return f"{tr_number(number/1_000_000,1)} Milyon{suffix}"
    return tr_number(number,0,suffix)


def haversine_km(lat1, lon1, lat2, lon2):
    try:
        a1,b1,a2,b2=map(float,(lat1,lon1,lat2,lon2))
    except Exception as _exc:
        log_swallowed("web.formatting.haversine_km: beklenmeyen hata", _exc)
        return None
    r=6371.0088
    p1,p2=math.radians(a1),math.radians(a2)
    dp=math.radians(a2-a1); dl=math.radians(b2-b1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))
