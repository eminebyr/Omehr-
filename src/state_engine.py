from __future__ import annotations

"""
DURUM/İŞ YÜKÜ HESAPLAMA KATMANI (P2 — engine_core.py modülerleştirme,
sekizinci adım)
=====================================================================
Mağaza+unvan bazında mevcut/norm/eksik/fazla durumunu (state()) ve destek
tablolarını (kontrol, kapsam-dışı, kapsam temeli) üretir. text_utils'teki
saf yardımcılar dışında hiçbir dış duruma bağımlı değildir — girdi olarak
zaten okunmuş norm/staff/sheets DataFrame'lerini alır.
"""

import json

import pandas as pd

from services.runtime_paths import runtime_root
from src.text_utils import canon, col, numeric, req, txt, _title_key, _region_name, _store_key

def _norm_kadro_kontrol_path():
    return runtime_root() / 'reference' / 'GUNCEL_NORM_KADRO_KONTROL.xlsx'

_CONTROL_TABLES_CACHE: dict = {}


def _control_tables():
    """Kullanıcının 24.07.2026 kontrol tablosunu resmi rapor kontrolü olarak bir kez okur.

    DÜZELTME (kritik test-izolasyon + çok kiracılı risk): önceden hem
    dosya yolu (ROOT) hem de SONUÇ, modül import anında/ilk çağrıda
    SABİTLENİYORDU — OMEHR_RUNTIME_ROOT sonradan değişse (ör. farklı
    kiracı/test) bile HEP İLK çağrının sonucu dönerdi. Artık çözümlenmiş
    yola göre anahtarlanan bir sözlükte önbelleklenir."""
    cp = _norm_kadro_kontrol_path()
    key = str(cp)
    if key in _CONTROL_TABLES_CACHE:
        return _CONTROL_TABLES_CACHE[key]
    if not cp.exists():
        return None
    try:
        _CONTROL_TABLES_CACHE[key] = (pd.read_excel(cp, sheet_name='NORM KADRO'), pd.read_excel(cp, sheet_name='FAZLA'), pd.read_excel(cp, sheet_name='EKSİK'))
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed(f"kontrol tabloları '{cp}' okunamadı", _exc)
        return None
    return _CONTROL_TABLES_CACHE[key]



def _control_long(df, store_col, kind):
    column_map={
        'YÖNETİCİ':'YÖNETİCİ','YÖNETİCİ Y.':'YÖNETİCİ YARDIMCISI','YÖNETİCİ YARDIMCISI':'YÖNETİCİ YARDIMCISI',
        'KASİYER':'KASİYER','REYON':'REYON GÖREVLİSİ','REYON GÖREVLİSİ':'REYON GÖREVLİSİ',
        'BAKLİYAT':'BAKLİYAT','ŞARKÜTERİ':'ŞARKÜTERİ','ŞARKÜTERİ Y.':'ŞARKÜTERİ YARDIMCISI',
        'ŞARKÜTERİ YARDIMCISI':'ŞARKÜTERİ YARDIMCISI','KASAP':'KASAP','KASAP Y.':'KASAP YARDIMCISI',
        'KASAP YARDIMCISI':'KASAP YARDIMCISI','MANAV':'MANAV','MANAV YARD.':'MANAV YARDIMCISI',
        'MANAV YARDIMCISI':'MANAV YARDIMCISI','MANAV TERAZİ':'MANAV TERAZİ','PART TİME':'PART TİME',
        'PARTTİME':'PART TİME','ONLİNE ŞOFÖR':'ONLİNE ŞOFÖR','ONLİNE TOPLAYICI':'ONLİNE TOPLAYICI',
        'UNLU MAMÜLLER':'UNLU MAMÜLLER'}
    rows=[]
    for _,r in df.iterrows():
        store=txt(r.get(store_col)).strip()
        if not store or canon(store)=='toplam': continue
        for source,title in column_map.items():
            if source not in df.columns: continue
            value=float(numeric(pd.Series([r.get(source)])).iloc[0])
            if value:
                rows.append({'Mağaza':store,'Mağaza Anahtarı':_store_key(store),'Unvan':title,
                             'Unvan Anahtarı':_title_key(title),kind:int(value)})
    return pd.DataFrame(rows)

_GAP_TABLE_CACHE=None


def _gap_tables():
    """EKSİK/FAZLA tablolarını mağaza + departman anahtarında dinamik okur."""
    global _GAP_TABLE_CACHE
    if _GAP_TABLE_CACHE is not None:
        return _GAP_TABLE_CACHE.copy()
    ctl=_control_tables()
    if ctl is None:
        raise ValueError('EKSİK/FAZLA kontrol tabloları bulunamadı.')
    _,fctl,ectl=ctl
    fazla=_control_long(fctl,'FAZLA','Norm Fazlası')
    eksik=_control_long(ectl,'EKSİK','Norm Eksiği')
    keys=['Mağaza Anahtarı','Unvan Anahtarı']
    gap=pd.merge(fazla,eksik,on=keys,how='outer',suffixes=('_fazla','_eksik'))
    gap['Norm Fazlası']=numeric(gap.get('Norm Fazlası',pd.Series(index=gap.index,dtype=float))).astype(int)
    gap['Norm Eksiği']=numeric(gap.get('Norm Eksiği',pd.Series(index=gap.index,dtype=float))).astype(int)
    _GAP_TABLE_CACHE=gap[keys+['Norm Eksiği','Norm Fazlası']].copy()
    return _GAP_TABLE_CACHE.copy()

_SCOPE_BASELINE_CACHE: dict = {}


def _scope_baseline():
    """Referans tarihteki norm kapsamı ve etkin mevcut başlangıç değerleri.

    DÜZELTME (kritik test-izolasyon + çok kiracılı risk): AYNI kök
    nedenin en önemli örneği — bu fonksiyon state()'in TEMEL bir
    bağımlılığı, ve önceden ROOT + SONUÇ İKİSİ DE ilk çağrıda
    sabitleniyordu. Bizzat kanıtlandı: farklı bir OMEHR_RUNTIME_ROOT
    ile çalışan bir sonraki test/kiracı, YANLIŞLIKLA İLK çağrının
    NORM_KAPSAM_BAZI.json içeriğini almaya devam ediyordu."""
    path = runtime_root() / 'reference' / 'NORM_KAPSAM_BAZI.json'
    key = str(path)
    if key in _SCOPE_BASELINE_CACHE:
        return _SCOPE_BASELINE_CACHE[key].copy()
    if not path.is_file():
        raise ValueError('Norm kapsam başlangıç dosyası bulunamadı: NORM_KAPSAM_BAZI.json')
    payload=json.loads(path.read_text(encoding='utf-8'))
    base=pd.DataFrame(payload.get('rows',[]))
    required={'StoreKey','RoleKey','BaselineRaw','BaselineEffective','InScope'}
    if base.empty or not required.issubset(base.columns):
        raise ValueError('Norm kapsam başlangıç dosyasının şeması geçersiz.')
    base=base.rename(columns={'StoreKey':'_Mağaza','RoleKey':'_Unvan'})
    base['_Mağaza']=base['_Mağaza'].map(_store_key)
    compact_roles={
        'yonetici':'yonetici','yoneticiyardimcisi':'yonetici yardimcisi',
        'kasiyer':'kasiyer','reyongorevlisi':'reyon gorevlisi',
        'bakliyat':'bakliyat','sarkuteri':'sarkuteri',
        'sarkuteriyardimcisi':'sarkuteri yardimcisi','kasap':'kasap',
        'kasapyardimcisi':'kasap yardimcisi','manav':'manav',
        'manavyardimcisi':'manav yardimcisi','manavterazi':'manav terazi',
        'parttime':'part time','onlinesofor':'online sofor',
        'onlinetoplayici':'online toplayici','unlumamuller':'unlu mamuller',
    }
    base['_Unvan']=base['_Unvan'].map(lambda value:compact_roles.get(_store_key(value),_title_key(value)))
    base['BaselineRaw']=numeric(base['BaselineRaw']).astype(int)
    base['BaselineEffective']=numeric(base['BaselineEffective']).astype(int)
    base['InScope']=base['InScope'].fillna(False).astype(bool)
    base['_HasBaseline']=True
    _SCOPE_BASELINE_CACHE[key]=base
    return base.copy()



def _staff_norm_family(real_title, department):
    """Config tabanlı norm ailesi eşleştirmesi.

    Normal modda Departman ana veri kaynağıdır; config_norm_rules.json içindeki
    Uzman/Elit eş adları ana aileye bağlanır. raw_title_mode_enabled=true ise
    aile birleştirme kapatılır ve gerçek unvan doğrudan hesap anahtarı olur.
    """
    from services.norm_rule_config import load_norm_rules
    try:
        from src.feature_flags import feature_enabled
        raw_mode = feature_enabled('raw_title_mode_enabled', False)
    except Exception:
        raw_mode = False
    real = _title_key(real_title)
    dep = _title_key(department)
    if raw_mode:
        return real or dep
    rules = load_norm_rules()
    aliases = rules.get('family_aliases') or {}
    alias_map = {}
    for family, names in aliases.items():
        family_key = _title_key(family)
        alias_map[family_key] = family_key
        for name in names or []:
            alias_map[_title_key(name)] = family_key
    separate = {_title_key(v) for v in (rules.get('separate_roles') or [])}
    if real in separate:
        return real
    if real in alias_map:
        return alias_map[real]
    # Diğer tüm görevlerde Departman norm ailesidir; boşsa gerçek unvan kullanılır.
    return dep or real


def _apply_assistant_balance(title):
    """Manav/Kasap/Şarküteri ana norm açığını uygun yardımcı kapasitesiyle dengeler.

    Yardımcı önce kendi normunu karşılar. Yalnız kendi normunun üzerindeki
    yardımcı kapasitesi ana ailenin açığını kapatabilir. Ana aile personeli
    yardımcı normunu kapatmaz.
    """
    out = title.copy()
    if '_Yardımcı Denge' not in out.columns:
        out['_Yardımcı Denge'] = 0
    else:
        out['_Yardımcı Denge'] = numeric(out['_Yardımcı Denge']).fillna(0).astype(int)
    from services.norm_rule_config import load_norm_rules
    _balance = load_norm_rules().get('assistant_balance') or {}
    if not bool(_balance.get('enabled', True)):
        return out
    pairs = [(_title_key(k), _title_key(v)) for k,v in (_balance.get('pairs') or {}).items()]
    min_main = int(_balance.get('minimum_main_current', 1) or 1)
    for store_key in out['_Mağaza'].dropna().unique():
        store_mask = out['_Mağaza'].eq(store_key)
        for main_key, assistant_key in pairs:
            main_idx = out.index[store_mask & out['_Unvan'].eq(main_key)].tolist()
            assistant_idx = out.index[store_mask & out['_Unvan'].eq(assistant_key)].tolist()
            if not main_idx or not assistant_idx:
                continue
            mi, ai = main_idx[0], assistant_idx[0]
            main_norm = int(out.at[mi, 'Norm Kadro'])
            main_current = int(out.at[mi, 'Aktif Mevcut'])
            assistant_norm = int(out.at[ai, 'Norm Kadro'])
            assistant_current = int(out.at[ai, 'Aktif Mevcut'])
            main_gap = max(0, main_norm - main_current)
            assistant_capacity = max(0, assistant_current - assistant_norm)
            # Denge yalnız ana ailede en az 1 kişi varken uygulanır.
            # 0 ana personel + yardımcılar, ana normu tek başına kapatamaz.
            support = min(main_gap, assistant_capacity) if main_current >= min_main else 0
            if support <= 0:
                continue
            out.at[mi, 'Norm Eksiği'] = max(0, int(out.at[mi, 'Norm Eksiği']) - support)
            out.at[ai, 'Norm Fazlası'] = max(0, int(out.at[ai, 'Norm Fazlası']) - support)
            out.at[mi, '_Yardımcı Denge'] = int(out.at[mi, '_Yardımcı Denge']) + support
    out['_Yardımcı Denge'] = numeric(out['_Yardımcı Denge']).fillna(0).astype(int)
    return out


def _reconcile_main_family_rules(title):
    """Ana ve yardımcı unvan arasındaki dağılım farkını mağaza bazında dengeler.

    Aynı ailede bir satır eksik, eş satır fazla ise karşılıklı mahsup edilir.
    Böylece 1 Yönetici + 1 Yönetici Yardımcısı normuna karşı 2 Yönetici
    Yardımcısı bulunan mağazada yapay 1 eksik ve 1 fazla raporlanmaz.

    KARAR (kullanıcı ile netleştirildi — bkz. TUM_SUBELER_AILE_DENGE_
    DUZELTME_NOTU.md, "Kural A"): burası KPI/norm dengeleme katmanıdır ve
    soruyu "aynı aile içindeki fiili kapasite normu karşılıyor mu?" olarak
    yanıtlar — "bu kişinin unvanını değiştirelim" demez. Bu yüzden ana
    unvanda HİÇ (veya minimum_main_current'ın altında) gerçek kişi olsa
    bile, aile toplam kapasitesi aile toplam normunu karşılıyorsa
    Eksik/Fazla dengelenir (Eksik=0, Fazla=0) — bu KASITLIDIR. Amaç,
    yapay 1 eksik + 1 fazla ile toplam rakamların ve transfer motorunun
    şişmesini ÖNLEMEKTİR.

    Kaybedilmemesi gereken bilgi (ana unvanda gerçek kimse yok) KPI
    sayısını BOZMADAN, ayrı bir niteliksel bayrak olarak korunur:
    '_Ana Unvan Personelsiz' sütunu — bkz. aşağıda. Web/rapor katmanları
    bunu bir UYARI olarak gösterebilir, KPI hesabına DAHİL ETMEZ.
    """
    out = title.copy()
    from services.norm_rule_config import load_norm_rules
    balance = load_norm_rules().get('assistant_balance') or {}
    if not bool(balance.get('enabled', True)):
        return out
    pairs = [(_title_key(k), _title_key(v)) for k, v in (balance.get('pairs') or {}).items()]
    min_main = int(balance.get('minimum_main_current', 1) or 1)
    out['_Aile Denge'] = 0
    if '_Ana Unvan Personelsiz' not in out.columns:
        out['_Ana Unvan Personelsiz'] = False
    for store_key in out['_Mağaza'].dropna().unique():
        store_mask = out['_Mağaza'].eq(store_key)
        for main_key, assistant_key in pairs:
            idxs = out.index[store_mask & out['_Unvan'].isin([main_key, assistant_key])].tolist()
            if not idxs:
                continue
            main_idx = out.index[store_mask & out['_Unvan'].eq(main_key)].tolist()
            main_current = int(out.at[main_idx[0], 'Aktif Mevcut']) if main_idx else 0
            gross_gap = sum(max(0, int(out.at[i, 'Norm Eksiği'])) for i in idxs)
            gross_surplus = sum(max(0, int(out.at[i, 'Norm Fazlası'])) for i in idxs)
            balance_count = min(gross_gap, gross_surplus)
            if balance_count <= 0:
                continue
            # NİTELİKSEL UYARI (KPI'yi etkilemez): ana unvanda gerçek kişi
            # sayısı tabanın altındaysa, aile dengesi yine de uygulanır
            # (Kural A) ama bu satır(lar) için ayrı bir bayrak bırakılır —
            # "mağazada bu rolde doğrudan görevli personel yok" bilgisi
            # KPI sayısı sıfırlanınca kaybolmasın diye.
            if main_current < min_main and main_idx:
                out.at[main_idx[0], '_Ana Unvan Personelsiz'] = True
            remaining = balance_count
            for i in idxs:
                if remaining <= 0:
                    break
                value = max(0, int(out.at[i, 'Norm Eksiği']))
                take = min(value, remaining)
                out.at[i, 'Norm Eksiği'] = value - take
                remaining -= take
            remaining = balance_count
            for i in idxs:
                if remaining <= 0:
                    break
                value = max(0, int(out.at[i, 'Norm Fazlası']))
                take = min(value, remaining)
                out.at[i, 'Norm Fazlası'] = value - take
                remaining -= take
            for i in idxs:
                out.at[i, '_Aile Denge'] = balance_count
    return out


def state(norm,staff,sheets):
    norm=norm.copy(); staff=staff.copy()
    nmid=req(norm,'MağazaID','MagazaID'); nm=req(norm,'Mağaza','Magaza'); nb=req(norm,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge'); nn=req(norm,'Norm Kadro','Toplam Norm','Norm')
    smid=req(staff,'MağazaID','MagazaID'); sm=req(staff,'Mağaza','Magaza'); sb=req(staff,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge')
    pname=req(staff,'İsim Soyisim','Isim Soyisim','Ad Soyad')
    dep=req(staff,'Departman')
    nu=req(norm,'Unvan')
    norm[nn]=numeric(norm[nn])
    # Bölge sorumlusu adı standart olarak ALİ ÇELİK şeklinde kullanılır.
    norm['_Bölge']=norm[nb].map(_region_name); staff['_Bölge']=staff[sb].map(_region_name)
    norm['_Mağaza']=norm[nm].map(_store_key); staff['_Mağaza']=staff[sm].map(_store_key)
    norm['_Unvan']=norm[nu].map(_title_key)
    _real_title_col=col(staff,'Unvan')
    _real_titles=staff[_real_title_col] if _real_title_col else staff[dep]
    staff['_Unvan']=[_staff_norm_family(u,d) for u,d in zip(_real_titles,staff[dep])]

    # MağazaID bazı satırlarda tekrar kullanıldığı için norm eşleştirmesi mağaza adı + departmanla yapılır.
    ng=norm.groupby(['_Mağaza','_Unvan'],dropna=False)[nn].sum().reset_index(name='Norm Kadro')
    mg=staff.groupby(['_Mağaza','_Unvan'],dropna=False)[pname].count().reset_index(name='Aktif Mevcut')
    title=pd.merge(ng,mg,on=['_Mağaza','_Unvan'],how='outer').fillna({'Norm Kadro':0,'Aktif Mevcut':0})

    # NORM AİLESİ KURALI
    # -------------------
    # Fact_Mevcut.Unvan personelin GERÇEK unvanıdır (ELİT/UZMAN vb.).
    # Fact_Mevcut.Departman ise norm ailesidir ve hesapta TEK esas alandır.
    # Bu nedenle ELİT YÖNETİCİ / UZMAN YÖNETİCİ / YÖNETİCİ gerçek unvanları,
    # Departman=YÖNETİCİ ise aynı yönetici normunu karşılar. Aynı kural
    # ŞARKÜTERİ, KASAP ve MANAV ana aileleri için geçerlidir.
    #
    # Yardımcı unvanlar (YÖNETİCİ YARDIMCISI, ŞARKÜTERİ YARDIMCISI,
    # KASAP YARDIMCISI, MANAV YARDIMCISI) AYRI norm satırlarıdır; ana
    # ailedeki personel yardımcı normunu, yardımcı personel ana normu kapatmaz.
    title['Norm Kadro']=numeric(title['Norm Kadro']).astype(int)
    title['Aktif Mevcut']=numeric(title['Aktif Mevcut']).astype(int)

    # Norm kapsamı, şirket genelinde Fact_Norm'da tanımlı departman aileleridir.
    # Normu o mağazada 0 olan fakat aynı norm ailesinde mevcut personel varsa
    # bu kişi norm fazlası olabilir. Norm dışı görevler (ör. merkez özel rolleri)
    # eksik/fazla hesabına alınmaz.
    kapsam_unvanlari=set(ng['_Unvan'].dropna().tolist())
    # DÜZELTME: yardımcı (YARDIMCISI) unvanların çoğu zaman KENDİ Fact_Norm
    # satırı hiç yoktur — bu tasarım gereğidir (norm ana unvanda tanımlanır,
    # yardımcı yalnız destek sağlar). Önceden bu durumda yardımcı unvan
    # "kapsam dışı" sayılıp Norm Fazlası'sı DAİMA 0'a zorlanıyordu; bu da
    # _reconcile_main_family_rules()'ın ihtiyaç duyduğu "fazla kapasiteyi"
    # sıfırlayıp 1 ana+1 yardımcı senaryosunda ana unvanda yapay bir eksik
    # raporlanmasına yol açıyordu (gerçek veride İZMİRSPOR/ŞARKÜTERİ ve
    # ÖZDERE/MANAV'da tespit edildi). Yardımcı unvanlar da artık kapsama
    # dahil edilir.
    from services.norm_rule_config import load_norm_rules as _load_norm_rules_for_scope
    _assistant_pairs = (_load_norm_rules_for_scope().get('assistant_balance') or {}).get('pairs') or {}
    kapsam_unvanlari |= {_title_key(v) for v in _assistant_pairs.values()}
    in_scope=title['_Unvan'].isin(kapsam_unvanlari)
    effective=title['Aktif Mevcut'].where(in_scope,0)
    title['_Norm Kapsam Mevcut']=effective
    title['Norm Eksiği']=(title['Norm Kadro']-effective).where(in_scope,0).clip(lower=0).astype(int)

    # Resmî norm dağılımı input içindeki REFERENTIAL_CONTROL sayfasından okunur.
    # Bu değerler kodda sabit değildir; kullanıcı inputu değiştirildiğinde aynı
    # sayfadaki mağaza+norm ailesi dağılımı esas alınır. Tüm norm aileleri
    # (UNLU MAMÜLLER, PART TİME, ONLINE vb. dahil) işlenir.
    title['Norm Fazlası']=(effective-title['Norm Kadro']).where(in_scope,0).clip(lower=0).astype(int)
    # DÜZELTME (KRİTİK — bizzat canlıda bulundu, 20.08.2026): bu blok
    # REFERENTIAL_CONTROL sayfası varsa yukarıda TAZE hesaplanan Norm
    # Eksiği/Norm Fazlası'nı SESSİZCE eziyordu — sayfada karşılığı olmayan
    # her (mağaza,unvan) için 0'a düşürüyordu. Sonuç: personel eklense/
    # çıkarılsa bile (Aktif Mevcut doğru güncellense bile) Norm Eksiği/
    # Fazlası hiç değişmiyormuş gibi görünüyordu — canlı ortamda Akevler/
    # Kasiyer ve Akevler/Yönetici örnekleriyle defalarca doğrulandı (kişi
    # çıkarıldı, Eksik hiç oynamadı). Artık bu "resmi/sabit dağılım" ezmesi
    # varsayılan olarak KAPALI; yalnız OMEHR_USE_REFERENTIAL_CONTROL=1
    # açıkça ayarlanırsa devreye girer (bilinçli bir kalibrasyon/onay
    # süreci isteniyorsa).
    import os as _os_ref_ctl
    ctl=sheets.get('REFERENTIAL_CONTROL') if isinstance(sheets,dict) and _os_ref_ctl.getenv('OMEHR_USE_REFERENTIAL_CONTROL','0')=='1' else None
    if ctl is not None and not ctl.empty:
        try:
            c=ctl.copy()
            c_mid=req(c,'MağazaID','MagazaID')
            c_uid=req(c,'UnvanID')
            c_e=req(c,'Norm Eksiği Kontrol','Norm Eksigi Kontrol')
            c_f=req(c,'Norm Fazlası Kontrol','Norm Fazlasi Kontrol')
            dim_u=sheets.get('Dim_Unvan',pd.DataFrame()) if isinstance(sheets,dict) else pd.DataFrame()
            if not dim_u.empty and {'UnvanID','Unvan'}.issubset(dim_u.columns):
                uid_to_name={txt(r['UnvanID']):_title_key(r['Unvan']) for _,r in dim_u.iterrows()}
            else:
                uid_to_name={txt(r.get('UnvanID')):_title_key(r.get(nu)) for _,r in norm.iterrows()}
            c['_MağazaID']=c[c_mid].map(txt)
            c['_Unvan']=c[c_uid].map(lambda x: uid_to_name.get(txt(x), _title_key(txt(x))))
            c['_Eksik']=numeric(c[c_e]).astype(int)
            c['_Fazla']=numeric(c[c_f]).astype(int)
            cmap_e=c.groupby(['_MağazaID','_Unvan'])['_Eksik'].sum()
            cmap_f=c.groupby(['_MağazaID','_Unvan'])['_Fazla'].sum()
            title['_MağazaID']=title['_Mağaza'].map(lambda sk: txt(store_meta.loc[store_meta['_Mağaza'].eq(sk),'MağazaID'].iloc[-1]) if not store_meta.loc[store_meta['_Mağaza'].eq(sk)].empty else '') if 'store_meta' in locals() else ''
        except Exception:
            cmap_e=cmap_f=None
        if cmap_e is not None:
            # MağazaID norm/staff kaynaklarından güvenilir biçimde alınır.
            id_by_store={}
            for _,r in norm.iterrows(): id_by_store[_store_key(r[nm])]=txt(r[nmid])
            for _,r in staff.iterrows(): id_by_store[_store_key(r[sm])]=txt(r[smid])
            # Kontrol dağılımında olup o anda Fact_Norm/Fact_Mevcut birleşiminde
            # satırı bulunmayan aileleri de ekle (ör. mevcut=0 ve norm satırı
            # görünmeyen yardımcı aile). Böylece tüm unvanlar yok sayılmaz.
            store_by_id={v:k for k,v in id_by_store.items()}
            existing={(id_by_store.get(sk,''),uk) for sk,uk in zip(title['_Mağaza'],title['_Unvan'])}
            extra=[]
            for mid,uk in set(cmap_e.index)|set(cmap_f.index):
                if (mid,uk) not in existing:
                    extra.append({'_Mağaza':store_by_id.get(mid,''),'_Unvan':uk,'Norm Kadro':0,'Aktif Mevcut':0,'_Norm Kapsam Mevcut':0})
            if extra:
                title=pd.concat([title,pd.DataFrame(extra)],ignore_index=True,sort=False).fillna({'Norm Kadro':0,'Aktif Mevcut':0})
            idx=[(id_by_store.get(sk,''),uk) for sk,uk in zip(title['_Mağaza'],title['_Unvan'])]
            title['Norm Eksiği']=[int(cmap_e.get(k,0)) for k in idx]
            title['Norm Fazlası']=[int(cmap_f.get(k,0)) for k in idx]

    # Resmî kontrol dağılımını tüm şubelerde ana aile ve yardımcı denge
    # kurallarıyla uzlaştır. Böylece uzman/elit personel varken yapay açık
    # veya yardımcı kapasitesi normu tamamlarken boş pozisyon oluşmaz.
    title=_reconcile_main_family_rules(title)

    norm_title_map=norm.drop_duplicates('_Unvan').set_index('_Unvan')[nu].to_dict()
    staff_title_map=staff.drop_duplicates('_Unvan').set_index('_Unvan')[dep].to_dict()
    title['Unvan']=title['_Unvan'].map(norm_title_map).fillna(title['_Unvan'].map(staff_title_map))

    store_meta=pd.concat([
        norm[['_Mağaza',nmid,nm,'_Bölge']].rename(columns={nmid:'MağazaID',nm:'Mağaza','_Bölge':'Bölge Sorumlusu'}),
        staff[['_Mağaza',smid,sm,'_Bölge']].rename(columns={smid:'MağazaID',sm:'Mağaza','_Bölge':'Bölge Sorumlusu'})
    ],ignore_index=True).drop_duplicates('_Mağaza',keep='last')
    title=title.merge(store_meta,on='_Mağaza',how='left',suffixes=('_kontrol','_meta'))
    store_series=pd.Series('',index=title.index,dtype=object)
    for candidate in ['Mağaza_meta','Mağaza_kontrol','Mağaza']:
        if candidate in title.columns:
            store_series=store_series.mask(store_series.map(txt).eq(''),title[candidate])
    title['Mağaza']=store_series.map(txt)
    title_series=pd.Series('',index=title.index,dtype=object)
    for candidate in ['Unvan_kontrol','Unvan']:
        if candidate in title.columns:
            title_series=title_series.mask(title_series.map(txt).eq(''),title[candidate])
    title['Unvan']=title_series.mask(title_series.map(txt).eq(''),title['_Unvan'].map(lambda x:txt(x).upper()))
    title['UnvanID']=''
    _ana_unvan_uyari_var = '_Ana Unvan Personelsiz' in title.columns
    _secili_kolonlar = ['MağazaID','Mağaza','Bölge Sorumlusu','UnvanID','Unvan','Norm Kadro','Aktif Mevcut','Norm Eksiği','Norm Fazlası']
    if _ana_unvan_uyari_var:
        _secili_kolonlar.append('_Ana Unvan Personelsiz')
    tt=title[_secili_kolonlar].copy()
    if not _ana_unvan_uyari_var:
        tt['_Ana Unvan Personelsiz'] = False
    tt=tt.rename(columns={'_Ana Unvan Personelsiz': 'Ana Unvan Personelsiz Uyarısı'})
    for c in ['Norm Kadro','Aktif Mevcut','Norm Eksiği','Norm Fazlası']: tt[c]=numeric(tt[c]).astype(int)
    tt['Net Fark']=tt['Norm Fazlası']-tt['Norm Eksiği']
    st=tt.groupby(['MağazaID','Mağaza','Bölge Sorumlusu'],dropna=False)[['Norm Kadro','Aktif Mevcut','Norm Eksiği','Norm Fazlası']].sum().reset_index()
    st['Net Fark']=st['Norm Fazlası']-st['Norm Eksiği']
    # Genel aktif mevcut, Fact_Mevcut içindeki ad-soyadlı tüm aktif satırların sayısıdır.
    st.attrs['kpi_override']={
        'Aktif Mevcut':int(len(staff)),
        'Toplam Norm':int(tt['Norm Kadro'].sum()),
        'Norm Eksiği':int(tt['Norm Eksiği'].sum()),
        'Norm Fazlası':int(tt['Norm Fazlası'].sum()),
        'Net İhtiyaç':int(tt['Norm Fazlası'].sum()-tt['Norm Eksiği'].sum()),
    }
    return st,tt


def family_balance_notes(tt, store_key):
    """Bir mağaza için ana/yardımcı unvan ailesi arasında Kural A'nın
    (_reconcile_main_family_rules) uyguladığı dengelemeyi, kullanıcıya
    gösterilecek açıklama cümleleri olarak üretir.

    Metin kalıbı, kutucuklu Excel/PDF raporlarındaki (src/pdf_report.py,
    "MEVCUT DURUM AÇIKLAMASI") aynı denge cümlesiyle BİREBİR aynıdır —
    web ve raporlar arasında tutarlılık için ortak bu fonksiyondan üretilir.
    `tt`, state()'in döndürdüğü unvan-seviyeli tablodur (Mağaza/Unvan/
    Norm Kadro/Aktif Mevcut sütunlarını taşımalıdır).
    """
    from services.norm_rule_config import load_norm_rules
    balance = load_norm_rules().get('assistant_balance') or {}
    pairs = list((balance.get('pairs') or {}).items())
    if not pairs or tt is None or tt.empty:
        return []
    magaza_col = 'Mağaza' if 'Mağaza' in tt.columns else 'MağazaID'
    sub = tt[tt[magaza_col].astype(str) == str(store_key)]
    if sub.empty:
        return []
    notes = []
    for ana, yrd in pairs:
        ana_row = sub[sub['Unvan'].astype(str).str.upper() == str(ana).upper()]
        yrd_row = sub[sub['Unvan'].astype(str).str.upper() == str(yrd).upper()]
        if ana_row.empty or yrd_row.empty:
            continue
        ana_norm = int(numeric(ana_row['Norm Kadro']).fillna(0).iloc[0])
        ana_mevcut = int(numeric(ana_row['Aktif Mevcut']).fillna(0).iloc[0])
        yrd_norm = int(numeric(yrd_row['Norm Kadro']).fillna(0).iloc[0])
        yrd_mevcut = int(numeric(yrd_row['Aktif Mevcut']).fillna(0).iloc[0])
        aile_normu = ana_norm + yrd_norm
        aile_mevcut = ana_mevcut + yrd_mevcut
        dagilim_farkli = (ana_mevcut != ana_norm or yrd_mevcut != yrd_norm)
        if aile_normu > 0 and aile_mevcut >= aile_normu and dagilim_farkli:
            from src.text_utils import tr_title
            ana_t, yrd_t = tr_title(ana), tr_title(yrd)
            notes.append(
                f'{ana_t} normu {ana_norm}, {yrd_t} normu {yrd_norm}; '
                f'şubede {ana_mevcut} {ana_t} ve {yrd_mevcut} {yrd_t} mevcuttur. '
                'Aynı aile içindeki mevcut kapasiteyle norm dengesi korunabilir; '
                'bu denge norm eksiği toplamına dahil edilmemiştir.'
            )
    return notes
