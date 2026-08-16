from __future__ import annotations

"""
SENARYO/TRANSFER MOTORU (P2 — engine_core.py modülerleştirme, onuncu adım)
=====================================================================
Unvan uyumluluğu (compat), transfer havuzu, ihtiyaç listesi, dengeli/
minimum-mesafe transfer senaryoları (scipy linear_sum_assignment ile) ve
risk tablosunu üretir. state_engine'in ürettiği DataFrame'leri girdi olarak
alır.
"""

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from src.text_utils import canon, col, req, txt


from src.geo_utils import address_map, distance, person_address_map, _point_distance, _home_metrics


COMP={'reyon gorevlisi':{'reyon gorevlisi':0,'bakliyat':1,'sarkuteri yardimcisi':2},'sarkuteri yardimcisi':{'sarkuteri yardimcisi':0,'sarkuteri':2,'reyon gorevlisi':2},'kasap yardimcisi':{'kasap yardimcisi':0,'kasap':2},'manav yardimcisi':{'manav yardimcisi':0,'manav':2,'manav terazi':1},'kasiyer yardimcisi':{'kasiyer yardimcisi':0,'kasiyer':1}}


def compat(a,b):
    a,b=canon(a),canon(b)
    return 0 if a==b else COMP.get(a,{}).get(b,99)



def transfer_pool(st,tt,staff):
    mid=req(staff,'MağazaID','MagazaID'); uid=req(staff,'UnvanID'); ent=col(staff,'İşe Giriş','Ise Giris'); rows=[]
    for _,s in st[st['Norm Fazlası']>0].iterrows():
        p=staff[staff[mid].map(txt)==txt(s['MağazaID'])].copy(); ex={txt(r['UnvanID']):int(r['Norm Fazlası']) for _,r in tt[(tt['MağazaID'].map(txt)==txt(s['MağazaID'])) & (tt['Norm Fazlası']>0)].iterrows()}
        p['_ex']=p[uid].map(lambda x:ex.get(txt(x),0)); p['_date']=pd.to_datetime(p[ent],errors='coerce') if ent else pd.Timestamp('1900-01-01')
        rows += p.sort_values(['_ex','_date'],ascending=[False,False]).head(int(s['Norm Fazlası'])).to_dict('records')
    return rows



def needs(tt):
    out=[]
    for _,r in tt[tt['Norm Eksiği']>0].iterrows():out += [r.to_dict()]*int(r['Norm Eksiği'])
    return out



def scenarios(st,tt,staff,sheets):
    pool=transfer_pool(st,tt,staff); need=needs(tt); am=address_map(sheets); pam=person_address_map(sheets)
    p_name=col(staff,'İsim Soyisim','Isim Soyisim','Ad Soyad'); p_id=col(staff,'PersonelID'); p_store=col(staff,'Mağaza','Magaza'); p_reg=col(staff,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge'); p_title=col(staff,'Unvan'); p_ent=col(staff,'İşe Giriş','Ise Giris')
    results={}
    for scen in ['Dengeli','Aynı Unvan','Aynı Bölge','Minimum Mesafe','Eve En Yakın']:
        if not pool or not need: results[scen]=pd.DataFrame(); continue
        C=np.full((len(pool),len(need)),1e9)
        meta={}
        for i,p in enumerate(pool):
            for j,t in enumerate(need):
                if txt(p.get(p_store))==txt(t['Mağaza']):continue
                cp=compat(p.get(p_title),t['Unvan'])
                if cp>=99:continue
                d=distance(p.get(p_store),t['Mağaza'],am); sr=canon(p.get(p_reg))==canon(t['Bölge Sorumlusu']); stitle=cp==0
                home,current_home,target_home,gain,target_minutes=_home_metrics(p,p.get(p_store),t['Mağaza'],am,pam,p_id,p_name)
                if canon(home.get('approval'))=='hayir':continue
                train=0 if cp==0 else (4 if cp==1 else 8); adapt=3 if sr else 7
                branch_score=max(0,min(100,100-d*2))
                home_score=50 if target_home is None else max(0,min(100,100-target_home*2.5))
                gain_score=50 if gain is None else max(0,min(100,50+gain*4))
                approval_score=100 if canon(home.get('approval'))=='evet' else 65
                title_score=max(0,100-cp*20); region_score=100 if sr else 70
                total_score=title_score*.30+branch_score*.20+home_score*.20+gain_score*.15+approval_score*.10+region_score*.05
                max_minutes=float(home.get('max_minutes') or 60)
                commute_penalty=250 if target_minutes is not None and target_minutes>max_minutes else 0
                score={'Dengeli':100-total_score+commute_penalty,'Aynı Unvan':(0 if stitle else 10000)+(100-total_score)+commute_penalty,'Aynı Bölge':(0 if sr else 10000)+(100-total_score)+commute_penalty,'Minimum Mesafe':d+cp*250+(0 if sr else 20)+commute_penalty,'Eve En Yakın':(target_home if target_home is not None else 9999)+cp*250+commute_penalty}[scen]
                C[i,j]=score; meta[i,j]=(d,train,adapt,sr,stitle,current_home,target_home,gain,target_minutes,branch_score,home_score,gain_score,total_score,home)
        ri,cj=linear_sum_assignment(C); rows=[]
        for i,j in zip(ri,cj):
            if C[i,j]>=1e8:continue
            p,t=pool[i],need[j]; d,tr,ad,sr,sti,current_home,target_home,gain,target_minutes,branch_score,home_score,gain_score,total_score,home=meta[i,j]
            rows.append({'Senaryo':scen,'PersonelID':txt(p.get(p_id)),'İsim Soyisim':txt(p.get(p_name)),'Kaynak Mağaza':txt(p.get(p_store)),'Kaynak Bölge':txt(p.get(p_reg)),'Mevcut Unvan':txt(p.get(p_title)),'Hedef Mağaza':txt(t['Mağaza']),'Hedef Bölge':txt(t['Bölge Sorumlusu']),'İhtiyaç Unvanı':txt(t['Unvan']),'Şubeler Arası Mesafe (km)':round(d,1),'Ev-Mevcut Şube (km)':None if current_home is None else round(current_home,1),'Ev-Hedef Şube (km)':None if target_home is None else round(target_home,1),'Yol Kazancı (km)':None if gain is None else round(gain,1),'Tahmini Yeni Yol (dk)':None if target_minutes is None else round(target_minutes),'Şubeye Yakınlık Puanı':round(branch_score,1),'Eve Yakınlık Puanı':round(home_score,1),'Personel Memnuniyeti Puanı':round(gain_score,1),'Transfer Uygunluk Puanı':round(total_score,1),'Transfer Onayı':txt(home.get('approval')),'Adres Veri Durumu':txt(home.get('status')),'Eğitim İhtiyacı (saat)':tr,'Adaptasyon (gün)':ad,'İşe Giriş':p.get(p_ent) if p_ent else None,'Transfer Gerekçesi':('Aynı unvan; ' if sti else 'Uyumlu unvan; ')+('aynı bölge; ' if sr else 'farklı bölge; ')+f'şubeler arası {d:.1f} km; '+(('ev yolunda %.1f km iyileşme'%gain) if gain is not None and gain>0 else 'ev yolu iyileşmesi yok'),'Optimizasyon Puanı':round(total_score,1)})
        results[scen]=pd.DataFrame(rows)
    return results



def risk_table(st):
    x=st.copy(); x['Risk Puanı']=(x['Norm Eksiği']*12 + (x['Norm Eksiği']>0)*15).clip(upper=100); x['Risk Seviyesi']=pd.cut(x['Risk Puanı'],[-1,39,59,79,100],labels=['Düşük','Orta','Yüksek','Kritik']); return x.sort_values('Risk Puanı',ascending=False)


# ============================================================================
# P2 MODÜLERLEŞTİRME — engine_core.py 2189 satırdan bölündü (adım 3-5).
# Excel/AI-norm/PDF üretim fonksiyonları artık ayrı modüllerde; engine_core.py
# bunları AYNI İSİMLERLE geri içe aktarır, mevcut hiçbir çağrı noktası
# (main.py, web/app.py, tests/) değişmedi. İçe aktarma SIRASI önemlidir:
# excel_report ve pdf_report, engine_core'daki _title_key/_region_name/state/
# kpis/ai_features_enabled/executive_analysis_enabled isimlerini bu satırdan
# ÖNCE tanımlanmış olduklarını varsayarak (döngüsel-ama-güvenli import ile)
# geri okur.
# ============================================================================
from src.excel_report import (
    write_df, executive_excel, _store_roster_rows,
    _personnel_names_by_store_title, _title_report_with_names,
    _personnel_detail_report, _surplus_people_report, _gap_text,
    _region_excel, enhanced_excel_reports, _v16_enrich_explanations,
    _v16_scenario_impact, _v16_add_workbook_layers,
    _executive_analysis_frames, _add_executive_analysis_sheets,
    _add_visible_ai_dashboard, _build_admin_report_pack,
)
from src.ai_norm import (
    _transfer_coverage, _decision_reason, ai_norm_table, validate_ai_decisions,
)
from src.pdf_report import (
    font, _pdf_text, _pdf_plain_text, pdf_report, _pdf_styles, _footer,
    enhanced_pdf_reports, _chart_label, _tr_chart_value, _pdf_empty_chart,
    _pdf_bar_chart, _pdf_grouped_chart, _pdf_visual_story, _build_store_pdf,
)
