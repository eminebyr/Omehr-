"""Transfer Optimizasyonu sekmesi.

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

from web.geo_transfer import transfer_recommendations
from web.context import PageContext


def render(ctx: PageContext) -> None:
    """Transfer Optimizasyonu sekmesinin içeriğini çizer."""
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

    st.info("Mesafeler ücretsiz olarak input koordinatlarından veya Transfer_Kisitlari rota tablosundan hesaplanır. Google Cloud, API anahtarı ve ödeme hesabı gerekmez.")
    scenario=st.selectbox("Senaryo",["Dengeli","Aynı Unvan","Aynı Bölge","Minimum Mesafe","Eve En Yakın"])
    recs=transfer_recommendations(fm,detail,sheets,scenario=scenario,limit=200)
    if recs.empty: st.info("Uygun norm fazlası / norm eksiği eşleşmesi bulunamadı.")
    else:
        st.dataframe(
            recs,use_container_width=True,hide_index=True,
            column_config={"Google Maps":st.column_config.LinkColumn("Google Maps",display_text="Rotayı Aç")}
        )
        chart=recs.dropna(subset=["Şubeler Arası Mesafe (km)"])
        if not chart.empty: st.plotly_chart(px.scatter(chart,x="Şubeler Arası Mesafe (km)",y="Transfer Uygunluk Puanı",hover_name="Personel",size="Hedef Risk Puanı",color="Personel Memnuniyeti Puanı",title="Şube Yakınlığı - Ev Yakınlığı - Transfer Uygunluğu"),use_container_width=True)
