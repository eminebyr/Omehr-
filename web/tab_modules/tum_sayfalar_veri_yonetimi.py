"""Tüm Sayfalar (Veritabanı) — 62+ input sayfasının TAMAMI için genel,
şema tabanlı web CRUD paneli.

Bu panel yalnızca OMEHR_INPUT_SOURCE=db ayarlandığında GERÇEK veri
gösterir/kaydeder (bkz. services/input_data_access.py). Excel modunda
(varsayılan) bilgilendirme mesajı gösterir — hiçbir veri kaybı riski
yoktur, çünkü bu iki mod birbirinden TAMAMEN bağımsızdır.

Neden ayrı bir panel (mevcut "Ana Veri Yönetimi"nden farklı): O panel
yalnız 4 çekirdek sayfayı (Fact_Mevcut, Fact_Norm, Dim_Magaza, Dim_Unvan)
Excel'e geri yazacak şekilde tasarlanmıştı. Bu panel TÜM 62+ sayfayı,
veritabanına yazacak şekilde, sayfa başına özel kod YAZMADAN (şemadan
otomatik türeterek) kapsar.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from web.context import PageContext

# Hangi sayfaların SAHA/İK/vb. tarafından elle doldurulacağını, hangilerinin
# sistem çıktısı olduğu için salt-okunur kalması gerektiğini belirler.
# (bkz. daha önce hazırlanan OMEHR_SAHA_VERI_INPUT_SABLONU.xlsx ile aynı
# sınıflandırma mantığı.)
OTOMATIK_SAYFALAR = {
    "Dim_Tarih", "İş Yükü Endeksi", "REFERENTIAL_CONTROL", "STAR_SCHEMA_REHBER",
    "KULLANIM_REHBERI", "AI_Norm_Sonuclari", "Veri_Kalitesi_Log", "Transfer_Talepleri",
    "Ev_Sube_Rota_Ozeti", "Norm_Bazli_Transfer_Rotalari", "Personel_Performans_Endeksi",
    "Performans_Endeksi_Kriterleri", "Tahmin_Dogruluk_Testi", "Verimlilik_Operasyon_Tahmini",
    "Istatistiksel_Model_Testi", "Norm_Durumu", "Oncelikli_Transfer_Listesi",
    "Magaza_KPI_Skor_Karti", "00_AI_SIZ_GIRIS_REHBERI", "00_TUM_SAYFALAR_REHBERI",
}

KATEGORILER = {
    "Çekirdek (Mağaza/Unvan/Norm/Personel)": [
        "Dim_Magaza", "Dim_Unvan", "Fact_Norm", "Fact_Mevcut", "Dim_CikisNedeni",
        "Departman Matrisi", "Mağaza Özellikleri",
    ],
    "Adres ve Konum": ["Magaza_Adres", "Personel_Adresleri"],
    "Günlük Operasyon": [
        "Günlük Operasyon", "Saatlik Yoğunluk", "Kasa Kullanımı", "Online Sipariş",
        "Mal Kabul", "Sevkiyat", "Fire ve İade", "Müşteri Şikayetleri",
    ],
    "İK ve Bordro": [
        "Fazla Mesai", "Devamsızlık", "Eğitim", "İzin", "Performans",
        "Personel Maliyeti", "Devir Riski", "Aylık Operasyon KPI",
    ],
    "Saha Etüdü / AI Parametreleri": [
        "Standart_Sure_Kutuphanesi", "Kapasite_Parametreleri", "Gunluk_Aktivite_Hacmi",
        "Kalibrasyon", "Minimum_Kadro_Kurallari", "Vardiya_Pik_Saat",
    ],
    "Tahmin ve Senaryo": [
        "Tahmin_Parametreleri", "Isgucu_Tahmin_Parametreleri", "Tahmin_Takvimi",
        "Maliyet_Parametreleri", "Senaryo_Parametreleri", "Transfer_Kisitlari",
        "Rapor_Parametreleri", "Parametreler", "Çarpanlar", "Girdiler",
    ],
    "Mail ve Kullanıcı Erişimi": ["Mail_Listesi", "Sube_Mail_Listesi", "Kurumsal_Eposta_Rehberi"],
    "Sistem Sonuçları (Salt Okunur)": sorted(OTOMATIK_SAYFALAR),
}


def _tum_manuel_sayfalar() -> list[str]:
    from services.input_db_schema import load_schema
    sema = load_schema()
    manuel = [s for s in sema if s not in OTOMATIK_SAYFALAR]
    kategorize = {s for liste in KATEGORILER.values() for s in liste}
    kalan = sorted(set(manuel) - kategorize)
    if kalan:
        KATEGORILER.setdefault("Diğer", [])
        for s in kalan:
            if s not in KATEGORILER["Diğer"]:
                KATEGORILER["Diğer"].append(s)
    return manuel


def render(ctx: PageContext) -> None:
    st.header("Tüm Sayfalar (Veritabanı Tabanlı Veri Girişi)")

    kaynak = os.getenv("OMEHR_INPUT_SOURCE", "excel").strip().lower()
    if kaynak != "db":
        st.info(
            "Bu panel yalnız sistem veritabanı modunda (OMEHR_INPUT_SOURCE=db) "
            "çalışır. Şu an sistem Excel modunda — mevcut '4 çekirdek sayfa' "
            "editörü için 'Ana Veri Yönetimi' sekmesini kullanın.\n\n"
            "Veritabanı moduna geçmek için yöneticinize başvurun: "
            "`services/input_excel_migration.py` ile mevcut Excel bir kez "
            "veritabanına aktarılır, ardından OMEHR_INPUT_SOURCE=db ile "
            "sistem başlatılır."
        )
        return

    if ctx.role not in {"ADMIN", "HR_DIRECTOR", "IK_DIREKTORU"}:
        st.info("Bu panel yalnız Sistem Yöneticisi ve İK Direktörü rolüne açıktır.")
        return

    from services.input_db_schema import load_schema
    from services.input_data_access import read_sheet, write_sheet

    _tum_manuel_sayfalar()
    sema = load_schema()

    st.caption(
        "62+ input sayfasının TAMAMI burada düzenlenebilir. Gri (salt-okunur) "
        "sayfalar sistemin kendi ürettiği sonuçlardır — elle düzenlenmez."
    )

    kategori = st.selectbox("Kategori", list(KATEGORILER.keys()), key="tumsayfa_kategori")
    sayfa_listesi = [s for s in KATEGORILER[kategori] if s in sema]
    if not sayfa_listesi:
        st.warning("Bu kategoride sayfa bulunamadı.")
        return
    sayfa = st.selectbox("Sayfa", sayfa_listesi, key="tumsayfa_sayfa")

    salt_okunur = sayfa in OTOMATIK_SAYFALAR
    state_key = f"tumsayfa_veri_{sayfa}"
    if state_key not in st.session_state:
        st.session_state[state_key] = read_sheet(sayfa)
    df = st.session_state[state_key]

    if salt_okunur:
        st.warning(f"'{sayfa}' sistemin kendi ürettiği bir sonuç sayfasıdır — salt okunur gösterilir.")
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    st.markdown(f"### {sayfa}")
    duzenlenen = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"editor_{sayfa}",
    )
    st.session_state[state_key] = duzenlenen

    c1, c2, c3 = st.columns(3)
    if c1.button("Değişiklikleri Kaydet", type="primary", use_container_width=True, key=f"kaydet_{sayfa}"):
        try:
            yazilan = write_sheet(sayfa, duzenlenen, kullanici=getattr(ctx, "username", ""))
            st.success(f"'{sayfa}' kaydedildi ({yazilan} satır).")
        except Exception as exc:
            st.error(f"Kaydetme başarısız: {exc}")
    if c2.button("Veritabanından Yeniden Yükle", use_container_width=True, key=f"yenile_{sayfa}"):
        st.session_state[state_key] = read_sheet(sayfa)
        st.rerun()
    c3.caption(f"{len(duzenlenen)} satır")
