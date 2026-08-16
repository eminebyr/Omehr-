"""AI Geri Bildirim sekmesi.

Kapsam ve bilinçli sınırlar için bkz. services/ai_feedback.py modül
docstring'i. Özetle: bu ekran AI'nin ürettiği her norm önerisi için
yönetimin "Kabul Edildi / Reddedildi / Revize Edildi" kararını ve
gerekçesini kalıcı olarak kaydeder, geçmiş kararları ve kabul oranını
gösterir. "Gerçek norm ne oldu / fazla mesai azaldı mı" alanları şema
olarak vardır ama OTOMATİK doldurulmaz (bkz. modül docstring'i) —
bu ekranda yalnız manuel giriş için bir form sunulur.
"""
from __future__ import annotations

import pandas as pd
from services.cached_excel_reader import read_sheet_cached
import streamlit as st

from web.context import PageContext


def render(ctx: PageContext) -> None:
    """AI Geri Bildirim sekmesinin içeriğini çizer."""
    role, username = ctx.role, ctx.username
    is_global = ctx.is_global
    scope = ctx.scope
    OUTPUT = ctx.output_path
    norm_text = ctx.norm_text

    from services.ai_feedback import acceptance_summary, history, record_decision, VALID_DECISIONS
    from services.exceptions import TransferConflictError

    st.subheader("AI Geri Bildirim — öneriler gerçekten işe yarıyor mu?")
    st.caption(
        "Her AI norm önerisi için yönetim kararını (kabul/red/revize) ve "
        "gerekçesini kalıcı olarak kaydeder. Bu, AI'nin gerçek faydasını "
        "gösterecek en önemli göstergedir."
    )

    ozet = acceptance_summary()
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam kayıtlı karar", ozet["toplam_karar"])
    c2.metric(
        "Kabul oranı",
        f"%{ozet['kabul_orani']*100:.0f}" if ozet["kabul_orani"] is not None else "—",
    )
    c3.metric("Reddedilen", ozet["karar_dagilimi"].get("Reddedildi", 0))

    st.divider()
    st.subheader("Yeni AI önerisi için karar kaydet")

    ai_path = OUTPUT / "V19_AI_Norm_Sonuclari.xlsx"
    if not ai_path.is_file():
        st.info("AI analizi için önce 'Tüm tabloları şimdi yenile' düğmesini çalıştırın.")
    else:
        try:
            ai_view = read_sheet_cached(ai_path, "AI_Norm_Sonuclari")
        except Exception:
            st.warning("AI_Norm_Sonuclari sayfası okunamadı.")
            ai_view = pd.DataFrame()

        if not ai_view.empty:
            if not is_global and "Bölge" in ai_view.columns:
                ai_view = ai_view[ai_view["Bölge"].astype(str).map(norm_text).eq(norm_text(scope))]

            ai_view = ai_view.copy()
            ai_view["_etiket"] = (
                ai_view.get("Mağaza", "").astype(str) + " / " + ai_view.get("Unvan", "").astype(str)
                + " (öneri: " + ai_view.get("AI Önerilen Norm", "").astype(str) + ")"
            )
            secim = st.selectbox("Mağaza / Unvan", ai_view["_etiket"].tolist(), index=None, placeholder="Seçin...")
            if secim:
                satir = ai_view[ai_view["_etiket"] == secim].iloc[0]
                with st.form("ai_geri_bildirim_form"):
                    karar = st.radio("Karar", sorted(VALID_DECISIONS), horizontal=True)
                    gerekce = st.text_area(
                        "Gerekçe (özellikle Reddedildi/Revize Edildi için önerilir)",
                        placeholder="Örn: Sahada gerçek ihtiyaç farklı, saha etüdü bekleniyor, mevsimsel etki vb.",
                    )
                    if st.form_submit_button("Kararı kaydet"):
                        try:
                            record_decision(
                                magaza_id=satir.get("MağazaID", ""),
                                magaza=satir.get("Mağaza", ""),
                                unvan_id=satir.get("UnvanID", ""),
                                unvan=satir.get("Unvan", ""),
                                ai_onerilen_norm=pd.to_numeric(satir.get("AI Önerilen Norm", 0), errors="coerce") or 0,
                                yonetim_normu=pd.to_numeric(satir.get("Yönetim Normu", 0), errors="coerce") or 0,
                                guven_skoru=pd.to_numeric(satir.get("Güven Skoru", 0), errors="coerce") or 0,
                                karar=karar,
                                karar_veren=username,
                                gerekce=gerekce,
                            )
                            st.success("Karar kaydedildi.")
                            st.rerun()
                        except TransferConflictError as exc:
                            st.error(str(exc))
        else:
            st.caption("Gösterilecek AI önerisi bulunamadı.")

    st.divider()
    st.subheader("Karar geçmişi")
    gecmis = history(magaza=None if is_global else None, limit=200)
    if gecmis:
        df = pd.DataFrame(gecmis)[[
            "created_at", "magaza", "unvan", "ai_onerilen_norm", "yonetim_normu",
            "guven_skoru", "karar", "karar_veren", "gerekce",
        ]]
        df.columns = [
            "Tarih", "Mağaza", "Unvan", "AI Önerisi", "Yönetim Normu",
            "Güven Skoru", "Karar", "Karar Veren", "Gerekçe",
        ]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Henüz kaydedilmiş bir karar yok.")
