from __future__ import annotations

"""
VERİ YÜKLEME KATMANI (P2 — engine_core.py modülerleştirme, yedinci adım)
=====================================================================
Input Excel'inin okunması, dosya kilidi altında yedekleme/koordinat
yenileme/formül yeniden hesaplama orkestrasyonu. Tüm alt-adımlar (backup,
file_lock, home_proximity, excel_recalc) zaten kendi modüllerinde; burası
sadece bunları doğru sırayla çağırır. Başka hiçbir engine_core modülüne
bağımlı değildir.
"""

from src.text_utils import canon, col, numeric, req, txt, _region_name


def load(*, prepare: bool | None = None):
    import os

    # DÜZELTME: girdi kaynağı artık Excel'e SABİT DEĞİL. BASDAS_INPUT_SOURCE=db
    # ayarlandığında, Excel'e hiç dokunmadan (dosya kilidi, yedekleme,
    # LibreOffice yeniden hesaplama adımlarının HİÇBİRİ çalışmadan)
    # doğrudan veritabanından okunur — bu sayede Excel dosyası hiç
    # bulunmasa bile sistem çalışabilir. Varsayılan davranış (bayrak
    # ayarlanmamışsa) DEĞİŞMEDEN Excel'den okumaya devam eder; bu yüzden
    # mevcut tüm kurulumlar hiçbir kod/ayar değişikliği yapılmadan
    # ÇALIŞMAYA DEVAM EDER.
    if os.getenv("BASDAS_INPUT_SOURCE", "excel").strip().lower() == "db":
        from services.input_data_access import read_all_sheets
        sheets = read_all_sheets()
        try:
            from common_veri_okuma import input_file, fingerprint as _fp
            _referans_yol = input_file()
            _ozet = _fp(_referans_yol)
        except Exception:
            # Excel dosyası hiç yok (tam veritabanı-yalnız kurulum) — bazı
            # alt sistemler (sağlık kontrolü, yedekleme) gerçek bir Path
            # bekleyebilir; var olmayan ama geçerli bir yol referansı
            # döndürülür, İÇERİĞİ asla okunmaz (sheets zaten DB'den geldi).
            from services.runtime_paths import runtime_root as _rr
            _referans_yol = _rr() / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
            _ozet = "veritabani-kaynakli"
        return _finish_load(sheets, kaynak_yolu=_referans_yol, kaynak_ozet=_ozet)

    from common_veri_okuma import input_file,read_all,fingerprint
    p=input_file()
    if prepare is None:
        prepare = os.getenv('BASDAS_PREPARE_INPUT', '1') == '1'
    try:
        # EŞZAMANLI KULLANIM KORUMASI: Aşağıdaki 3 adım (yedekleme, koordinat
        # yenileme, formül yeniden hesaplama) dosyayı DEĞİŞTİRİR. Birden fazla
        # kullanıcı web panelini aynı anda açarsa, iki işlemin bu adımları TAM
        # OLARAK aynı anda çalıştırıp birbirinin yazdığını ezmesini önlemek için
        # bu blok bir dosya kilidi (services/file_lock.py) altında çalışır.
        # Kilit alınamazsa (başka bir işlem hâlâ yazıyorsa, en fazla 60 sn
        # beklenir) bu adımlar sessizce ATLANIR — dosya olduğu gibi okunur,
        # ana akış asla çökmez.
        if not prepare:
            raise StopIteration
        from services.file_lock import file_lock
        with file_lock(p) as alindi:
            if alindi:
                try:
                    # Dosyada herhangi bir değişiklik (koordinat yenileme, formül
                    # yeniden hesaplama) yapılmadan ÖNCE zaman damgalı bir yedek
                    # alınır. Bir şey ters giderse services/backup.py ->
                    # list_backups()/restore_backup() ile geri dönülebilir.
                    from services.backup import backup_input_file
                    backup_input_file(p)
                except Exception as _exc:
                    from services.safe_exec import log_swallowed
                    log_swallowed("load(): backup_input_file başarısız", _exc, level="ERROR")
                try:
                    from services.home_proximity import refresh_home_proximity
                    refresh_home_proximity(p)
                except Exception as _exc:
                    from services.safe_exec import log_swallowed
                    log_swallowed("load(): refresh_home_proximity başarısız (koordinat eksik olabilir)", _exc, level="INFO")
                try:
                    # KULLANICI KARARI: Fact_Mevcut/Fact_Norm'daki Mağaza/Unvan
                    # sütunları artık gerçek Excel formülüdür (VLOOKUP). openpyxl
                    # formülleri hesaplamadığı için (yukarıdaki kayıtlar dahil,
                    # HERHANGİ bir openpyxl kaydı) formül hücrelerinin önbelleğe
                    # alınmış sonucunu siler. Bu yüzden pandas'a okutmadan HEMEN
                    # önce dosya LibreOffice ile zorla yeniden hesaplatılır
                    # (taşınabilir profil: reference/lo_profile). LibreOffice
                    # kurulu değilse bu adım sessizce atlanır — AMA loglanır,
                    # çünkü bu, sistemin LibreOffice-bağımsızlığının KALBİDİR
                    # (statiklestir başarısız olursa Norm_Durumu ve Mağaza KPI
                    # Skor Kartı gibi türetilmiş sayfalar eski/yanlış kalabilir).
                    from services.formula_bagimsiz_hesapla import statiklestir
                    statiklestir(p)
                except Exception as _exc:
                    from services.safe_exec import log_swallowed
                    log_swallowed("load(): statiklestir() başarısız — türetilmiş sayfalar (Norm_Durumu, Skor Kartı) eski kalmış olabilir", _exc, level="ERROR")
                try:
                    # LibreOffice yalnız isteğe bağlı bir Excel önbellek yenileyicisidir.
                    # Resmî KPI ve rapor hesapları Python motorundan gelir.
                    from services.excel_recalc import recalculate_workbook, is_recalc_available
                    if is_recalc_available():
                        recalculate_workbook(p)
                except Exception as _exc:
                    from services.safe_exec import log_swallowed
                    log_swallowed("load(): isteğe bağlı Excel önbellek yenilemesi başarısız", _exc, level="INFO")
    except StopIteration:
        pass
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("load(): dosya kilidi/yenileme bloğu genel hata", _exc, level="ERROR")
    sheets=read_all(p)
    return _finish_load(sheets, kaynak_yolu=p, kaynak_ozet=fingerprint(p))


def _finish_load(sheets, *, kaynak_yolu, kaynak_ozet):
    """load()'un Excel VE veritabanı kaynaklı yollarının PAYLAŞTIĞI işleme
    adımları (şema doğrulama, VLOOKUP eşdeğeri, aile normalizasyonu, aktif
    personel filtresi). Önceden bu mantık load() içine gömülüydü ve yalnız
    Excel yoluna özeldi; artık iki kaynak için de TEK yerde, aynı şekilde
    çalışır — davranış farkı riski ortadan kalkar."""
    # VERİ ŞEMASI SÖZLEŞMESİ + FAIL-FAST (P0 — reviewer önerisi): zorunlu bir
    # sütun/sayfa TAMAMEN eksikse, yanlış bir rapor sessizce üretmek yerine
    # burada KESİN olarak durulur (SchemaValidationError fırlatılır — main.py
    # bunu yakalayıp "HATA: Sistem baslatilamadi" ile kullanıcıya gösterir,
    # tıpkı diğer kritik hatalar gibi). Sütunlar var ama İÇERİK şüpheliyse
    # (tekrarlayan PersonelID, geçersiz e-posta, vb.) bu SADECE loglanır —
    # pipeline durmaz, çünkü bu tür sorunlar genelde saha/İK düzeltmesi
    # gerektirir (BUCA2 örneğinde olduğu gibi), koddan çözülemez.
    from services.schema_validation import validate as _sema_dogrula
    _dogrulama_sonucu = _sema_dogrula(sheets)  # kritikse burada exception fırlar
    if _dogrulama_sonucu.uyarilar:
        from services.safe_exec import log_swallowed
        for _uyari in _dogrulama_sonucu.uyarilar:
            log_swallowed(f"VERİ KALİTESİ UYARISI: {_uyari}", Warning(_uyari), level="WARNING")
    if 'Fact_Norm' not in sheets or 'Fact_Mevcut' not in sheets: raise ValueError('Fact_Norm ve Fact_Mevcut sayfalari zorunludur.')
    norm=sheets['Fact_Norm'].copy(); staff=sheets['Fact_Mevcut'].copy()
    for df in (norm,staff): df.columns=[txt(c) for c in df.columns]
    # Personel kimliği kullanıcı tarafından atanan ayrı bir ID değildir. Ad Soyad benzersiz anahtardır.
    # Eski modüllerle geriye uyum için yalnız bellekte geçici PersonelID oluşturulur; Excel'de sütun yoktur.
    _ad_col=col(staff,'İsim Soyisim','Isim Soyisim','Ad Soyad')
    if _ad_col and 'PersonelID' not in staff.columns:
        staff['PersonelID']=staff[_ad_col].map(txt).str.strip()
    _pa=sheets.get('Personel_Adresleri')
    if _pa is not None and not _pa.empty and 'PersonelID' not in _pa.columns:
        _pa=_pa.copy(); _pa.columns=[txt(c) for c in _pa.columns]
        _pa_ad=col(_pa,'İsim Soyisim','Isim Soyisim','Ad Soyad')
        if _pa_ad: _pa['PersonelID']=_pa[_pa_ad].map(txt).str.strip()
        sheets['Personel_Adresleri']=_pa
    # KRİTİK GÜVENİLİRLİK ADIMI: Fact_Mevcut/Fact_Norm'daki Mağaza/Bölge Sorumlusu/
    # Unvan sütunları Excel formülüdür (VLOOKUP). Bu formüller sadece LibreOffice
    # dosyayı yeniden hesapladığında dolu gelir — LibreOffice kurulu değilse veya
    # hesaplama başarısız olursa bu sütunlar BOŞ okunur ve tüm norm hesaplaması
    # (mağaza/unvan eşleştirmesi) sessizce bozulur. Bunu KESİN olarak önlemek için,
    # motor BURADA, LibreOffice'in başarılı olup olmadığından tamamen bağımsız
    # olarak, Dim_Magaza/Dim_Unvan'dan kendi Python-taraflı VLOOKUP eşdeğerini
    # uygular. Excel formülleri sadece kullanıcı dosyayı Excel/LibreOffice'te
    # AÇTIĞINDA görsel/canlı bir deneyim sunmak içindir; resmi KPI hesaplaması
    # asla bunlara muhtaç değildir.
    dim_magaza=sheets.get('Dim_Magaza')
    dim_unvan=sheets.get('Dim_Unvan')
    if dim_magaza is not None and not dim_magaza.empty:
        dim_magaza=dim_magaza.copy(); dim_magaza.columns=[txt(c) for c in dim_magaza.columns]
        mag_id_c=col(dim_magaza,'MağazaID'); mag_ad_c=col(dim_magaza,'Mağaza'); mag_bolge_c=col(dim_magaza,'Bölge Sorumlusu')
        if mag_id_c and mag_ad_c:
            mag_ad_map=dict(zip(dim_magaza[mag_id_c],dim_magaza[mag_ad_c]))
            mag_bolge_map=dict(zip(dim_magaza[mag_id_c],dim_magaza[mag_bolge_c])) if mag_bolge_c else {}
            for df in (norm,staff):
                mid_c=col(df,'MağazaID')
                if mid_c:
                    mag_c=col(df,'Mağaza')
                    if mag_c: df[mag_c]=df[mid_c].map(mag_ad_map).fillna(df[mag_c])
                    if mag_bolge_map:
                        bolge_c=col(df,'Bölge Sorumlusu')
                        if bolge_c: df[bolge_c]=df[mid_c].map(mag_bolge_map).fillna(df[bolge_c])
    if dim_unvan is not None and not dim_unvan.empty:
        dim_unvan=dim_unvan.copy(); dim_unvan.columns=[txt(c) for c in dim_unvan.columns]
        uid_c=col(dim_unvan,'UnvanID'); uad_c=col(dim_unvan,'Unvan')
        if uid_c and uad_c:
            unvan_ad_map=dict(zip(dim_unvan[uid_c],dim_unvan[uad_c]))
            for df in (norm,staff):
                uidc=col(df,'UnvanID')
                if uidc:
                    unvan_c=col(df,'Unvan')
                    if unvan_c: df[unvan_c]=df[uidc].map(unvan_ad_map).fillna(df[unvan_c])
    # Gerçek unvan uzman/elit varyant ise norm ailesi kesin olarak ana unvandır.
    # Saha girişinde Departman yanlışlıkla yardımcı aileye yazılmış olsa bile
    # Python motoru bunu otomatik düzeltir. Yardımcı gerçek unvanlar ayrı kalır.
    dep_c=col(staff,'Departman')
    real_u_c=col(staff,'Unvan')
    if dep_c and real_u_c:
        _family_by_real={
            'yonetici':'YÖNETİCİ','uzman yonetici':'YÖNETİCİ','elit yonetici':'YÖNETİCİ',
            'yonetici yardimcisi':'YÖNETİCİ YARDIMCISI',
            'sarkuteri':'ŞARKÜTERİ','uzman sarkuteri':'ŞARKÜTERİ','elit sarkuteri':'ŞARKÜTERİ',
            'sarkuteri yardimcisi':'ŞARKÜTERİ YARDIMCISI',
            'kasap':'KASAP','uzman kasap':'KASAP','elit kasap':'KASAP',
            'kasap yardimcisi':'KASAP YARDIMCISI',
            'manav':'MANAV','uzman manav':'MANAV','elit manav':'MANAV',
            'manav yardimcisi':'MANAV YARDIMCISI',
        }
        _mapped=staff[real_u_c].map(canon).map(_family_by_real)
        staff.loc[_mapped.notna(),dep_c]=_mapped[_mapped.notna()]
        sheets['Fact_Mevcut']=staff.copy()
    # PersonelID boş olsa bile ad-soyad ve mağaza bilgisi bulunan çalışanlar mevcuda dahildir.
    # Önceki sürüm PersonelID boş 31 çalışanı silerek 611 yerine 580 gösteriyordu.
    pname=col(staff,'İsim Soyisim','Isim Soyisim','Ad Soyad')
    pid=col(staff,'PersonelID')
    if pname:
        staff=staff[staff[pname].notna() & staff[pname].map(txt).ne('')].copy()
    elif pid:
        staff=staff[staff[pid].notna()].copy()
    durum=col(staff,'Durum'); cikis=col(staff,'İşten Çıkış','Isten Cikis','Çıkış Tarihi','Cikis Tarihi')
    # Çıkış tarihi bulunan personel hariç tutulur. Durum formül önbelleği boş olan satırlar,
    # çıkış tarihi yoksa aktif kabul edilir.
    # DÜZELTME (iş kuralı — Madde 13/76): önceden burada yalnız
    # "İşten Çıkış DOLU mu" kontrol ediliyordu (tarih karşılaştırması
    # YOKTU) — bu, personnel_status.py'deki merkezi kuraldan BAĞIMSIZ,
    # tutarsız bir ikinci filtreydi. Artık AYNI merkezi, tarih-duyarlı
    # fonksiyonu kullanır: gelecek tarihli bir çıkış kaydı olan kişi
    # ÇIKIŞ TARİHİNE KADAR aktif sayılır (main.py'nin resmi raporları
    # ile web panelinin gösterdiği durum artık HER ZAMAN tutarlı).
    if cikis and staff[cikis].notna().any():
        from services.personnel_status import exit_is_recorded
        staff=staff[~staff[cikis].map(exit_is_recorded)].copy()
    elif durum and staff[durum].notna().any():
        valid=staff[durum].map(canon).isin({'aktif',''}) | staff[durum].isna()
        staff=staff[valid].copy()
    normcol=req(norm,'Norm Kadro','Toplam Norm','Norm')
    norm[normcol]=numeric(norm[normcol])
    # Bölge raporlarının iki ayrı ALİ dosyası üretmemesi için kaynaklarda da normalize et.
    nregion=col(norm,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge')
    sregion=col(staff,'Bölge Sorumlusu','Bolge Sorumlusu','Bölge')
    if nregion: norm[nregion]=norm[nregion].map(_region_name)
    if sregion: staff[sregion]=staff[sregion].map(_region_name)
    return kaynak_yolu,sheets,norm,staff,kaynak_ozet

# TAŞINDI: _region_name, _title_key artık src/text_utils.py'de tanımlı (saf
# fonksiyonlar, canon/txt dışında hiçbir dış duruma bağımlı değiller) — bu
# sayede excel_report.py/pdf_report.py bunları engine_core.py'ye dönüp
# dolanmadan doğrudan text_utils'ten alabiliyor (döngüsel import riski
# tamamen ortadan kalktı, bkz. FONT_TURKCE_DOGRULAMA.md).

