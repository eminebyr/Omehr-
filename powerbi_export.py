"""POWER BI EXPORT MOTORU.

Amaç: input Excel'indeki (Dim_Magaza, Dim_Unvan, Fact_Norm, Fact_Mevcut)
sayfalarını, Power BI'a DOĞRUDAN bağlanabilecek TEMİZ bir star şema
olarak `output/OMEHR_PowerBI_Model.xlsx` dosyasına yazar.

Neden ayrı bir dosya (kaynak input'u DEĞİL): Power BI ilişkileri,
katılan (join) sütunların TİPİNİN (metin/sayı) ve İÇERİĞİNİN (yetim ID
olmaması) tam tutarlı olmasını gerektirir. Kaynak Excel'de bu genelde
doğrudur ama garanti değildir — kullanıcı elle veri girerken bir mağaza
adını yanlış yazabilir, bir UnvanID boş kalabilir, MağazaID bir yerde
sayı bir yerde metin olarak girilebilir. Bu motor:

  1. Dim_Magaza / Dim_Unvan'ı TEKİLLEŞTİRİR (aynı ID iki kez girilmişse
     tek satıra indirir) ve anahtar sütunları METİN'e sabitler (Power
     BI'da "1" ile 1.0 farklı değer sayılır — bu, ilişkilerin en sık
     kırılma nedenidir).
  2. Fact_Norm / Fact_Mevcut'taki YETİM referansları (Dim tablosunda
     karşılığı olmayan MağazaID/UnvanID) SESSİZCE ATMAZ — ayrı bir
     "Yetim_Kayitlar" sayfasına yazar ki kullanıcı bunları görüp
     kaynak veriyi düzeltebilsin.
  3. Bir Dim_Tarih (takvim) boyutu ÜRETİR — kaynak Excel'de böyle bir
     sayfa yoksa bile (bkz. Ek B'de belgelenen ama hiçbir kodun
     okumadığı "Dim_Tarih" sayfası) — zaman bazlı analiz (aylık
     trend, mevsimsellik) için gereklidir.
  4. Her Dim/Fact çiftinin HANGİ sütunla ilişkilendirileceğini açıkça
     belgeleyen bir "Iliskiler" sayfası ekler — Power BI'da ilişkileri
     elle kurarken referans olması için.

Bu modül YALNIZ bir DIŞA AKTARIM aracıdır — Power BI'a otomatik veri
GÖNDERMEZ (bunun için Power BI REST API + bir "dataset" ve kimlik
doğrulama akışı gerekir, ayrı ve çok daha büyük bir iştir). Üretilen
dosya, Power BI Desktop'ta "Veri Al > Excel" ile açılıp bağlanır.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from services.exceptions import WorkbookError

OUTPUT_FILE_NAME = "OMEHR_PowerBI_Model.xlsx"


def _metin_id(seri: pd.Series) -> pd.Series:
    """Bir ID sütununu Power BI ilişkileri için GÜVENLİ, TUTARLI bir
    metin gösterimine çevirir. '1', '1.0' ve 1 hepsi '1' olur —
    aksi halde Power BI bunları FARKLI değerler sayar ve ilişki
    (relationship) sessizce hiç eşleşme üretmez."""
    def _tek(v):
        if pd.isna(v):
            return None
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()
    return seri.map(_tek)


def _clean_dim_magaza(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = sheets.get("Dim_Magaza")
    if df is None or df.empty or "MağazaID" not in df.columns:
        return pd.DataFrame(columns=["MağazaID", "Mağaza", "Bölge Sorumlusu"])
    df = df.copy()
    df["MağazaID"] = _metin_id(df["MağazaID"])
    df = df.dropna(subset=["MağazaID"]).drop_duplicates(subset=["MağazaID"], keep="last")
    for kolon in ("Mağaza", "Bölge Sorumlusu"):
        if kolon not in df.columns:
            df[kolon] = ""
    return df[["MağazaID", "Mağaza", "Bölge Sorumlusu"]].reset_index(drop=True)


def _clean_dim_unvan(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = sheets.get("Dim_Unvan")
    if df is None or df.empty or "UnvanID" not in df.columns:
        return pd.DataFrame(columns=["UnvanID", "Unvan"])
    df = df.copy()
    df["UnvanID"] = _metin_id(df["UnvanID"])
    df = df.dropna(subset=["UnvanID"]).drop_duplicates(subset=["UnvanID"], keep="last")
    if "Unvan" not in df.columns:
        df["Unvan"] = ""
    return df[["UnvanID", "Unvan"]].reset_index(drop=True)


def _clean_fact(
    sheets: dict[str, pd.DataFrame], sheet_adi: str, gerekli_kolonlar: list[str],
    dim_magaza: pd.DataFrame, dim_unvan: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bir fact tablosunu temizler; (temiz_tablo, yetim_kayitlar) döner."""
    df = sheets.get(sheet_adi)
    if df is None or df.empty:
        return pd.DataFrame(columns=gerekli_kolonlar), pd.DataFrame(columns=gerekli_kolonlar + ["Yetim Nedeni"])
    df = df.copy()
    if "MağazaID" in df.columns:
        df["MağazaID"] = _metin_id(df["MağazaID"])
    if "UnvanID" in df.columns:
        df["UnvanID"] = _metin_id(df["UnvanID"])

    gecerli_magaza = set(dim_magaza["MağazaID"]) if not dim_magaza.empty else set()
    gecerli_unvan = set(dim_unvan["UnvanID"]) if not dim_unvan.empty else set()

    magaza_yetim = ~df["MağazaID"].isin(gecerli_magaza) if "MağazaID" in df.columns else pd.Series(False, index=df.index)
    unvan_yetim = ~df["UnvanID"].isin(gecerli_unvan) if "UnvanID" in df.columns else pd.Series(False, index=df.index)
    yetim_maske = magaza_yetim | unvan_yetim

    yetim = df[yetim_maske].copy()
    if not yetim.empty:
        nedenler = []
        for _, satir in yetim.iterrows():
            sebep = []
            if "MağazaID" in df.columns and satir.get("MağazaID") not in gecerli_magaza:
                sebep.append(f"MağazaID '{satir.get('MağazaID')}' Dim_Magaza'da yok")
            if "UnvanID" in df.columns and satir.get("UnvanID") not in gecerli_unvan:
                sebep.append(f"UnvanID '{satir.get('UnvanID')}' Dim_Unvan'da yok")
            nedenler.append("; ".join(sebep))
        yetim["Yetim Nedeni"] = nedenler
        yetim.insert(0, "Kaynak Sayfa", sheet_adi)

    temiz = df[~yetim_maske].copy().reset_index(drop=True)
    return temiz, yetim.reset_index(drop=True)


def _build_dim_tarih(baslangic: date, bitis: date) -> pd.DataFrame:
    """Basit bir günlük takvim (tarih) boyutu üretir — kaynak Excel'de
    böyle bir sayfa olmasa bile zaman bazlı analiz için gereklidir."""
    gunler = pd.date_range(baslangic, bitis, freq="D")
    ay_adlari = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    return pd.DataFrame({
        "Tarih": gunler,
        "Yıl": gunler.year,
        "Ay No": gunler.month,
        "Ay Adı": [ay_adlari[m - 1] for m in gunler.month],
        "Çeyrek": gunler.quarter,
        "Hafta No": gunler.isocalendar().week.values,
        "Yıl-Ay": gunler.strftime("%Y-%m"),
    })


def build_powerbi_model(sheets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Star şema tablolarını temizleyip tek bir sözlükte döner.

    Dönüş anahtarları: dim_magaza, dim_unvan, dim_tarih, fact_norm,
    fact_mevcut, yetim_norm, yetim_mevcut, iliskiler (DataFrame'ler) ve
    ozet (dict).
    """
    dim_magaza = _clean_dim_magaza(sheets)
    dim_unvan = _clean_dim_unvan(sheets)
    fact_norm, yetim_norm = _clean_fact(
        sheets, "Fact_Norm", ["MağazaID", "UnvanID", "Norm Kadro"], dim_magaza, dim_unvan,
    )
    fact_mevcut, yetim_mevcut = _clean_fact(
        sheets, "Fact_Mevcut", ["PersonelID", "MağazaID", "UnvanID"], dim_magaza, dim_unvan,
    )

    # Takvim aralığı: İşe Giriş / İşten Çıkış varsa oradan; yoksa
    # bugünden geriye 2 yıl, ileriye 6 ay (temkinli, sabit bir aralık).
    bugun = date.today()
    tarih_kolonlari = []
    for kolon in ("İşe Giriş", "İşten Çıkış"):
        if kolon in fact_mevcut.columns:
            seri = pd.to_datetime(fact_mevcut[kolon], errors="coerce").dropna()
            if not seri.empty:
                tarih_kolonlari.append(seri)
    if tarih_kolonlari:
        tum_tarihler = pd.concat(tarih_kolonlari)
        baslangic = min(tum_tarihler.min().date(), bugun - timedelta(days=730))
        bitis = max(tum_tarihler.max().date(), bugun + timedelta(days=180))
    else:
        baslangic = bugun - timedelta(days=730)
        bitis = bugun + timedelta(days=180)
    dim_tarih = _build_dim_tarih(baslangic, bitis)

    iliskiler = pd.DataFrame([
        {"Fact Tablosu": "Fact_Norm", "Fact Sütunu": "MağazaID", "Dim Tablosu": "Dim_Magaza", "Dim Sütunu": "MağazaID", "Yön": "Çoktan-Bire (Fact -> Dim)"},
        {"Fact Tablosu": "Fact_Norm", "Fact Sütunu": "UnvanID", "Dim Tablosu": "Dim_Unvan", "Dim Sütunu": "UnvanID", "Yön": "Çoktan-Bire (Fact -> Dim)"},
        {"Fact Tablosu": "Fact_Mevcut", "Fact Sütunu": "MağazaID", "Dim Tablosu": "Dim_Magaza", "Dim Sütunu": "MağazaID", "Yön": "Çoktan-Bire (Fact -> Dim)"},
        {"Fact Tablosu": "Fact_Mevcut", "Fact Sütunu": "UnvanID", "Dim Tablosu": "Dim_Unvan", "Dim Sütunu": "UnvanID", "Yön": "Çoktan-Bire (Fact -> Dim)"},
        {"Fact Tablosu": "Fact_Mevcut", "Fact Sütunu": "İşe Giriş", "Dim Tablosu": "Dim_Tarih", "Dim Sütunu": "Tarih", "Yön": "Çoktan-Bire (Fact -> Dim, isteğe bağlı)"},
    ])

    ozet = {
        "dim_magaza_sayisi": len(dim_magaza),
        "dim_unvan_sayisi": len(dim_unvan),
        "fact_norm_sayisi": len(fact_norm),
        "fact_mevcut_sayisi": len(fact_mevcut),
        "yetim_norm_sayisi": len(yetim_norm),
        "yetim_mevcut_sayisi": len(yetim_mevcut),
        "dim_tarih_gun_sayisi": len(dim_tarih),
    }

    return {
        "dim_magaza": dim_magaza, "dim_unvan": dim_unvan, "dim_tarih": dim_tarih,
        "fact_norm": fact_norm, "fact_mevcut": fact_mevcut,
        "yetim_norm": yetim_norm, "yetim_mevcut": yetim_mevcut,
        "iliskiler": iliskiler, "ozet": ozet,
    }


def export_powerbi_workbook(sheets: dict[str, pd.DataFrame], output_dir: Path) -> dict[str, Any]:
    """build_powerbi_model()'i çalıştırıp sonucu tek bir Excel dosyasına
    (output/OMEHR_PowerBI_Model.xlsx) yazar. Dönüş: özet + dosya yolu."""
    model = build_powerbi_model(sheets)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / OUTPUT_FILE_NAME

    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            model["dim_magaza"].to_excel(writer, sheet_name="Dim_Magaza", index=False)
            model["dim_unvan"].to_excel(writer, sheet_name="Dim_Unvan", index=False)
            model["dim_tarih"].to_excel(writer, sheet_name="Dim_Tarih", index=False)
            model["fact_norm"].to_excel(writer, sheet_name="Fact_Norm", index=False)
            model["fact_mevcut"].to_excel(writer, sheet_name="Fact_Mevcut", index=False)
            model["iliskiler"].to_excel(writer, sheet_name="Iliskiler_Rehberi", index=False)
            if not model["yetim_norm"].empty:
                model["yetim_norm"].to_excel(writer, sheet_name="Yetim_Kayitlar_Norm", index=False)
            if not model["yetim_mevcut"].empty:
                model["yetim_mevcut"].to_excel(writer, sheet_name="Yetim_Kayitlar_Mevcut", index=False)
    except OSError as exc:
        raise WorkbookError(f"Power BI model dosyası yazılamadı: {exc}") from exc

    return {"file": str(path), **model["ozet"]}
