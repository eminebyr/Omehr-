from __future__ import annotations

"""
SAF METİN/VERİ NORMALİZASYON YARDIMCILARI (P2 — engine_core.py
modülerleştirme, ilk adım)
=====================================================================
engine_core.py 2158 satırdı. Bu modüldeki fonksiyonlar (txt/canon/col/
req gibi) SAF metin/veri normalizasyon yardımcılarıdır — Excel/pandas
dışında hiçbir dış duruma bağımlı değildir, engine_core.py boyunca
(51+38+32+26 kez) yoğun şekilde kullanılır. engine_core.py bunları AYNI
İSİMLERLE geri import eder, mevcut hiçbir çağrı noktası değişmedi.
"""

import unicodedata

import numpy as np
import pandas as pd


def _region_name(v):
    c=canon(v)
    aliases={'ali tekin':'ALİ ÇELİK','ali celik':'ALİ ÇELİK',
             'cuneyt cikrikci ayse avcu':'CÜNEYT ÇIKRIKÇI - AYŞE AVCU',
             'derya yardimci':'DERYA YARDIMCI','ertan teki':'ERTAN TEKİ'}
    return aliases.get(c,txt(v).strip())

def _title_key(v):
    c=canon(v)
    aliases={'online sofor':'online sofor','sanal market soforu':'online sofor',
             'online toplayici':'online toplayici','sanal market toplayici':'online toplayici',
             'unlu mamuller':'unlu mamuller','parttime':'part time','part time':'part time'}
    return aliases.get(c,c)

def product_name():
    return 'OMEHR Norm Kadro, Transfer ve İş Gücü Optimizasyon Platformu'

def _repair_mojibake(value):
    s = '' if value is None else str(value)
    # UTF-8 metnin cp1252/latin1 olarak yanlış açıldığı yaygın durumları onar.
    for source in ('latin1', 'cp1252'):
        try:
            fixed = s.encode(source).decode('utf-8')
            if sum(fixed.count(ch) for ch in 'ÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß├┼─') < sum(s.count(ch) for ch in 'ÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß├┼─'):
                s = fixed
        except Exception:
            # NOT: Bu except BİLEREK loglanmıyor. Bu, "onarım dene, işe
            # yaramazsa vazgeç" sezgisel bir denemedir — DOĞRU şekilde
            # kodlanmış her Türkçe karakter (ğ, ı, İ, Ç, Ö, Ü vb.) burada
            # encode() sırasında NORMAL ve BEKLENEN şekilde hata verir
            # (bu bir "yutulan hata" değil, olağan kontrol akışıdır).
            # log_swallowed buraya eklenmişti ama her Türkçe metin satırında
            # tetiklendiği için logu anlamsızca dolduruyordu; kaldırıldı.
            pass
    return s

def txt(v):
    if v is None or (isinstance(v,float) and np.isnan(v)):
        return ''
    return _repair_mojibake(v).strip()

def canon(v):
    s=txt(v).casefold().replace('ı','i')
    return ''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
def _store_key(v):
    """Mağaza adındaki boşluk, tire ve yaygın ad farklarını tek anahtara indirir."""
    k=''.join(c for c in canon(v) if c.isalnum())
    aliases={
        'buca2menderes':'buca2',
        'bucamenderes':'buca2',
        'buca':'bucafirat',
        'efeler':'aydinefeler',
        'torbali':'torbali1',
    }
    return aliases.get(k,k)
def numeric(s): return pd.to_numeric(s,errors='coerce').fillna(0)

# Mağaza raporlarında kullanılacak kurumsal unvan sırası.
# Aynı unvanın "YÖNETİCİ ELİT" / "ELİT YÖNETİCİ" gibi farklı yazımları
# tek sırada değerlendirilir. Listede bulunmayan unvanlar en altta alfabetik kalır.
UNVAN_SIRASI = [
    'elit yonetici',
    'uzman yonetici',
    'yonetici',
    'yonetici yardimcisi',
    'kasiyer',
    'kasiyer yardimcisi',
    'uzman reyon gorevlisi',
    'reyon gorevlisi',
    'uzman bakliyat',
    'bakliyat',
    'elit sarkuteri',
    'uzman sarkuteri',
    'sarkuteri',
    'sarkuteri yardimcisi',
    'elit manav',
    'uzman manav',
    'manav',
    'manav yardimcisi',
    'manav terazi',
    'elit kasap',
    'uzman kasap',
    'kasap',
    'kasap yardimcisi',
    'unlu mamuller',
    'sanal market soforu',
    'sanal market toplayici',
    'part time',
]
_UNVAN_SIRA_MAP = {u:i for i,u in enumerate(UNVAN_SIRASI)}

def unvan_anahtari(value):
    """Unvanı kurumsal sıralama için standartlaştırır."""
    c=canon(value)
    # Veri kaynağındaki ters kelime sıralarını ve yaygın yazım çeşitlerini eşleştir.
    aliases={
        'yonetici elit':'elit yonetici', 'magaza yoneticisi elit':'elit yonetici',
        'elit magaza yoneticisi':'elit yonetici',
        'yonetici uzman':'uzman yonetici', 'magaza yoneticisi uzman':'uzman yonetici',
        'uzman magaza yoneticisi':'uzman yonetici', 'magaza yoneticisi':'yonetici',
        'yonetici yardimcisi elit':'yonetici yardimcisi',
        'reyon gorevlisi uzman':'uzman reyon gorevlisi', 'uzman reyon':'uzman reyon gorevlisi',
        'bakliyat uzman':'uzman bakliyat',
        'sarkuteri elit':'elit sarkuteri', 'sarkuteri uzman':'uzman sarkuteri',
        'manav elit':'elit manav', 'manav uzman':'uzman manav',
        'kasap elit':'elit kasap', 'kasap uzman':'uzman kasap',
        'online sofor':'sanal market soforu', 'online soforu':'sanal market soforu',
        'sanal market sofor':'sanal market soforu',
        'online toplayici':'sanal market toplayici', 'online market toplayici':'sanal market toplayici',
        'sanal market toplatici':'sanal market toplayici',
        'unlu mamul':'unlu mamuller',
    }
    return aliases.get(c,c)

def unvan_sira_no(value):
    return _UNVAN_SIRA_MAP.get(unvan_anahtari(value), len(UNVAN_SIRASI)+100)

def unvan_sirali(df, grup_kolonlari=None, unvan_kolonu='Unvan'):
    """DataFrame'i grup kolonları içinde tanımlı kurumsal unvan sırasına dizer."""
    if df is None or df.empty or unvan_kolonu not in df.columns:
        return df
    x=df.copy()
    x['_UnvanSira']=x[unvan_kolonu].map(unvan_sira_no)
    x['_UnvanAlfa']=x[unvan_kolonu].map(canon)
    by=list(grup_kolonlari or [])+['_UnvanSira','_UnvanAlfa']
    x=x.sort_values(by,kind='stable').drop(columns=['_UnvanSira','_UnvanAlfa'])
    return x
def col(df,*names):
    mp={canon(c):c for c in df.columns}
    for n in names:
        if canon(n) in mp:return mp[canon(n)]
    return None
def req(df,*names):
    c=col(df,*names)
    if not c: raise ValueError('Eksik sutun: '+ ' / '.join(names))
    return c
