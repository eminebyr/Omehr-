"""Bölge & Mağaza sekmesi.

Bu modül, web/app.py içindeki eski "with tabs[N]:" bloğundan otomatik
olarak çıkarılmıştır. Kod davranışı değiştirilmeden taşınmıştır; tüm
paylaşılan durum (sheets, kullanıcı/rol bilgisi, fm/detail/stores/kpis,
servis fonksiyonları) web.context.PageContext üzerinden gelir.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from web.context import PageContext


def render(ctx: PageContext) -> None:
    """Bölge & Mağaza sekmesinin içeriğini çizer."""
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

    # stores modeli, geriye dönük uyumluluk için aynı KPI'ları hem eski
    # (Norm Kadro/Aktif Mevcut/Norm Eksiği/Norm Fazlası) hem de kısa
    # (Norm/Mevcut/Eksik/Fazla) adlarla taşıyabilir. CEO ve bölge ekranında
    # bunların ikisini birden göstermek aynı veriyi iki kez tekrarlar.
    # Görünümde tek ve açıklayıcı bir şema kullanılır.
    def _series(*names: str) -> pd.Series:
        for name in names:
            if name in stores.columns:
                return pd.to_numeric(stores[name], errors="coerce").fillna(0)
        return pd.Series(0, index=stores.index, dtype="float64")

    store_view = pd.DataFrame(index=stores.index)
    store_view["Mağaza"] = stores.get("Mağaza", pd.Series("", index=stores.index)).fillna("")
    store_view["Bölge Sorumlusu"] = stores.get("Bölge Sorumlusu", pd.Series("", index=stores.index)).fillna("")
    store_view["Norm Kadro"] = _series("Norm Kadro", "Norm").astype(int)
    store_view["Aktif Mevcut"] = _series("Aktif Mevcut", "Mevcut").astype(int)
    store_view["Norm Eksiği"] = _series("Norm Eksiği", "Eksik").astype(int)
    store_view["Norm Fazlası"] = _series("Norm Fazlası", "Fazla").astype(int)
    store_view["Net Fark"] = store_view["Norm Fazlası"] - store_view["Norm Eksiği"]

    st.dataframe(
        store_view.sort_values(["Bölge Sorumlusu", "Mağaza"]),
        use_container_width=True,
        hide_index=True,
    )

    # AÇIKLAMA MOTORU (kutucuklu Excel/PDF raporlarındaki "MEVCUT DURUM
    # AÇIKLAMASI" ile aynı denge cümlesi — src/state_engine.py::
    # family_balance_notes). Bir mağazada ana/yardımcı unvan ailesi
    # arasında Kural A dengelemesi uygulandıysa (ör. fazla Yönetici,
    # boş Yönetici Yardımcısı normunu örtüyorsa) burada açıkça gösterilir.
    st.markdown("##### Norm Dengesi Açıklaması")
    magaza_secenekleri = sorted(store_view["Mağaza"].dropna().astype(str).unique())
    if magaza_secenekleri:
        secili_magaza = st.selectbox("Mağaza seçin", magaza_secenekleri, key="fb_notes_magaza")
        from services.family_balance import family_balance_notes
        notlar = family_balance_notes(detail, secili_magaza)
        if notlar:
            for n in notlar:
                st.info(n)
        else:
            st.caption("Bu mağazada ana/yardımcı unvan ailesi arasında bir denge uygulanmadı.")

