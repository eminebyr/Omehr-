from __future__ import annotations

"""
AI NORM ÖNERİ MOTORU (P2 — engine_core.py modülerleştirme, üçüncü adım)
=====================================================================
AI'nin mağaza/unvan bazında önerdiği normu, gerekçesini ve resmi norma göre
sapmasını üreten SAF karar-destek katmanı. engine_core.py'deki state/kpis
hesaplamasına bağımlı DEĞİLDİR — girdi olarak zaten hesaplanmış sheets/tt/
scens/kpi/st alır, hiçbir global duruma yazmaz.

KALİBRASYON NOTU (bkz. 00_OKU_CURRENT.txt): AI'nin önerdiği toplam normun
resmi normdan çok yüksek çıkmasının nedeni bu dosyadaki mantık değil,
Standart_Sure_Kutuphanesi'ndeki doğrulanmamış (sahada ölçülmemiş) süre
varsayımlarıdır. `validate_ai_decisions` bu sapmayı görünür kılar ve
büyük farklarda uyarı üretir; bkz. AI_NORM_KALIBRASYON.md.
"""

import math

import numpy as np
import pandas as pd

from services.runtime_paths import runtime_root
from src.text_utils import canon, col, numeric, txt, _title_key



def _transfer_coverage(scens):
    """Dengeli senaryodaki fiili hedef mağaza-unvan eşleşmelerini sayar."""
    d=scens.get('Dengeli',pd.DataFrame()) if isinstance(scens,dict) else pd.DataFrame()
    if d.empty:return {}
    needed=['Hedef Mağaza','İhtiyaç Unvanı']
    if any(c not in d.columns for c in needed):return {}
    g=d.groupby(needed,dropna=False).size()
    return {(canon(k[0]),canon(k[1])):int(v) for k,v in g.items()}



def _decision_reason(r):
    def safe_num(v,default=0.0):
        try:
            x=float(v)
            return default if not math.isfinite(x) else x
        except Exception:
            # NOT: Bilerek loglanmıyor — boş/metin hücrelerde (ör. henüz
            # doldurulmamış "Güven Skoru") bu dönüşüm normal koşullarda da
            # sık sık başarısız olur; her satırda log basmak asıl önemli
            # hataları loglarda gömer.
            return default
    mevcut=int(round(safe_num(r.get('Aktif Mevcut',0)))); yonetim=int(round(safe_num(r.get('Norm Kadro',0)))); ai_norm=int(round(safe_num(r.get('AI Önerilen Norm',0))))
    gap=ai_norm-mevcut; parts=[]
    fte=safe_num(r.get('İş Yükü FTE',0)); minimum=int(round(safe_num(r.get('Minimum Kadro',0)))); peak=safe_num(r.get('Pik Katsayısı',0))
    if fte>0: parts.append(f'İş yükü ihtiyacı {fte:.2f} FTE')
    if minimum>0: parts.append(f'minimum kadro {minimum}')
    if peak>1.001: parts.append(f'pik katsayısı {peak:.2f}')
    parts.append(f'yönetim normu {yonetim}')
    parts.append(f'güncel mevcut {mevcut}')
    parts.append(f'AI normu {ai_norm}')
    if gap>0:
        tr=int(r.get('Doğrulanmış Transfer',0)); hire=int(r.get('Doğrulanmış İşe Alım',0))
        if tr and hire: parts.append(f'açığın {tr} kişisi transfer, {hire} kişisi işe alımla kapatılabilir')
        elif tr: parts.append(f'{tr} kişilik açık transferle kapatılabilir')
        else: parts.append(f'{hire} kişilik işe alım ihtiyacı bulunuyor')
    elif gap<0: parts.append(f'{abs(gap)} kişi AI normuna göre transfer adayı')
    else: parts.append('mevcut ile AI normu eşit')
    return '; '.join(parts)+'.'



def ai_norm_table(sheets, tt, scens=None):
    """AI normunu güncel gerçek mevcut ve fiili transfer optimizasyonuyla doğrular."""
    generated=runtime_root()/'output'/'V19_AI_Norm_Sonuclari.xlsx'
    if generated.is_file():
        ai=pd.read_excel(generated,sheet_name='AI_Norm_Sonuclari')
    else:
        ai = sheets.get('AI_Norm_Sonuclari', pd.DataFrame()).copy()
    if ai.empty:
        x = tt[['MağazaID','Mağaza','Bölge Sorumlusu','UnvanID','Unvan','Norm Kadro','Aktif Mevcut']].copy()
        x['AI Önerilen Norm'] = x['Norm Kadro']; x['Güven Skoru'] = np.nan
        # DÜZELTME: 'AI-Mevcut Fark' burada eksikti — validate_ai_decisions()
        # bu sütunu KOŞULSUZ okuyor (bkz. ai_norm_table normal dalındaki
        # aynı formül, satır ~178). Eksik olması, AI motoru henüz hiç
        # çalıştırılmamış bir kurulumda (ör. main.py'nin İLK çalıştırılışı)
        # run_all()'ın KeyError ile çökmesine yol açıyordu.
        x['AI-Mevcut Fark'] = x['Norm Kadro'] - x['Aktif Mevcut']
        # DÜZELTME: 'Veri Durumu' de eksikti — ai_norm_executive_summary()
        # d.get('Veri Durumu','') ile okuyor; sütun hiç yoksa bu bir string
        # sabiti döner (Series değil), sonraki .sum() çağrısı
        # AttributeError ile patlıyordu. Aynı ifade normal (AI motoru
        # çalışmış) daldaki "kayıt yok" durumuyla aynı (satır ~166).
        x['Veri Durumu'] = 'AI kaydı yok (yalnız resmi norm referansı)'
        x['Doğrulanmış Transfer']=0; x['Doğrulanmış İşe Alım']=0
        x['Önerilen Aksiyon'] = 'AI motoru çalıştırılmalı; yönetim normu geçici referanstır'
        x['Aksiyon Gerekçesi'] = x.apply(_decision_reason,axis=1)
        return x

    ai.columns=[txt(c) for c in ai.columns]
    aliases={
        'MağazaID':['MağazaID','MagazaID'], 'Mağaza':['Mağaza','Magaza'],
        'Bölge Sorumlusu':['Bölge','Bölge Sorumlusu','Bolge'], 'UnvanID':['UnvanID'], 'Unvan':['Unvan'],
        'Norm Kadro':['Yönetim Normu','Norm Kadro'], 'Aktif Mevcut':['Aktif Mevcut'],
        'Toplam İş Yükü (Dk)':['Toplam İş Yükü (Dk)'], 'İş Yükü FTE':['İş Yükü FTE'],
        'Minimum Kadro':['Minimum Kadro'], 'Pik Katsayısı':['Pik Katsayısı'],
        'AI Önerilen Norm':['AI Önerilen Norm'], 'Güven Skoru':['Güven Skoru'],
        'Veri Durumu':['Veri Durumu'], 'Öncelik Seviyesi':['Öncelik Seviyesi'],
        'Kaynak Önerilen Aksiyon':['Önerilen Aksiyon'], 'Kaynak Yönetici Açıklaması':['Yönetici Açıklaması']}
    rename={}
    for target,names in aliases.items():
        c=col(ai,*names)
        if c:rename[c]=target
    ai=ai.rename(columns=rename)
    # Inputtaki AI_Norm_Sonuclari sayfasında bulunan tahmin, maliyet,
    # finansal etki ve açıklama alanlarını kaybetme. Standart alanları
    # normalize et, diğer bütün AI sütunlarını raporlamaya taşı.
    ai=ai.copy(); ai['_AI Kaydı Var']=1
    for c in ['Norm Kadro','Aktif Mevcut','Toplam İş Yükü (Dk)','İş Yükü FTE','Minimum Kadro','Pik Katsayısı','AI Önerilen Norm','Güven Skoru']:
        if c in ai: ai[c]=numeric(ai[c])

    # KALİBRASYON DÜZELTMESİ (bkz. AI_NORM_KALIBRASYON.md): burada eskiden
    # birleştirme anahtarı (MağazaID, UnvanID) idi. tt['UnvanID'] engine_core.
    # state() içinde HER SATIRDA KASITLI OLARAK BOŞ bırakılır (unvan-grup
    # bazında toplulaştırma yapılır, ham UnvanID'ye indirgenemez — bkz.
    # engine_core.py state() içindeki not). Bu yüzden eski anahtar HİÇBİR
    # satırda eşleşmiyordu: outer join, AI sonuçlarının TAMAMINI (749) resmi
    # normun TAMAMIYLA (603) yan yana ekliyordu → 'AI Önerilen Norm' toplamı
    # 749+603=1352 çıkıyordu (dokümante edilen ~1359 'uçurum' budur — gerçek
    # bir kalibrasyon sorunu değil, bir birleştirme anahtarı hatasıydı).
    # DOĞRU anahtar: (MağazaID, unvanın normalize edilmiş grup adı) —
    # _title_key() ile üretilir, tt ile AI xlsx'i arasında %90+ örtüşür.
    # AI xlsx tt'den DAHA İNCE granülerdir (ham UnvanID bazında); bu yüzden
    # merge'den ÖNCE aynı grup anahtarında toplulaştırılır.
    ai['_JoinKey']=ai['Unvan'].map(_title_key)
    # Veri Durumu, gruptaki EN KÖTÜ (en az güvenilir) değeri yansıtır — bir
    # grupta tek bir 'Dummy/saha etüdü gerekli' satır bile varsa, birleşik
    # satırın güvenilirliği o satırla sınırlıdır; iyimser bir 'first' seçimi
    # yöneticiyi yanıltır.
    _veri_durumu_oncelik={'Dummy/saha etüdü gerekli':0,'Karma veri':1,'Ağırlıklı gerçek veri':2}
    if 'Veri Durumu' in ai.columns:
        ai['_VeriDurumuSira']=ai['Veri Durumu'].map(_veri_durumu_oncelik).fillna(-1)
    else:
        ai['Veri Durumu']=''
        ai['_VeriDurumuSira']=-1
    _agg_map={'Unvan':'first','UnvanID':'first','Toplam İş Yükü (Dk)':'sum',
              'Minimum Kadro':'sum','AI Önerilen Norm':'sum',
              'İş Yükü FTE':'mean','Pik Katsayısı':'mean','Güven Skoru':'mean',
              '_AI Kaydı Var':'max','_VeriDurumuSira':'min'}
    ai_agg=(ai.groupby(['MağazaID','_JoinKey'],dropna=False)
            .agg(_agg_map).reset_index())
    _sira_veri_durumu={v:k for k,v in _veri_durumu_oncelik.items()}
    ai_agg['Veri Durumu']=ai_agg['_VeriDurumuSira'].map(_sira_veri_durumu).fillna('')
    ai_agg=ai_agg.drop(columns=['_VeriDurumuSira'])

    truth=tt[['MağazaID','Mağaza','Bölge Sorumlusu','UnvanID','Unvan','Aktif Mevcut','Norm Kadro']].copy()
    truth['MağazaID']=truth['MağazaID'].map(txt);truth['_JoinKey']=truth['Unvan'].map(_title_key)
    # Aynı ID'nin kaynak dosyada farklı yazım/metadata satırları bulunabilmesine karşı
    # karar anahtarını tekilleştir; personel ve norm adetlerini güvenli biçimde topla.
    truth=(truth.groupby(['MağazaID','_JoinKey'],dropna=False)
           .agg({'Mağaza':'first','Bölge Sorumlusu':'first','Unvan':'first','Aktif Mevcut':'sum','Norm Kadro':'sum'}).reset_index())
    truth=truth.rename(columns={'Mağaza':'_Gerçek Mağaza','Bölge Sorumlusu':'_Gerçek Bölge','Unvan':'_Gerçek Unvan','Aktif Mevcut':'_Gerçek Aktif Mevcut','Norm Kadro':'_Gerçek Yönetim Normu'})
    ai=ai_agg.merge(truth,on=['MağazaID','_JoinKey'],how='outer')
    ai['Mağaza']=ai.get('Mağaza',pd.Series(index=ai.index,dtype=object)).fillna(ai['_Gerçek Mağaza'])
    ai['Bölge Sorumlusu']=ai.get('Bölge Sorumlusu',pd.Series(index=ai.index,dtype=object)).fillna(ai['_Gerçek Bölge'])
    ai['Unvan']=ai.get('Unvan',pd.Series(index=ai.index,dtype=object)).fillna(ai['_Gerçek Unvan'])
    ai['Aktif Mevcut']=numeric(ai['_Gerçek Aktif Mevcut']).round().astype(int)
    ai['Norm Kadro']=numeric(ai['_Gerçek Yönetim Normu']).round().astype(int)
    if 'AI Önerilen Norm' not in ai: ai['AI Önerilen Norm']=np.nan
    ai['AI Önerilen Norm']=pd.to_numeric(ai['AI Önerilen Norm'],errors='coerce')
    ai.loc[ai['_AI Kaydı Var'].isna(),'AI Önerilen Norm']=ai.loc[ai['_AI Kaydı Var'].isna(),'Norm Kadro']
    ai['AI Önerilen Norm']=ai['AI Önerilen Norm'].fillna(ai['Norm Kadro']).round().astype(int).clip(lower=0)
    if 'Veri Durumu' not in ai: ai['Veri Durumu']=''
    ai.loc[ai['_AI Kaydı Var'].isna(),'Veri Durumu']='AI kaydı yok (yalnız resmi norm referansı)'
    ai['Veri Durumu']=ai['Veri Durumu'].fillna('')
    # GÜVENLİK TAVANI (P0 — "mevcut ile AI önerisi arasında uçurum olmamalı"):
    # ai_operations_engine.py normalde AI Önerilen Norm'u zaten yönetim
    # normuna göre ±%20 ile sınırlar; ancak bu tabloya resmi norm referansı
    # OLMAYAN (AI kaydı bulunmayan/eşleşmeyen) satırlar için ek bir son
    # güvenlik tavanı uygulanır — hiçbir satır, yönetim normunun 1.20
    # katından fazla veya (norm=0 iken) 1'den fazla ÖNERİLEMEZ. Bu, birleştirme
    # veya veri kalitesi sorunlarının (ör. yukarıdaki anahtar hatası gibi)
    # tekrar sessizce dev bir sapma üretmesini engeller.
    _norm_ceiling=np.ceil(ai['Norm Kadro'].clip(lower=0)*1.20).astype(int)
    _norm_ceiling=np.where(ai['Norm Kadro'].le(0),1,_norm_ceiling)
    ai['AI Önerilen Norm']=np.minimum(ai['AI Önerilen Norm'],_norm_ceiling).astype(int)

    if 'Güven Skoru' not in ai:ai['Güven Skoru']=np.nan
    ai['Güven Skoru']=pd.to_numeric(ai['Güven Skoru'],errors='coerce')
    for c in ['İş Yükü FTE','Minimum Kadro','Pik Katsayısı','Toplam İş Yükü (Dk)']:
        if c not in ai:ai[c]=0
    ai['AI-Mevcut Fark']=ai['AI Önerilen Norm']-ai['Aktif Mevcut']

    coverage=_transfer_coverage(scens or {})
    ai['Transfer Kapasitesi']=ai.apply(lambda r:coverage.get((canon(r['Mağaza']),canon(r['Unvan'])),0),axis=1)
    ai['Doğrulanmış Transfer']=ai.apply(lambda r:min(max(int(r['AI-Mevcut Fark']),0),int(r['Transfer Kapasitesi'])),axis=1)
    ai['Doğrulanmış İşe Alım']=(ai['AI-Mevcut Fark'].clip(lower=0)-ai['Doğrulanmış Transfer']).astype(int)

    def action(r):
        gap=int(r['AI-Mevcut Fark']); tr=int(r['Doğrulanmış Transfer']); hire=int(r['Doğrulanmış İşe Alım'])
        if gap==0:return 'Mevcut yapı korunmalı'
        if gap<0:return f'{abs(gap)} kişi norm fazlası; transfer adayı'
        if tr>0 and hire>0:return f'{tr} transfer + {hire} işe alım'
        if tr>0:return f'{tr} kişi transfer ile kapatılmalı'
        return f'{hire} kişi için doğrudan işe alım başlatılmalı'
    ai['Önerilen Aksiyon']=ai.apply(action,axis=1)
    ai['Aksiyon Gerekçesi']=ai.apply(_decision_reason,axis=1)
    return ai.drop(columns=['_Gerçek Mağaza','_Gerçek Bölge','_Gerçek Unvan','_Gerçek Aktif Mevcut','_Gerçek Yönetim Normu','_AI Kaydı Var'],errors='ignore')



def validate_ai_decisions(ai, kpi, st):
    rows=[]
    def add(level,code,store,title,detail):rows.append({'Seviye':level,'Kontrol Kodu':code,'Mağaza':store,'Unvan':title,'Detay':detail})
    # NOT: (MağazaID,UnvanID) artık gerçek birleştirme anahtarı DEĞİL —
    # ai_norm_table() (MağazaID,_JoinKey) ile toplulaştırır, UnvanID sadece
    # bilgi amaçlı 'ilk değer'dir ve birden çok grupta tekrar edebilir.
    dup_key = ['MağazaID','_JoinKey'] if '_JoinKey' in ai.columns else ['MağazaID','UnvanID']
    keys=ai.duplicated(dup_key,keep=False)
    for _,r in ai[keys].iterrows():add('KRİTİK','DUPLICATE_KEY',r['Mağaza'],r['Unvan'],'Aynı mağaza-unvan anahtarı birden fazla kez bulundu.')
    for _,r in ai.iterrows():
        gap=int(r['AI-Mevcut Fark']); act=txt(r['Önerilen Aksiyon']);tr=int(r['Doğrulanmış Transfer']);hire=int(r['Doğrulanmış İşe Alım'])
        if gap==0 and act!='Mevcut yapı korunmalı':add('KRİTİK','EQUAL_NORM_ACTION',r['Mağaza'],r['Unvan'],f'Mevcut=AI norm olmasına rağmen aksiyon: {act}')
        if tr+hire!=max(gap,0):add('KRİTİK','GAP_ALLOCATION',r['Mağaza'],r['Unvan'],f'Açık {max(gap,0)}, transfer+işe alım {tr+hire}.')
        if tr>max(gap,0):add('KRİTİK','TRANSFER_OVER_GAP',r['Mağaza'],r['Unvan'],f'Transfer {tr}, açık {max(gap,0)}.')
        conf=float(r.get('Güven Skoru',0) or 0)
        if conf<0 or conf>100:add('UYARI','CONFIDENCE_RANGE',r['Mağaza'],r['Unvan'],f'Güven skoru beklenen aralığın dışında: {conf}')
    if int(st['Aktif Mevcut'].sum())!=int(kpi['Aktif Mevcut']):add('KRİTİK','KPI_STAFF_TOTAL','','', 'Aktif mevcut KPI toplamı mağaza toplamlarıyla uyuşmuyor.')
    if int(st['Norm Kadro'].sum())!=int(kpi['Toplam Norm']):add('KRİTİK','KPI_NORM_TOTAL','','', 'Norm KPI toplamı mağaza toplamlarıyla uyuşmuyor.')
    current_minus_norm=int(kpi['Aktif Mevcut'])-int(kpi['Toplam Norm'])
    surplus_minus_deficit=int(kpi['Norm Fazlası'])-int(kpi['Norm Eksiği'])
    if current_minus_norm!=surplus_minus_deficit:
        add('BİLGİ','KPI_SCOPE_DIFFERENCE','','',
            f'Tüm aktif mevcut-Norm={current_minus_norm}; norm kapsamındaki Fazla-Eksik={surplus_minus_deficit}. '
            'Norm tanımı olmayan çalışanlar toplam aktif mevcuda dahildir, eksik/fazla hesabına dahil değildir.')
    # DÜZELTME: önceden bu kural yalnız TEK bir sabit örnekte (AYDIN
    # EFELER / BAKLİYAT — kullanıcının bir zamanlar yakaladığı gerçek
    # örnek) kontrol ediliyordu. Bu, aynı hata BAŞKA bir mağaza/unvanda
    # (veya başka bir kiracıda) oluşsa TAMAMEN GÖZDEN KAÇARDI — kural
    # yalnız o tek satırı kontrol ettiği için. Artık TÜM satırlarda
    # genel olarak kontrol edilir (AI önerilen norm ile mevcut eşitken
    # 'Mevcut yapı korunmalı' DIŞINDA bir aksiyon önerilmesi, hangi
    # mağaza/unvanda olursa olsun bir hatadır).
    if 'AI Önerilen Norm' in ai.columns:
        for _, r in ai.iterrows():
            if int(r['Aktif Mevcut']) == int(r['AI Önerilen Norm']) and txt(r['Önerilen Aksiyon']) != 'Mevcut yapı korunmalı':
                add('KRİTİK', 'EQUAL_AI_NORM_ACTION', r['Mağaza'], r['Unvan'],
                    'Aktif Mevcut = AI Önerilen Norm olmasına rağmen aksiyon önerildi.')
    df=pd.DataFrame(rows,columns=['Seviye','Kontrol Kodu','Mağaza','Unvan','Detay'])
    critical=int((df['Seviye']=='KRİTİK').sum()) if not df.empty else 0
    summary={'Durum':'BAŞARILI' if critical==0 else 'HATALI','Kritik Hata':critical,'Uyarı':int((df['Seviye']=='UYARI').sum()) if not df.empty else 0,'Kontrol Edilen Karar':int(len(ai))}
    return df,summary


def ai_norm_executive_summary(ai):
    """AI önerilen norm ile resmi yönetim normu arasındaki farkı yöneticiye
    ANLAŞILIR şekilde açıklar: hangi UNVAN, hangi MAĞAZA farkı en çok
    büyütüyor ve NEDEN (veri kalitesi/güven skoru ile birlikte).

    Sadece 'toplamda +%24 fark var' demek yeterli değildir — bir yöneticinin
    aksiyon alabilmesi için 'bu farkın X'i tek başına KASİYER unvanından,
    Y'si şu 5 mağazadan geliyor ve bu mağazalardaki veri kalitesi Z' bilgisi
    gerekir. Bu fonksiyon üç parça döndürür:
      - 'genel': tek satırlık toplam özet (resmi/AI/fark/fark yüzdesi)
      - 'unvan_bazli': her unvanın toplam farka katkısı, en büyükten küçüğe
      - 'magaza_bazli': her mağazanın toplam farka katkısı, en büyükten küçüğe
      - 'anlatim': yöneticiye okunacak 4-6 satırlık düz metin özet
    """
    d=ai.copy()
    for c in ['Aktif Mevcut','Norm Kadro','AI Önerilen Norm','Güven Skoru']:
        if c in d: d[c]=pd.to_numeric(d[c],errors='coerce').fillna(0)
    d['Fark']=d['AI Önerilen Norm']-d['Norm Kadro']
    # 'Mağaza' boş olan satırlar bug DEĞİL: AI motoru bu unvanı mağaza için bir
    # olasılık olarak değerlendirmiş, ama mağazada bu unvana ait HİÇBİR resmi
    # kayıt (norm=0, mevcut=0) yok — bu yüzden truth (tt) ile eşleşmiyor. Boş
    # göstermek yerine MağazaID ile etiketlenir, yönetici "nan" görmez.
    if 'Mağaza' in d.columns and 'MağazaID' in d.columns:
        d['Mağaza']=d['Mağaza'].fillna('Tanımsız kayıt (' + d['MağazaID'].astype(str) + ')')
    # Unvan grubu için HAM METİN yerine kanonik _JoinKey kullanılır — aksi
    # halde aynı unvanın farklı yazım/kaynak varyantları (ör. ai xlsx'ten
    # gelen 'first' seçim farkı) yanlışlıkla ayrı satırlara bölünüp toplamı
    # şişirebilir veya küçültebilir.
    grup_anahtari='_JoinKey' if '_JoinKey' in d.columns else 'Unvan'

    resmi_toplam=int(d['Norm Kadro'].sum()); ai_toplam=int(d['AI Önerilen Norm'].sum())
    fark_toplam=ai_toplam-resmi_toplam
    fark_yuzde=round((ai_toplam/resmi_toplam-1)*100,1) if resmi_toplam else 0.0
    genel=pd.DataFrame([{
        'Resmi Toplam Norm':resmi_toplam,'AI Önerilen Toplam Norm':ai_toplam,
        'Fark (Kişi)':fark_toplam,'Fark (%)':fark_yuzde,
        'Toplam Kayıt':int(len(d)),
        'Dummy/Saha Etüdü Bekleyen Kayıt':int((d.get('Veri Durumu','')=='Dummy/saha etüdü gerekli').sum()),
        'Resmi Kaydı Olmayan (0/0) Kayıt':int(((d['Norm Kadro']==0)&(d['Aktif Mevcut']==0)).sum()),
    }])

    def _veri_durumu_ozeti(g):
        if 'Veri Durumu' not in g: return ''
        sayim=g['Veri Durumu'].value_counts()
        return '; '.join(f'{k}: {v}' for k,v in sayim.items())

    unvan=(d.groupby(grup_anahtari,dropna=False)
           .apply(lambda g: pd.Series({
               'Unvan':txt(g['Unvan'].iloc[0]) if 'Unvan' in g and len(g) else '',
               'Mağaza Sayısı':int(g['Mağaza'].nunique()) if 'Mağaza' in g else int(len(g)),
               'Aktif Mevcut':int(g['Aktif Mevcut'].sum()),
               'Resmi Norm':int(g['Norm Kadro'].sum()),
               'AI Önerilen Norm':int(g['AI Önerilen Norm'].sum()),
               'Fark (Kişi)':int(g['Fark'].sum()),
               'Ortalama Güven Skoru':round(float(g['Güven Skoru'].mean()),1) if g['Güven Skoru'].notna().any() else None,
               'Veri Durumu Dağılımı':_veri_durumu_ozeti(g),
           }), include_groups=False)
           .reset_index(drop=True)
           .sort_values('Fark (Kişi)',ascending=False))
    unvan['Fark (%)']=unvan.apply(lambda r: round((r['AI Önerilen Norm']/r['Resmi Norm']-1)*100,1) if r['Resmi Norm'] else None, axis=1)

    magaza=(d.groupby('Mağaza',dropna=False)
            .apply(lambda g: pd.Series({
                'Bölge Sorumlusu':txt(g['Bölge Sorumlusu'].iloc[0]) if 'Bölge Sorumlusu' in g and len(g) else '',
                'Aktif Mevcut':int(g['Aktif Mevcut'].sum()),
                'Resmi Norm':int(g['Norm Kadro'].sum()),
                'AI Önerilen Norm':int(g['AI Önerilen Norm'].sum()),
                'Fark (Kişi)':int(g['Fark'].sum()),
                'Ortalama Güven Skoru':round(float(g['Güven Skoru'].mean()),1) if g['Güven Skoru'].notna().any() else None,
                'En Çok Fark Yaratan Unvan':(g.loc[g['Fark'].idxmax(),'Unvan'] if g['Fark'].gt(0).any() else ''),
            }), include_groups=False)
            .reset_index()
            .sort_values('Fark (Kişi)',ascending=False))
    magaza['Fark (%)']=magaza.apply(lambda r: round((r['AI Önerilen Norm']/r['Resmi Norm']-1)*100,1) if r['Resmi Norm'] else None, axis=1)

    top_unvan=unvan[unvan['Fark (Kişi)']>0].head(3)
    top_magaza=magaza[magaza['Fark (Kişi)']>0].head(5)
    satirlar=[]
    satirlar.append(
        f"AI'nin önerdiği toplam norm ({ai_toplam}), resmi yönetim normundan ({resmi_toplam}) "
        f"{fark_toplam} kişi (%{fark_yuzde}) daha yüksek."
    )
    if not top_unvan.empty:
        parcalar=', '.join(f"{r['Unvan']} (+{int(r['Fark (Kişi)'])})" for _,r in top_unvan.iterrows())
        satirlar.append(f"Farkın en büyük kısmı şu unvanlardan geliyor: {parcalar}.")
    if not top_magaza.empty:
        parcalar=', '.join(f"{r['Mağaza']} (+{int(r['Fark (Kişi)'])})" for _,r in top_magaza.iterrows())
        satirlar.append(f"Mağaza bazında en çok fark üreten yerler: {parcalar}.")
    dummy_oran=genel['Dummy/Saha Etüdü Bekleyen Kayıt'].iloc[0]/max(1,len(d))
    if dummy_oran>0.5:
        satirlar.append(
            f"Kayıtların %{round(dummy_oran*100)}'i hâlâ 'saha etüdü bekliyor' (Standart_Sure_Kutuphanesi'nde "
            "doğrulanmamış varsayım süre) durumunda — bu, yukarıdaki farkın büyük kısmının GERÇEK bir kadro "
            "ihtiyacından çok, ölçülmemiş süre varsayımlarından kaynaklanabileceği anlamına gelir."
        )
    satirlar.append(
        "AI önerisi karar DESTEĞİDİR, resmi normu otomatik değiştirmez. Bu tablo, hangi unvan/mağazada saha "
        "zaman etüdünün önce yapılması gerektiğine öncelik vermek için kullanılmalıdır."
    )
    anlatim='\n'.join(satirlar)

    return {'genel':genel,'unvan_bazli':unvan,'magaza_bazli':magaza,'anlatim':anlatim}

