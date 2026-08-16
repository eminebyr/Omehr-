from __future__ import annotations

"""
COĞRAFİ/MESAFE VE TRANSFER ÖNERİ FONKSİYONLARI (P2 — modülerleştirme,
üçüncü adım)
=====================================================================
Mağaza/personel koordinatları, ev-şube mesafesi, Dijkstra tabanlı en
kısa yol ve transfer önerisi/harita üretimi — hiçbiri Streamlit'e
(st.*) bağımlı değildir, sadece veri alıp veri/figür döndürürler.
"""

import heapq
from urllib.parse import quote_plus

import pandas as pd
import plotly.graph_objects as go

from web.formatting import haversine_km, norm_text


def store_coordinates(sheets):
    for name in ('Magaza_Adres','Dim_Magaza'):
        x=sheets.get(name,pd.DataFrame()).copy()
        if x.empty: continue
        cols={norm_text(c):c for c in x.columns}
        mid=cols.get('MAGAZAID'); mag=cols.get('MAGAZA'); lat=cols.get('ENLEM'); lon=cols.get('BOYLAM')
        if lat and lon and (mid or mag):
            keep=[c for c in (mid,mag,lat,lon) if c]
            y=x[keep].copy(); y.columns=[('MağazaID' if c==mid else 'Mağaza' if c==mag else 'Enlem' if c==lat else 'Boylam') for c in keep]
            return y.drop_duplicates(subset=['MağazaID'] if 'MağazaID' in y else ['Mağaza'])
    return pd.DataFrame()


def store_addresses(sheets):
    x=sheets.get('Magaza_Adres',pd.DataFrame()).copy()
    if x.empty or 'Mağaza' not in x.columns:
        return {}
    return {
        norm_text(r.get('Mağaza')):(str(r.get('Adres')).strip() if pd.notna(r.get('Adres')) else '')
        for _,r in x.iterrows()
    }


def person_address_lookup(sheets):
    """Açık adresi ekrana taşımadan personelin koordinat ve tercihlerini indeksler."""
    x=sheets.get('Personel_Adresleri',pd.DataFrame()).copy()
    if x.empty or 'PersonelID' not in x.columns:
        return {}
    out={}
    for _,r in x.iterrows():
        pid=str(r.get('PersonelID','')).strip()
        name=norm_text(r.get('İsim Soyisim',''))
        if not pid:
            continue
        record={
            'lat':pd.to_numeric(r.get('Ev Enlem'),errors='coerce'),
            'lon':pd.to_numeric(r.get('Ev Boylam'),errors='coerce'),
            'approval':str(r.get('Transfer Onayı','Değerlendirilebilir')).strip(),
            'max_minutes':pd.to_numeric(r.get('Maksimum Tek Yön Yol (dk)'),errors='coerce'),
            'transport':str(r.get('Ulaşım Şekli','')).strip(),
            'preferred':str(r.get('Tercih Edilen Mağazalar','')).strip(),
            'status':str(r.get('Veri Durumu','')).strip(),
        }
        out[(pid,name)]=record
        out.setdefault((pid,''),record)
    return out


def transfer_distance_lookup(sheets):
    """Input'taki mesafe tablosunu kaynak/hedef/unvan anahtarıyla indeksler."""
    x=sheets.get('Transfer_Kisitlari',pd.DataFrame()).copy()
    required={'Kaynak MağazaID','Hedef MağazaID','Unvan','Tahmini Mesafe (Km)'}
    if x.empty or not required.issubset(x.columns):
        return {}
    out={}
    for _,r in x.iterrows():
        km=pd.to_numeric(r.get('Tahmini Mesafe (Km)'),errors='coerce')
        if pd.notna(km) and float(km)>0:
            role=''.join(ch for ch in norm_text(r.get('Unvan')) if ch.isalnum())
            out[(str(r.get('Kaynak MağazaID','')),str(r.get('Hedef MağazaID','')),role)]=float(km)
            out[(str(r.get('Hedef MağazaID','')),str(r.get('Kaynak MağazaID','')),role)]=float(km)
    return out


def input_route_distance(distance_lookup, source_id, target_id, role_id):
    """Doğrudan kayıt yoksa input mesafelerinden en kısa bağlı rotayı bulur."""
    source_id,target_id=map(str,(source_id,target_id))
    role_id=''.join(ch for ch in norm_text(role_id) if ch.isalnum())
    direct=distance_lookup.get((source_id,target_id,role_id))
    if direct is not None:
        return direct
    for generic_fallback in (False,True):
        graph={}
        edge_min={}
        for (source,target,role),km in distance_lookup.items():
            if generic_fallback or role==role_id:
                key=(source,target)
                edge_min[key]=min(float(km),edge_min.get(key,float('inf')))
        for (source,target),km in edge_min.items():
            graph.setdefault(source,[]).append((target,km))
        queue=[(0.0,source_id)]
        best={source_id:0.0}
        while queue:
            distance,node=heapq.heappop(queue)
            if node==target_id:
                return round(distance,1)
            if distance>best.get(node,float('inf')):
                continue
            for neighbor,edge in graph.get(node,[]):
                candidate=distance+edge
                if candidate<best.get(neighbor,float('inf')):
                    best[neighbor]=candidate
                    heapq.heappush(queue,(candidate,neighbor))
    return None


def transfer_recommendations(fm, detail, sheets, scenario='Dengeli', limit=100):
    surplus=detail[detail['Fazla']>0].copy(); deficit=detail[detail['Eksik']>0].copy()
    if surplus.empty or deficit.empty: return pd.DataFrame()
    coords=store_coordinates(sheets)
    addresses=store_addresses(sheets)
    people_addresses=person_address_lookup(sheets)
    input_distances=transfer_distance_lookup(sheets)
    cmap={}
    if not coords.empty:
        key='MağazaID' if 'MağazaID' in coords.columns else 'Mağaza'
        for _,r in coords.iterrows(): cmap[str(r.get(key,''))]=(r.get('Enlem'),r.get('Boylam'))
    rows=[]
    active=fm.copy()
    active["_RoleKey"] = active.get("Departman", active.get("Unvan", "")).map(
        lambda v: __import__("services.dashboard_model", fromlist=["role_key"]).role_key(v)
    )
    for _,src in surplus.iterrows():
        candidates=active[(active['MağazaID'].astype(str)==str(src['MağazaID'])) & (active['_RoleKey'].astype(str)==str(src['UnvanID']))]
        for _,person in candidates.head(int(src['Fazla'])).iterrows():
            person_id=str(person.get('PersonelID','')).strip()
            home=people_addresses.get((person_id,norm_text(person.get('İsim Soyisim','')))) or people_addresses.get((person_id,'')) or {}
            if norm_text(home.get('approval'))=='HAYIR':
                continue
            for _,dst in deficit[deficit['UnvanID'].astype(str)==str(src['UnvanID'])].iterrows():
                if str(dst['MağazaID'])==str(src['MağazaID']): continue
                c1=cmap.get(str(src['MağazaID'])) or cmap.get(str(src['Mağaza']))
                c2=cmap.get(str(dst['MağazaID'])) or cmap.get(str(dst['Mağaza']))
                km=haversine_km(*(c1+c2)) if c1 and c2 else None
                home_coord=(home.get('lat'),home.get('lon'))
                home_valid=all(pd.notna(v) for v in home_coord)
                current_home_km=haversine_km(*(home_coord+c1)) if home_valid and c1 else None
                target_home_km=haversine_km(*(home_coord+c2)) if home_valid and c2 else None
                commute_gain=(current_home_km-target_home_km) if current_home_km is not None and target_home_km is not None else None
                distance_source='Koordinat'
                origin=addresses.get(norm_text(src['Mağaza'])) or f"{src['Mağaza']}, Türkiye"
                destination=addresses.get(norm_text(dst['Mağaza'])) or f"{dst['Mağaza']}, Türkiye"
                duration_minutes=None if target_home_km is None else round(target_home_km*2.2+5)
                if km is None or pd.isna(km):
                    km=input_route_distance(input_distances,src['MağazaID'],dst['MağazaID'],src['UnvanID'])
                    distance_source='Input rota tahmini'
                maps_link=(
                    'https://www.google.com/maps/dir/?api=1'
                    f'&origin={quote_plus(origin)}&destination={quote_plus(destination)}&travelmode=driving'
                )
                same_region=norm_text(src['Bölge Sorumlusu'])==norm_text(dst['Bölge Sorumlusu'])
                risk=min(100,int(dst['Eksik'])*15+20)
                km_score=km if km is not None else 9999
                branch_score=0 if km is None else max(0,min(100,100-km*2))
                home_score=50 if target_home_km is None else max(0,min(100,100-target_home_km*2.5))
                satisfaction_score=50 if commute_gain is None else max(0,min(100,50+commute_gain*4))
                approval_score=100 if norm_text(home.get('approval'))=='EVET' else 65
                region_score=100 if same_region else 70
                total_score=branch_score*.25+home_score*.25+satisfaction_score*.20+approval_score*.15+region_score*.05+min(100,risk)*.10
                max_minutes=float(home.get('max_minutes')) if pd.notna(home.get('max_minutes')) else 60
                if duration_minutes is not None and duration_minutes>max_minutes:
                    total_score=max(0,total_score-30)
                scenario_bonus={'Aynı Bölge':15 if same_region else -30,'Minimum Mesafe':max(0,20-km_score),'Aynı Unvan':10,'Eve En Yakın':max(0,25-(target_home_km if target_home_km is not None else 100)),'Dengeli':0}.get(scenario,0)
                ranking_score=max(0,min(100,total_score+scenario_bonus))
                rows.append({'Personel':person.get('İsim Soyisim',''),'Kaynak Bölge':src['Bölge Sorumlusu'],'Kaynak Mağaza':src['Mağaza'],
                             'Departman':src['Unvan'],'Gerçek Unvan':person.get('Unvan',''),
                             'Hedef Bölge':dst['Bölge Sorumlusu'],'Hedef Mağaza':dst['Mağaza'],'Şubeler Arası Mesafe (km)':None if km is None else round(km,1),
                             'Ev-Mevcut Şube (km)':None if current_home_km is None else round(current_home_km,1),
                             'Ev-Hedef Şube (km)':None if target_home_km is None else round(target_home_km,1),
                             'Yol Kazancı (km)':None if commute_gain is None else round(commute_gain,1),
                             'Şubeye Yakınlık Puanı':round(branch_score,1),'Eve Yakınlık Puanı':round(home_score,1),
                             'Personel Memnuniyeti Puanı':round(satisfaction_score,1),'Transfer Onayı':home.get('approval',''),
                             'Adres Veri Durumu':home.get('status',''),
                             'Sürüş Süresi (dk)':duration_minutes,'Mesafe Kaynağı':distance_source,'Google Maps':maps_link,
                             'Hedef Risk Puanı':risk,'Senaryo':scenario,'Transfer Uygunluk Puanı':round(ranking_score,1),'Optimizasyon Puanı':round(ranking_score,1)})
    if not rows: return pd.DataFrame()
    result=pd.DataFrame(rows)
    # ŞEFFAFLIK DÜZELTMESİ (P2 — adres bazlı optimizasyon tamamlama):
    # Kanıtlanmış gerçek örnek: bir personelin coğrafi olarak EN YAKIN
    # adayı (ör. 9,5 km), o pozisyonun tek kontenjanı BAŞKA bir personele
    # (ör. 7,3 km — ondan da yakın) atandığı için kaybedilebiliyordu; sistem
    # bu durumda kullanıcıya sessizce daha uzak bir öneri (ör. 33 km)
    # gösteriyor, NEDEN diye açıklamıyordu. Bu, küresel optimizasyon olarak
    # DOĞRU bir sonuç (en yakın olan kişiye verilir) ama İK için şeffaf
    # değildi. Şimdi her kişinin teorik en iyi (coğrafi olarak en yakın)
    # adayı önceden hesaplanır; seçilen sonuç ondan farklıysa açıklanır.
    kisi_en_iyi_km = result.groupby('Personel')['Ev-Hedef Şube (km)'].min()

    result=result.sort_values(['Transfer Uygunluk Puanı','Hedef Risk Puanı'],ascending=[False,False])
    capacity={
        (str(r['Mağaza']),str(r['Unvan'])):int(r['Eksik'])
        for _,r in deficit.iterrows()
    }
    selected=[]
    used_people=set()
    for _,row in result.iterrows():
        person=str(row['Personel'])
        target_key=(str(row['Hedef Mağaza']),str(row['Departman']))
        if person in used_people or capacity.get(target_key,0)<=0:
            continue
        selected.append(row)
        used_people.add(person)
        capacity[target_key]-=1
        if len(selected)>=limit:
            break
    sonuc=pd.DataFrame(selected).reset_index(drop=True)
    if sonuc.empty:
        return sonuc

    def _aciklama(row):
        notlar = []
        en_iyi = kisi_en_iyi_km.get(row['Personel'])
        secilen = row['Ev-Hedef Şube (km)']
        if en_iyi is not None and secilen is not None and secilen > en_iyi + 0.5:
            notlar.append(
                f"Bu kişi için coğrafi olarak en yakın seçenek {en_iyi:.1f} km idi, ama o pozisyon "
                f"(kapasite dolduğu için) daha iyi uyan başka bir personele verildi."
            )
        if scenario == 'Eve En Yakın' and row.get('Yol Kazancı (km)') is not None and row['Yol Kazancı (km)'] < 0:
            notlar.append("⚠️ 'Eve En Yakın' senaryosuna rağmen bu transfer yol mesafesini KÖTÜLEŞTİRİYOR — mevcut şube zaten daha yakın, bu sadece mevcut açık pozisyonlar arasındaki en iyi seçenek.")
        if row.get('Adres Veri Durumu', '').startswith('Dummy'):
            notlar.append("Bu kişinin ev adresi henüz doğrulanmamış (varsayım) — mesafe hesapları kesin değil.")
        return " ".join(notlar)

    sonuc['Açıklama'] = sonuc.apply(_aciklama, axis=1)
    return sonuc


def transfer_distance_map(fm, detail, sheets):
    """En kısa uygun rotayı personel bazında harita üzerinde gösterir."""
    recs=transfer_recommendations(fm,detail,sheets,scenario='Minimum Mesafe',limit=500)
    if recs.empty:
        return None
    recs=recs.dropna(subset=['Şubeler Arası Mesafe (km)']).sort_values('Şubeler Arası Mesafe (km)')
    recs=recs.drop_duplicates(subset=['Personel'],keep='first').head(35)
    coords=store_coordinates(sheets)
    if recs.empty or coords.empty or 'Mağaza' not in coords.columns:
        return None
    coord_map={
        norm_text(r['Mağaza']):(pd.to_numeric(r['Enlem'],errors='coerce'),pd.to_numeric(r['Boylam'],errors='coerce'))
        for _,r in coords.iterrows()
    }
    fig=go.Figure()
    plotted=0
    for _,r in recs.iterrows():
        source=coord_map.get(norm_text(r['Kaynak Mağaza']))
        target=coord_map.get(norm_text(r['Hedef Mağaza']))
        if not source or not target or any(pd.isna(v) for v in (*source,*target)):
            continue
        hover=(
            f"<b>{r['Personel']}</b><br>"
            f"{r['Kaynak Mağaza']} → {r['Hedef Mağaza']}<br>"
            f"Departman: {r['Departman']}<br>"
            f"Gerçek unvan: {r['Gerçek Unvan']}<br>"
            f"Şubeler arası: {float(r['Şubeler Arası Mesafe (km)']):.1f} km<br>"
            f"Ev-hedef: {r.get('Ev-Hedef Şube (km)','-')} km<br>"
            f"Uygunluk: {r.get('Transfer Uygunluk Puanı','-')}/100"
        )
        # NOT: go.Scattermap harici OpenStreetMap tile sunucusuna erişim gerektirir;
        # kurumsal ağ/güvenlik duvarı arkasında bu genellikle engellenir ve harita
        # boş/yüklenmemiş görünür. Bunun yerine enlem/boylamı doğrudan eksen olarak
        # kullanan, hiçbir dış sunucuya ihtiyaç duymayan go.Scatter kullanılır.
        fig.add_trace(go.Scatter(
            x=[source[1],target[1]],y=[source[0],target[0]],mode='lines+markers',
            line={'width':2,'color':'#4472C4'},marker={'size':10,'color':['#102F64','#118B94']},
            text=[hover,hover],hovertemplate='%{text}<extra></extra>',showlegend=False,
        ))
        plotted+=1
    if not plotted:
        return None
    fig.update_layout(
        title='Kilometreye Göre Transfer Edilebilir Personel Haritası (Enlem/Boylam, harici harita sunucusu gerekmez)',
        xaxis_title='Boylam',yaxis_title='Enlem',
        margin={'l':40,'r':10,'t':45,'b':40},height=560,
    )
    return fig

