"""Personel Performansı sekmesi.

Bu modül, web/app.py içindeki eski "with tabs[N]:" bloğundan otomatik
olarak çıkarılmıştır. Kod davranışı değiştirilmeden taşınmıştır; tüm
paylaşılan durum (sheets, kullanıcı/rol bilgisi, fm/detail/stores/kpis,
servis fonksiyonları) web.context.PageContext üzerinden gelir.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from web.context import PageContext
from services.safe_exec import log_swallowed


def render(ctx: PageContext) -> None:
    """Personel Performansı sekmesinin içeriğini çizer."""
    sheets, acc = ctx.sheets, ctx.acc
    fm, detail, stores, kpis = ctx.fm, ctx.detail, ctx.stores, ctx.kpis
    user, username, role, scope, email = ctx.user, ctx.username, ctx.role, ctx.scope, ctx.email
    is_global = ctx.is_global
    can_view_personal_address = ctx.can_view_personal_address
    approval_level, can_approve = ctx.approval_level, ctx.can_approve
    ROOT, INPUT, OUTPUT, DB = ctx.root, ctx.input_path, ctx.output_path, ctx.db_path
    APPROVERS, BD_RENK = ctx.approvers, ctx.bd_renk
    db, log = ctx.db, ctx.log
    enqueue, job_status, tenant_code = ctx.enqueue, ctx.job_status, ctx.tenant_code
    norm_text, tr_number, tr_money_compact = ctx.norm_text, ctx.tr_number, ctx.tr_money_compact
    set_password, password_error = ctx.set_password, ctx.password_error
    refresh_home_proximity, maps_route = ctx.refresh_home_proximity, ctx.maps_route
    verify_password, transfer_recipients = ctx.verify_password, ctx.transfer_recipients
    cancel_transfer_request, redirect_transfer_request = ctx.cancel_transfer_request, ctx.redirect_transfer_request
    bulk_branch_mail_panel = ctx.bulk_branch_mail_panel
    _enqueue_and_process = ctx.enqueue_and_process
    read_input = ctx.read_input

    st.subheader("Mağaza Bazlı Proxy Performans Risk Göstergesi (0–100)")
    st.caption(
        "Devamlılık %25 · Verimlilik %31,25 · Enflasyona Göre Mağaza Katkısı %18,75 · "
        "Fazla Mesai Verimliliği %12,5 · Yönetici Değerlendirmesi %12,5"
    )
    try:
        from services.cached_excel_reader import read_sheet_cached
        perf_endeks = read_sheet_cached(INPUT, "Personel_Performans_Endeksi", header=1)
    except Exception as _exc:
        log_swallowed("web.tab_modules.performans.render: beklenmeyen hata", _exc)
        perf_endeks = pd.DataFrame()
    if perf_endeks.empty:
        st.info("Performans Endeksi verisi bulunamadı.")
    else:
        st.warning(
            "⚠️ Puantaj/eğitim/disiplin kaydı olmadığı için bu kriterler modelden çıkarılmıştır. "
            "Skor artık ağırlıklı olarak mağazanın **enflasyona göre reel büyümesine** (TÜİK %32,11, "
            "Haziran 2026) dayanır. Tüm bileşenler mağazanın aylık verisinden o mağazadaki personele "
            "yansıtılmıştır (proxy) — henüz kişiye özel ölçüm değildir. Yöntem için "
            "'Performans_Endeksi_Kriterleri' sayfasına bakın."
        )
        st.error(
            "🚫 **Bu endeks TEK BAŞINA disiplin, işten çıkarma, ücret veya terfi kararında "
            "kullanılamaz.** Proxy (mağaza bazlı) bir göstergedir, kişinin kendi performansının "
            "doğrudan ölçümü değildir. Herhangi bir personel kararı öncesi İK ile birlikte "
            "değerlendirilmeli ve gerçek kişi bazlı veriyle (puantaj, saha gözlemi, yönetici görüşmesi) "
            "doğrulanmalıdır."
        )
        if not is_global:
            perf_endeks = perf_endeks[perf_endeks["Mağaza"].isin(
                sheets.get("Dim_Magaza", pd.DataFrame())[
                    sheets.get("Dim_Magaza", pd.DataFrame()).get("Bölge Sorumlusu", pd.Series(dtype=str)).astype(str).map(norm_text).eq(norm_text(scope))
                ].get("Mağaza", pd.Series(dtype=str))
            )]
        sinif_etiketleri = {
            "🟢 Üstün Performans": "🟢 Güçlü mağaza sinyali",
            "🔵 Başarılı": "🔵 Olumlu mağaza sinyali",
            "🟡 Gelişim Gerekli": "🟡 İnceleme gerekli",
            "🔴 Yakın Takip Gerekli": "🔴 Kişi bazlı veri doğrulaması gerekli",
        }
        perf_endeks = perf_endeks.copy()
        perf_endeks["Proxy Sınıf"] = perf_endeks["Sınıf"].map(sinif_etiketleri).fillna("⚪ Veri yetersiz")
        c1, c2, c3, c4 = st.columns(4)
        sinif_sayilari = perf_endeks["Proxy Sınıf"].value_counts()
        c1.metric("🟢 Güçlü Sinyal", tr_number(sinif_sayilari.get("🟢 Güçlü mağaza sinyali", 0)))
        c2.metric("🔵 Olumlu Sinyal", tr_number(sinif_sayilari.get("🔵 Olumlu mağaza sinyali", 0)))
        c3.metric("🟡 İnceleme Gerekli", tr_number(sinif_sayilari.get("🟡 İnceleme gerekli", 0)))
        c4.metric("🔴 Veri Doğrulaması Gerekli", tr_number(sinif_sayilari.get("🔴 Kişi bazlı veri doğrulaması gerekli", 0)))

        left, right = st.columns(2)
        fig_pie = px.pie(
            perf_endeks, names="Proxy Sınıf", title="Proxy Risk/Sinyal Dağılımı",
            color="Proxy Sınıf",
            color_discrete_map={
                "🟢 Güçlü mağaza sinyali": "#70AD47", "🔵 Olumlu mağaza sinyali": "#4472C4",
                "🟡 İnceleme gerekli": "#FFC000", "🔴 Kişi bazlı veri doğrulaması gerekli": "#C00000",
                "⚪ Veri yetersiz": "#A5A5A5",
            },
        )
        left.plotly_chart(fig_pie, use_container_width=True)

        magaza_ort = perf_endeks.groupby("Mağaza", as_index=False)["Performans Endeksi (0-100)"].mean().sort_values("Performans Endeksi (0-100)", ascending=False).head(15)
        fig_magaza = px.bar(
            magaza_ort, x="Performans Endeksi (0-100)", y="Mağaza", orientation="h", text="Performans Endeksi (0-100)",
            title="En Yüksek Ortalama Performans — 15 Mağaza", color="Performans Endeksi (0-100)",
            color_continuous_scale="Greens",
        )
        fig_magaza.update_traces(textposition="outside", cliponaxis=False)
        right.plotly_chart(fig_magaza, use_container_width=True)

        if "Mağaza Reel Büyüme %" in perf_endeks.columns:
            reel_ozet = perf_endeks.drop_duplicates("Mağaza")[["Mağaza", "Mağaza Reel Büyüme %"]].dropna().sort_values("Mağaza Reel Büyüme %", ascending=False)
            fig_reel = px.bar(
                reel_ozet, x="Mağaza Reel Büyüme %", y="Mağaza", orientation="h",
                title="Mağaza Reel Büyümesi (Enflasyon %32,11 Baz Alınarak) — Performans Katkı Kaynağı",
                color="Mağaza Reel Büyüme %", color_continuous_scale=["#C00000", "#F2F2F2", "#70AD47"], color_continuous_midpoint=0,
                height=max(500, 20 * len(reel_ozet)),
            )
            fig_reel.add_vline(x=0, line_dash="dash", line_color="grey")
            st.plotly_chart(fig_reel, use_container_width=True)

        if can_view_personal_address:
            st.markdown("#### Kişi Bazlı Proxy Gösterge Tablosu (yalnız İK/Admin)")
            fc1, fc2, fc3 = st.columns(3)
            magaza_secim = fc1.selectbox("Mağaza filtrele", ["(Tümü)"] + sorted(perf_endeks["Mağaza"].dropna().unique().tolist()), key="perf_magaza_filtre")
            unvan_secim = fc2.selectbox("Unvan filtrele", ["(Tümü)"] + sorted(perf_endeks["Unvan"].dropna().unique().tolist()), key="perf_unvan_filtre")
            sinif_secim = fc3.selectbox("Sınıf filtrele", ["(Tümü)"] + sorted(perf_endeks["Sınıf"].dropna().unique().tolist()), key="perf_sinif_filtre")
            gosterim = perf_endeks.copy()
            if magaza_secim != "(Tümü)":
                gosterim = gosterim[gosterim["Mağaza"] == magaza_secim]
            if unvan_secim != "(Tümü)":
                gosterim = gosterim[gosterim["Unvan"] == unvan_secim]
            if sinif_secim != "(Tümü)":
                gosterim = gosterim[gosterim["Sınıf"] == sinif_secim]
            goster_kolonlar = [
                "PersonelID", "İsim Soyisim", "Mağaza", "Unvan", "Devamlılık Puanı (%25)",
                "Verimlilik Puanı (%31,25)", "Enflasyona Göre Mağaza Katkısı (%18,75)", "Mağaza Reel Büyüme %",
                "Fazla Mesai Verimliliği Puanı (%12,5)", "Yönetici Değerlendirme Puanı (%12,5)",
                "Performans Endeksi (0-100)", "Proxy Sınıf",
            ]
            goster_kolonlar = [c for c in goster_kolonlar if c in gosterim.columns]
            st.dataframe(
                gosterim.sort_values("Performans Endeksi (0-100)", ascending=False)[goster_kolonlar],
                use_container_width=True, hide_index=True,
            )
        else:
            # KVKK/HR gizliliği: isim + düşük performans etiketi (🔴) gibi hassas kişi
            # bazlı bilgi, İK/Admin dışındaki rollere (bölge müdürü dahil) gösterilmez.
            # Sadece mağaza bazında ORTALAMA (yukarıdaki grafiklerde zaten var) görünür.
            st.info(
                "🔒 Kişi bazlı performans tablosu (isim ve düşük performans etiketleri dahil) "
                "yalnız İK Direktörü ve Sistem Yöneticisi rolüne açıktır. Yukarıdaki mağaza bazlı "
                "ortalama grafikler tüm rollere görünür."
            )

        st.markdown("---")
        st.markdown(
            "**Transfer motoruna entegrasyon önerisi:** Bu skorlar, Transfer Optimizasyonu ve "
            "Transfer Merkezi sekmelerinde şu şekillerde kullanılabilir — (1) aynı mağazadaki tüm "
            "🟢/🔵 sınıfı personelin aynı anda transfer edilmesini engellemek, (2) kritik açığı olan "
            "mağazalara öncelikli olarak yüksek performanslı adayları önermek, (3) 🔴 sınıfındaki "
            "personel için eğitim/gelişim planı tetiklemek. Bu entegrasyon henüz aktif değildir — "
            "istenirse ayrıca eklenebilir."
        )

