from __future__ import annotations

"""
ADRES/MESAFE HESAPLAMA YARDIMCILARI (P2 — engine_core.py
modülerleştirme, ikinci adım)
=====================================================================
Mağaza/personel adres haritalama ve haversine mesafe hesabı — Excel/
pandas dışında hiçbir dış duruma bağımlı değildir.
"""

import math

import pandas as pd

from src.text_utils import canon, col, txt


def address_map(sheets):
    df=sheets.get('Magaza_Adres',sheets.get('Dim_Magaza',pd.DataFrame()))
    if df.empty:return {}
    mc=col(df,'Mağaza','Magaza'); lat=col(df,'Enlem','Latitude'); lon=col(df,'Boylam','Longitude'); il=col(df,'İl','Il'); ilce=col(df,'İlçe','Ilce'); adr=col(df,'Adres')
    out={}
    for _,r in df.iterrows():out[canon(r.get(mc))]={'lat':r.get(lat) if lat else None,'lon':r.get(lon) if lon else None,'il':txt(r.get(il)) if il else '', 'ilce':txt(r.get(ilce)) if ilce else '', 'adres':txt(r.get(adr)) if adr else ''}
    return out

def distance(a,b,am):
    x,y=am.get(canon(a),{}),am.get(canon(b),{})
    try:
        la1,lo1,la2,lo2=map(float,[x.get('lat'),x.get('lon'),y.get('lat'),y.get('lon')]); R=6371
        p1,p2=math.radians(la1),math.radians(la2); dp=math.radians(la2-la1); dl=math.radians(lo2-lo1)
        q=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        val=R*2*math.atan2(math.sqrt(q),math.sqrt(1-q))
        if not math.isfinite(val): raise ValueError('invalid coordinate')
        return val
    except Exception:
        # NOT: Bilerek loglanmıyor — kılavuzda da belirtildiği gibi
        # "Dummy - değiştiriniz" yer tutucu koordinatlar tamamlanana kadar
        # bu düşüş normal ve beklenen bir durumdur; il/ilçe eşleşmesine
        # geri düşülür (aşağıda).
        if canon(x.get('ilce')) and canon(x.get('ilce'))==canon(y.get('ilce')):return 5
        if canon(x.get('il')) and canon(x.get('il'))==canon(y.get('il')):return 30
        return 120

def person_address_map(sheets):
    """Personel adres/tercih verisini açık adresi çıktılara taşımadan indeksler."""
    df=sheets.get('Personel_Adresleri',pd.DataFrame())
    if df.empty:return {}
    pid=col(df,'PersonelID'); name=col(df,'İsim Soyisim','Ad Soyad'); lat=col(df,'Ev Enlem','Enlem'); lon=col(df,'Ev Boylam','Boylam')
    approval=col(df,'Transfer Onayı'); max_minutes=col(df,'Maksimum Tek Yön Yol (dk)','Maksimum Yol (dk)')
    transport=col(df,'Ulaşım Şekli'); preferred=col(df,'Tercih Edilen Mağazalar'); status=col(df,'Veri Durumu')
    out={}
    for _,r in df.iterrows():
        record={
            'lat':r.get(lat) if lat else None,'lon':r.get(lon) if lon else None,
            'approval':txt(r.get(approval)) if approval else 'Değerlendirilebilir',
            'max_minutes':pd.to_numeric(pd.Series([r.get(max_minutes)]),errors='coerce').fillna(60).iloc[0] if max_minutes else 60,
            'transport':txt(r.get(transport)) if transport else '',
            'preferred':txt(r.get(preferred)) if preferred else '',
            'status':txt(r.get(status)) if status else '',
        }
        person_id=txt(r.get(pid)) if pid else ''
        person_name=txt(r.get(name)) if name else ''
        if person_id and person_name:out[(canon(person_id),canon(person_name))]=record
        if person_id:out.setdefault((canon(person_id),''),record)
    return out

def _point_distance(lat1,lon1,lat2,lon2):
    try:
        la1,lo1,la2,lo2=map(float,[lat1,lon1,lat2,lon2]); R=6371
        p1,p2=math.radians(la1),math.radians(la2); dp=math.radians(la2-la1); dl=math.radians(lo2-lo1)
        q=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return R*2*math.atan2(math.sqrt(q),math.sqrt(max(0,1-q)))
    except Exception:
        # NOT: Bilerek loglanmıyor — bkz. yukarıdaki distance() notu.
        return None

def _home_metrics(person,source_store,target_store,stores,people,person_id_col,person_name_col):
    key=(canon(person.get(person_id_col)),canon(person.get(person_name_col)))
    home=people.get(key) or people.get((key[0],'')) or {}
    source,target=stores.get(canon(source_store),{}),stores.get(canon(target_store),{})
    current_km=_point_distance(home.get('lat'),home.get('lon'),source.get('lat'),source.get('lon'))
    target_km=_point_distance(home.get('lat'),home.get('lon'),target.get('lat'),target.get('lon'))
    gain=(current_km-target_km) if current_km is not None and target_km is not None else None
    target_minutes=(target_km*2.2+5) if target_km is not None else None
    return home,current_km,target_km,gain,target_minutes
