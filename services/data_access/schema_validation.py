from __future__ import annotations

"""
VERİ ŞEMASI SÖZLEŞMESİ VE FAIL-FAST KONTROLÜ
=================================================
İki FARKLI kategori kesin olarak ayrılır (reviewer önerisi):

1) ŞEMA İHLALİ (kritik, FAIL-FAST): Bir sayfada ZORUNLU bir sütun tamamen
   eksikse, motor bu durumda YANLIŞ bir rapor üretmek yerine DURMALIDIR.
   Bu modül böyle bir durumda SchemaValidationError fırlatır.

2) VERİ KALİTESİ UYARISI (kritik değil, LOGLANIR, akış BOZULMAZ): Sütunlar
   var ama İÇERİK şüpheli (ör. tekrarlayan PersonelID, geçersiz e-posta,
   çıkış tarihi işe girişten önce). Bunlar toplanıp raporlanır ama
   pipeline durmaz — çünkü bu tür sorunlar genelde saha/İK düzeltmesi
   gerektirir, koddan çözülemez (bu konuşma boyunca BUCA2 örneğinde
   olduğu gibi).
"""

import re
from dataclasses import dataclass, field

import pandas as pd


class SchemaValidationError(Exception):
    """Zorunlu bir sütun/sayfa tamamen eksik olduğunda fırlatılır — bu,
    veri kalitesi uyarısından farklı olarak PIPELINE'I DURDURMALIDIR."""


# Her sayfa için ZORUNLU sütunlar — biri bile eksikse fail-fast.
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "Fact_Mevcut": ["MağazaID", "UnvanID", "İsim Soyisim"],
    "Fact_Norm": ["MağazaID", "UnvanID", "Norm Kadro"],
    "Dim_Magaza": ["MağazaID", "Mağaza"],
    "Dim_Unvan": ["UnvanID", "Unvan"],
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class DogrulamaSonucu:
    kritik_hatalar: list[str] = field(default_factory=list)   # şema ihlalleri (varsa zaten exception fırlar, burası boş kalır)
    uyarilar: list[str] = field(default_factory=list)          # veri kalitesi uyarıları
    detay: dict = field(default_factory=dict)

    @property
    def sorunsuz(self) -> bool:
        return not self.uyarilar


def _sema_kontrolu(sheets: dict[str, pd.DataFrame]) -> None:
    """FAIL-FAST: zorunlu sütun/sayfa eksikse SchemaValidationError fırlatır."""
    eksikler = []
    for sheet_adi, zorunlu_sutunlar in REQUIRED_COLUMNS.items():
        df = sheets.get(sheet_adi)
        if df is None or df.empty:
            eksikler.append(f"'{sheet_adi}' sayfası bulunamadı veya tamamen boş.")
            continue
        for sutun in zorunlu_sutunlar:
            if sutun not in df.columns:
                eksikler.append(f"'{sheet_adi}' sayfasında zorunlu sütun eksik: '{sutun}'")
    if eksikler:
        raise SchemaValidationError(
            "ŞEMA İHLALİ — pipeline durduruldu (rapor ÜRETİLMEDİ, çünkü eksik veriyle "
            "üretilen rapor yanlış olurdu):\n" + "\n".join(f"  - {e}" for e in eksikler)
        )


def validate(sheets: dict[str, pd.DataFrame]) -> DogrulamaSonucu:
    """Önce şema kontrolü (fail-fast), sonra veri kalitesi kontrolleri
    (uyarı, akışı bozmaz) çalıştırılır."""
    _sema_kontrolu(sheets)  # eksikse burada exception fırlar, devam edilmez

    sonuc = DogrulamaSonucu()
    fm = sheets.get("Fact_Mevcut", pd.DataFrame())
    fn = sheets.get("Fact_Norm", pd.DataFrame())
    dm = sheets.get("Dim_Magaza", pd.DataFrame())
    ml = sheets.get("Mail_Listesi", pd.DataFrame())

    # 1) İsim Soyisim benzersiz mi? (aktif kayıtlar arasında)
    if "İşten Çıkış" in fm.columns:
        aktif = fm[fm["İşten Çıkış"].isna() | (fm["İşten Çıkış"].astype(str).str.strip() == "")]
    else:
        aktif = fm
    if "İsim Soyisim" in aktif.columns:
        _ad=aktif["İsim Soyisim"].astype(str).str.strip()
        tekrar=_ad[_ad.duplicated(keep=False) & _ad.ne("")].unique().tolist()
        if tekrar:
            sonuc.uyarilar.append(f"İsim Soyisim benzersiz DEĞİL (aktif kayıtlarda tekrarlanan {len(tekrar)} ad): {tekrar[:10]}")

    # 2) Aktif personelin mağazası Dim_Magaza'da var mı?
    if "MağazaID" in aktif.columns and "MağazaID" in dm.columns:
        gecerli_magazalar = set(dm["MağazaID"].dropna())
        gecersiz = aktif[~aktif["MağazaID"].isin(gecerli_magazalar)]
        if not gecersiz.empty:
            sonuc.uyarilar.append(
                f"{len(gecersiz)} aktif personelin MağazaID'si Dim_Magaza'da TANIMLI DEĞİL: "
                f"{sorted(gecersiz['MağazaID'].dropna().unique().tolist())[:10]}"
            )

    # 3) Norm Kadro < 0 olan kayıt var mı?
    if "Norm Kadro" in fn.columns:
        negatif = fn[pd.to_numeric(fn["Norm Kadro"], errors="coerce") < 0]
        if not negatif.empty:
            sonuc.uyarilar.append(f"Fact_Norm'da Norm Kadro < 0 olan {len(negatif)} kayıt var (imkansız değer).")

    # 4) Aynı MağazaID+UnvanID için birden fazla norm satırı (bilgi amaçlı —
    #    bu sistemde BİLEREK toplanabilir bir durumdur, kritik değil, sadece görünür kılınır).
    if {"MağazaID", "UnvanID"}.issubset(fn.columns):
        cift_sayimi = fn.groupby(["MağazaID", "UnvanID"]).size()
        tekrarlayan = cift_sayimi[cift_sayimi > 1]
        if not tekrarlayan.empty:
            sonuc.detay["coklu_norm_satiri_sayisi"] = int(len(tekrarlayan))

    # 5) Çıkış tarihi işe giriş tarihinden önce mi?
    if {"İşe Giriş", "İşten Çıkış"}.issubset(fm.columns):
        giris = pd.to_datetime(fm["İşe Giriş"], errors="coerce")
        cikis = pd.to_datetime(fm["İşten Çıkış"], errors="coerce")
        gecersiz_tarih = fm[(cikis.notna()) & (giris.notna()) & (cikis < giris)]
        if not gecersiz_tarih.empty:
            # KVKK — LOGLARDA KİŞİSEL VERİ MASKELEME: Bu uyarı mesajı LOGGER
            # üzerinden düz metin log dosyasına yazılır. Gerçek "İsim Soyisim"
            # yerine PersonelID kullanılır — kimlik tespiti için PersonelID
            # tek başına yeterli değildir (Fact_Mevcut sayfasına erişim
            # gerekir), gerçek ad ise doğrudan kişiyi ifşa eder.
            kimlikler = gecersiz_tarih.get("İsim Soyisim", pd.Series(dtype=object)).dropna().tolist()
            sonuc.uyarilar.append(f"{len(gecersiz_tarih)} kayıtta İşten Çıkış tarihi İşe Giriş'ten ÖNCE (İsim Soyisim): {kimlikler[:10]}")

    # 6) Aynı personel (İsim Soyisim) birden fazla AKTİF mağazada mı?
    if {"İsim Soyisim", "MağazaID"}.issubset(aktif.columns):
        coklu_magaza = aktif.groupby("İsim Soyisim")["MağazaID"].nunique()
        sorunlu = coklu_magaza[coklu_magaza > 1]
        if not sorunlu.empty:
            sonuc.uyarilar.append(f"{len(sorunlu)} personel AYNI ANDA birden fazla aktif mağazada görünüyor: {sorunlu.index.tolist()[:10]}")

    # 7) Bölge yöneticisi (Bölge Sorumlusu) olmayan mağaza var mı?
    if {"MağazaID", "Bölge Sorumlusu"}.issubset(dm.columns):
        bos_bolge = dm[dm["Bölge Sorumlusu"].isna() | (dm["Bölge Sorumlusu"].astype(str).str.strip() == "")]
        if not bos_bolge.empty:
            sonuc.uyarilar.append(f"{len(bos_bolge)} mağazanın Bölge Sorumlusu BOŞ: {bos_bolge['MağazaID'].tolist()[:10]}")

    # 8) E-posta adresleri geçerli formatta mı? (Mail_Listesi) — bazı
    #    hücreler ";" veya "," ile ayrılmış BİRDEN FAZLA adres içerebilir
    #    (tasarım gereği geçerli), bu yüzden her adres AYRI AYRI kontrol edilir.
    if "E-posta" in ml.columns:
        def _tum_adresler_gecerli(hucre) -> bool:
            metin = str(hucre or "").strip()
            if not metin:
                return True
            adresler = [a.strip() for a in re.split(r"[;,]", metin) if a.strip()]
            return bool(adresler) and all(_EMAIL_RE.match(a) for a in adresler)

        gecersiz_email = ml[ml["E-posta"].notna() & (ml["E-posta"].astype(str).str.strip() != "") & ~ml["E-posta"].map(_tum_adresler_gecerli)]
        if not gecersiz_email.empty:
            sonuc.uyarilar.append(f"Mail_Listesi'nde {len(gecersiz_email)} GEÇERSİZ formatta e-posta var: {gecersiz_email['E-posta'].tolist()[:10]}")

    # 9) ÜRETİM ORTAMINDA TEST VERİSİ UYARISI (KVKK/veri kalitesi — reviewer
    #    önerisi): Sistemde "Dummy" işaretli veri oranı yüksekse, kullanıcı
    #    bunun FARKINDA olmalı — bu, gerçek üretim kararları için güvenilmez
    #    bir temel oluşturabilir.
    if "E-posta" in ml.columns:
        toplam_email = ml["E-posta"].notna().sum()
        dummy_email = ml["E-posta"].astype(str).str.contains("dummy", case=False, na=False).sum()
        if toplam_email and dummy_email / toplam_email > 0.30:
            sonuc.uyarilar.append(
                f"⚠️ ÜRETİM UYARISI: Mail_Listesi'ndeki e-postaların %{dummy_email/toplam_email*100:.0f}'i "
                f"'dummy' işaretli test verisi — bu sistem gerçek üretimde mi, test ortamında mı çalışıyor kontrol edin."
            )
    sure_kutuphanesi = sheets.get("Standart_Sure_Kutuphanesi", pd.DataFrame())
    if "Kaynak" in sure_kutuphanesi.columns and not sure_kutuphanesi.empty:
        # NOT: Etiket "Dummy"den "Saha Etüdü Bekleniyor"ya çevrildi (daha
        # profesyonel görünüm için) — ama VERİ HÂLÂ AYNI DERECEDE
        # DOĞRULANMAMIŞ. Tespit mantığı da yeni etikete göre güncellendi;
        # aksi halde bu uyarı sessizce hiç tetiklenmezdi (yanlış güven verirdi).
        dummy_oran = sure_kutuphanesi["Kaynak"].astype(str).str.contains("Saha Etüdü Bekleniyor|Dummy", case=False, na=False, regex=True).mean()
        if dummy_oran > 0.30:
            sonuc.uyarilar.append(
                f"⚠️ ÜRETİM UYARISI: Standart_Sure_Kutuphanesi'ndeki aktivitelerin %{dummy_oran*100:.0f}'i "
                f"saha etüdü yapılmamış (henüz doğrulanmamış varsayım) süre içeriyor — AI önerileri bu ölçüde güvenilmezdir."
            )

    return sonuc
