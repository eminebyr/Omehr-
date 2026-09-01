from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from services.sales_root_cause import build_sales_root_cause
from services.supabase_sync import fetch_sales_targets
from web.context import PageContext


@st.cache_data(ttl=120, show_spinner=False)
def _targets() -> list[dict]:
    return fetch_sales_targets()


def render(ctx: PageContext) -> None:
    st.subheader("Satış Kök Neden Analizi")
    st.caption("Satış sapmasını fiş, sepet, reel büyüme, norm ve operasyon kanıtlarıyla mağaza bazında açıklar.")
    inflation = st.number_input("Karşılaştırma enflasyonu (%)", min_value=0.0, max_value=200.0, value=32.11, step=0.1)
    result, latest, previous = build_sales_root_cause(
        sheets=ctx.sheets, stores=ctx.stores, targets=_targets(), inflation_pct=float(inflation),
    )
    if result.empty:
        st.info("Aylık Operasyon KPI veya mağaza norm verisi bulunamadı.")
        return

    below = int(pd.to_numeric(result["Hedef Gerçekleşme %"], errors="coerce").lt(100).sum())
    unsupported = int(result["Personel İddiası"].eq("Desteklenmiyor").sum())
    missing = int(result["Hedef Gerçekleşme %"].isna().sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hedef Altında", below)
    c2.metric("Personel İddiası Kanıtsız", unsupported)
    c3.metric("Hedef/Veri Açığı", missing)
    c4.metric("Dönem", latest or "—", delta=f"Önceki: {previous or '—'}")

    chart = result.dropna(subset=["Norm Karşılama %", "Hedef Gerçekleşme %"]).copy()
    if not chart.empty:
        quadrant = px.scatter(
            chart, x="Norm Karşılama %", y="Hedef Gerçekleşme %", color="Otomatik Kök Neden",
            size="Gerçekleşen Ciro", hover_name="Mağaza", hover_data=["Fiş Değişim %", "Sepet Değişim %", "Reel Büyüme %"],
            title="Norm Karşılama – Satış Hedef Gerçekleşme Matrisi",
        )
        quadrant.add_vline(x=100, line_dash="dash", line_color="#D5A95C")
        quadrant.add_hline(y=100, line_dash="dash", line_color="#D5A95C")
        st.plotly_chart(quadrant, use_container_width=True)

        drivers = chart.melt(
            id_vars=["Mağaza"], value_vars=["Fiş Değişim %", "Sepet Değişim %", "Reel Büyüme %"],
            var_name="Sürücü", value_name="Değişim %",
        ).dropna()
        if not drivers.empty:
            driver_chart = px.bar(
                drivers, x="Mağaza", y="Değişim %", color="Sürücü", barmode="group",
                title="Fiş, Ortalama Sepet ve Reel Büyüme Karşılaştırması",
            )
            driver_chart.add_hline(y=0, line_color="#5B8CA0")
            st.plotly_chart(driver_chart, use_container_width=True)

    counts = result["Otomatik Kök Neden"].value_counts().rename_axis("Kök Neden").reset_index(name="Mağaza Sayısı")
    st.plotly_chart(
        px.bar(counts, x="Mağaza Sayısı", y="Kök Neden", orientation="h", text="Mağaza Sayısı", title="Kök Neden Dağılımı"),
        use_container_width=True,
    )

    st.markdown("#### Satışın Hesap Verme Tablosu")
    st.dataframe(result.sort_values(["Hedef Gerçekleşme %", "Norm Karşılama %"], na_position="first"), use_container_width=True, hide_index=True)
    st.caption("Satış hedefi, açıklama ve aksiyon Vercel'deki yetkili Satış girişiyle Supabase'e kaydedilir; Streamlit aynı kaydı salt okunur gösterir.")
