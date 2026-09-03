from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from services.real_staffing_need import build_real_staffing_need
from web.context import PageContext


def render(ctx: PageContext) -> None:
    st.subheader("Gerçek Personel İhtiyacı")
    st.caption(
        "Norm açığını; transfer, geçici operasyonel açık, norm revizyonu ve gerçek işe alım "
        "ihtiyacı olarak sınıflandırır. Yetersiz veride kesin karar yayımlamaz."
    )
    result, kpis = build_real_staffing_need(ctx.detail, sheets=ctx.sheets)
    cards = st.columns(5)
    for column, key in zip(cards, (
        "Norm Eksiği", "Transferle Kapatılabilir", "Geçici Operasyonel Açık",
        "Norm Revizyonu Gerektiren", "Gerçek İşe Alım İhtiyacı",
    )):
        column.metric(key, kpis[key])

    if result.empty:
        st.info("Mağaza-unvan bazında norm eksiği bulunmuyor.")
        return

    decision_counts = (
        result.groupby("Karar", as_index=False)["Norm Eksiği"].sum()
        .rename(columns={"Norm Eksiği": "Açık Kişi"})
    )
    st.plotly_chart(
        px.bar(
            decision_counts, x="Açık Kişi", y="Karar", orientation="h",
            text="Açık Kişi", title="Karar Dağılımı",
        ),
        use_container_width=True,
    )
    st.dataframe(
        result.sort_values(["Gerçek İşe Alım İhtiyacı", "Norm Eksiği"], ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Bu ekran karar desteğidir; resmî normu değiştirmez ve İK onayı olmadan işlem oluşturmaz.")
