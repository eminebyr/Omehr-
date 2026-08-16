from __future__ import annotations

"""
SAHA/İK/FİNANS VERİ TOPLAMA — PAYLAŞILAN İŞ MANTIĞI
=========================================================
Bu modül, "Dummy"/"Saha Etüdü Bekleniyor" işaretli operasyonel verileri
GERÇEK ölçüm/kayıtlarla değiştirme mantığını içerir. Hem komut satırı
betikleri (saha_olcumu_ice_aktar.py vb.) HEM Streamlit web paneli
("Veri Toplama" sekmesi) AYNI bu fonksiyonları çağırır — mantık iki
yerde ayrı ayrı tutulmaz.

Hiçbir fonksiyon veri UYDURMAZ — sadece kullanıcının GERÇEKTEN girdiği
değerleri, dürüst kaynak etiketiyle ana dosyaya aktarır.
"""

from datetime import datetime

import pandas as pd


def saha_olcumu_uygula(form_wb, ana_wb) -> tuple[int, list[dict]]:
    """SAHA_OLCUM_FORMU'ndaki (açık workbook) gerçek ölçümleri, ana
    workbook'un Standart_Sure_Kutuphanesi sayfasına uygular. İkisi de
    zaten AÇIK openpyxl Workbook nesneleri olmalı (dosya yolu değil) —
    böylece hem CLI (dosyadan açar) hem Streamlit (yüklenen dosyadan
    açar) aynı fonksiyonu kullanabilir."""
    form_ws = form_wb["Ölçüm Formu"]
    form_basliklar = [c.value for c in form_ws[1]]

    def fs(ad):
        return form_basliklar.index(ad) + 1

    olcumler = []
    for r in range(3, form_ws.max_row + 1):
        akt_id = form_ws.cell(r, fs("AktiviteID")).value
        if not akt_id:
            continue
        ortalama = form_ws.cell(r, fs("ORTALAMA (Dk)")).value
        if ortalama in (None, ""):
            continue
        n_olcum = sum(
            1 for col in ("Ölçüm 1 (Dk)", "Ölçüm 2 (Dk)", "Ölçüm 3 (Dk)", "Ölçüm 4 (Dk)", "Ölçüm 5 (Dk)")
            if form_ws.cell(r, fs(col)).value not in (None, "")
        )
        olcumler.append({
            "akt_id": str(akt_id).strip(),
            "ortalama": round(float(ortalama), 2),
            "n": n_olcum,
            "magaza": str(form_ws.cell(r, fs("Ölçülen Mağaza")).value or "belirtilmemiş"),
            "kisi": str(form_ws.cell(r, fs("Ölçen Kişi")).value or "belirtilmemiş"),
            "tarih": str(form_ws.cell(r, fs("Ölçüm Tarihi")).value or datetime.now().strftime("%d.%m.%Y")),
        })

    ana_ws = ana_wb["Standart_Sure_Kutuphanesi"]
    ana_basliklar = [c.value for c in ana_ws[1]]
    ana_sutun = {h: i + 1 for i, h in enumerate(ana_basliklar)}

    guncellenen = 0
    for o in olcumler:
        for r in range(2, ana_ws.max_row + 1):
            if str(ana_ws.cell(r, ana_sutun["AktiviteID"]).value).strip() == o["akt_id"]:
                ana_ws.cell(r, ana_sutun["Standart Süre (Dk)"]).value = o["ortalama"]
                ana_ws.cell(r, ana_sutun["Kaynak"]).value = (
                    f"Gerçek/Saha Ölçümü — Ölçen: {o['kisi']}, Tarih: {o['tarih']}, "
                    f"Mağaza: {o['magaza']}, n={o['n']} ölçüm"
                )
                guncellenen += 1
                break
    return guncellenen, olcumler


def vardiya_pik_turet(ana_wb, saatlik_yogunluk_df: pd.DataFrame) -> int:
    """Gerçek 'Saatlik Yoğunluk' verisinden Vardiya_Pik_Saat'i türetir."""
    df = saatlik_yogunluk_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    turetilen = {}
    for magaza_id, grup in df.groupby("MagazaID"):
        toplam = grup["Yoğunluk Skoru"].sum()
        if toplam <= 0 or len(grup) < 3:
            continue
        skorlar = grup.sort_values("Saat").set_index("Saat")["Yoğunluk Skoru"]
        saatler = sorted(skorlar.index)
        en_iyi_pencere, en_iyi_toplam = None, -1
        for i in range(len(saatler) - 2):
            pencere = saatler[i:i + 3]
            if pencere[-1] - pencere[0] != 2:
                continue
            t = skorlar.loc[pencere].sum()
            if t > en_iyi_toplam:
                en_iyi_toplam, en_iyi_pencere = t, pencere
        if en_iyi_pencere is None:
            continue
        aralik = f"{en_iyi_pencere[0]:02d}:00-{en_iyi_pencere[-1] + 1:02d}:00"
        pay = round(en_iyi_toplam / toplam, 2)
        ort = skorlar.mean()
        katsayi = round(skorlar.loc[en_iyi_pencere].mean() / ort, 2) if ort else 1.0
        turetilen[magaza_id] = (aralik, pay, katsayi)

    ws = ana_wb["Vardiya_Pik_Saat"]
    headers = [c.value for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(headers)}
    guncellenen = 0
    for r in range(2, ws.max_row + 1):
        mid = ws.cell(r, col["MağazaID"]).value
        if mid not in turetilen:
            continue
        aralik, pay, katsayi = turetilen[mid]
        ws.cell(r, col["Pik Saat Aralığı"]).value = aralik
        ws.cell(r, col["Pik Hacim Payı"]).value = pay
        ws.cell(r, col["Pik Katsayısı"]).value = katsayi
        ws.cell(r, col["Veri Kaynağı"]).value = "Saatlik Yoğunluk - Gerçek/Türetilmiş"
        guncellenen += 1
    return guncellenen


def ik_finans_uygula(form_wb, ana_wb) -> dict:
    """IK_FINANS_VERI_FORMU'ndaki gerçek değerleri Kapasite_Parametreleri
    ve Maliyet_Parametreleri'ne uygular."""
    def _guncelle(form_ws, ana_ws, eslesme, id_kolonu="UnvanID"):
        form_basliklar = [c.value for c in form_ws[1]]
        ana_basliklar = [c.value for c in ana_ws[1]]
        ana_id_col = ana_basliklar.index(id_kolonu) + 1
        guncellenen = 0
        for form_r in range(2, form_ws.max_row + 1):
            uid = form_ws.cell(form_r, form_basliklar.index(id_kolonu) + 1).value
            if not uid:
                continue
            degerler = {}
            for ana_kolon, form_kolon in eslesme.items():
                deger = form_ws.cell(form_r, form_basliklar.index(form_kolon) + 1).value
                if deger not in (None, ""):
                    degerler[ana_kolon] = deger
            if not degerler:
                continue
            for ana_r in range(2, ana_ws.max_row + 1):
                if str(ana_ws.cell(ana_r, ana_id_col).value).strip() == str(uid).strip():
                    for ana_kolon, deger in degerler.items():
                        ana_ws.cell(ana_r, ana_basliklar.index(ana_kolon) + 1).value = deger
                    if "Veri Durumu" in ana_basliklar:
                        ana_ws.cell(ana_r, ana_basliklar.index("Veri Durumu") + 1).value = "Gerçek/İK-Finans Kaynağı"
                    guncellenen += 1
                    break
        return guncellenen

    n1 = _guncelle(
        form_wb["Kapasite Politikası"], ana_wb["Kapasite_Parametreleri"],
        {"Brüt Vardiya (Dk)": "GERÇEK Brüt Vardiya (Dk)", "Mola (Dk)": "GERÇEK Mola (Dk)",
         "Zorunlu Kayıp (Dk)": "GERÇEK Zorunlu Kayıp (Dk)", "Verimlilik Oranı": "GERÇEK Verimlilik Oranı"},
    )
    n2 = _guncelle(
        form_wb["Maliyet Verileri"], ana_wb["Maliyet_Parametreleri"],
        {"Aylık Brüt Maliyet": "GERÇEK Aylık Brüt Maliyet",
         "Aylık İşveren Maliyeti": "GERÇEK Aylık İşveren Maliyeti",
         "İşe Alım Maliyeti": "GERÇEK İşe Alım Maliyeti"},
    )
    return {"kapasite": n1, "maliyet": n2}


def vardiya_pik_turet_ve_serialize(ana_wb, saatlik_yogunluk_df: pd.DataFrame) -> tuple[int, bytes]:
    """DÜZELTME (mimari sınır): bkz. saha_olcumu_uygula_ve_serialize."""
    from io import BytesIO
    n = vardiya_pik_turet(ana_wb, saatlik_yogunluk_df)
    buf = BytesIO()
    ana_wb.save(buf)
    return n, buf.getvalue()


def saha_olcumu_uygula_ve_serialize(form_wb, ana_wb) -> tuple[int, list[dict], bytes]:
    """DÜZELTME (mimari sınır): web/ katmanı artık Workbook.save() çağrısını
    doğrudan yapmıyor — UI'daki bu çağrı buraya, servis katmanına taşındı.
    Sonucu indirilebilir bayt dizisi olarak döner."""
    from io import BytesIO
    n, olcumler = saha_olcumu_uygula(form_wb, ana_wb)
    if n == 0:
        return n, olcumler, b""
    buf = BytesIO()
    ana_wb.save(buf)
    return n, olcumler, buf.getvalue()


def ik_finans_uygula_ve_serialize(form_wb, ana_wb) -> tuple[dict, bytes]:
    """DÜZELTME (mimari sınır): bkz. saha_olcumu_uygula_ve_serialize."""
    from io import BytesIO
    sonuc = ik_finans_uygula(form_wb, ana_wb)
    if sonuc["kapasite"] == 0 and sonuc["maliyet"] == 0:
        return sonuc, b""
    buf = BytesIO()
    ana_wb.save(buf)
    return sonuc, buf.getvalue()
