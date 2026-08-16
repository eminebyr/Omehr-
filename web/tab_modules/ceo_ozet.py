"""CEO Özet sekmesi.

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
from services.safe_exec import log_swallowed


def render(ctx: PageContext) -> None:
    """CEO Özet sekmesinin içeriğini çizer."""
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

    # NOT: Başlık, açıklama ve ana KPI kartları artık sadece üstte (tüm
    # sekmelerin üzerinde) bir kez gösteriliyor — burada tekrar etmiyoruz
    # (kullanıcı geri bildirimi: aynı bilgi iki kez görünüyordu).

    st.markdown("---")
    ceo_c1, ceo_c2 = st.columns(2)

    with ceo_c1:
        st.markdown("#### 🔴 En Riskli 10 Mağaza (Norm Eksiği)")
        try:
            _risk = detail.groupby("Mağaza", as_index=False)["Eksik"].sum().sort_values("Eksik", ascending=False)
            _risk = _risk[_risk["Eksik"] > 0].head(10)
            if not _risk.empty:
                st.dataframe(_risk.rename(columns={"Eksik": "Norm Eksiği"}), use_container_width=True, hide_index=True)
            else:
                st.success("Şu an kritik norm eksiği olan mağaza yok.")
        except Exception:
            st.info("Risk sıralaması hesaplanamadı.")

        st.markdown("#### 🔁 Transfer Bekleyenler")
        try:
            con_ceo = db()
            bekleyen = con_ceo.execute(
                "SELECT COUNT(*) FROM transfers WHERE status LIKE '%Bekliyor%'"
            ).fetchone()[0]
            toplam_transfer = con_ceo.execute("SELECT COUNT(*) FROM transfers").fetchone()[0]
            con_ceo.close()
            tc1, tc2 = st.columns(2)
            tc1.metric("Onay Bekleyen", tr_number(bekleyen))
            tc2.metric("Toplam Kayıtlı Transfer", tr_number(toplam_transfer))
        except Exception:
            st.info("Transfer verisi okunamadı.")

    with ceo_c2:
        st.markdown("#### 🤖 Yapay Zekâ Öncelikli Öneriler")
        try:
            from services.cached_excel_reader import read_sheet_cached
            _ai_ceo = read_sheet_cached(OUTPUT / "V19_AI_Norm_Sonuclari.xlsx", "AI_Norm_Sonuclari")
            _ai_ceo = _ai_ceo.dropna(subset=["Mağaza", "Unvan"])
            _kritik = _ai_ceo[_ai_ceo["Öncelik Seviyesi"].isin(["Kritik", "Yüksek"])].sort_values(
                "Güven Skoru", ascending=False
            ).head(8)
            if not _kritik.empty:
                st.dataframe(
                    _kritik[["Mağaza", "Unvan", "Öncelik Seviyesi", "Güven Skoru", "Önerilen Aksiyon"]],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.success("Kritik/Yüksek öncelikli AI önerisi bulunmuyor.")
        except Exception:
            st.info("AI önerileri henüz oluşmadı — main.py'yi çalıştırın.")

        st.markdown("#### 📊 Norm Fazlası En Yüksek 5 Mağaza")
        try:
            _fazla_ceo = detail.groupby("Mağaza", as_index=False)["Fazla"].sum().sort_values("Fazla", ascending=False)
            _fazla_ceo = _fazla_ceo[_fazla_ceo["Fazla"] > 0].head(5)
            if not _fazla_ceo.empty:
                st.dataframe(_fazla_ceo.rename(columns={"Fazla": "Norm Fazlası"}), use_container_width=True, hide_index=True)
            else:
                st.info("Norm fazlası olan mağaza yok.")
        except Exception as _exc:
            log_swallowed("web.tab_modules.ceo_ozet.render: beklenmeyen hata", _exc)
            pass

    st.markdown("---")
    st.markdown("#### 🏆 Mağaza KPI Skor Kartı (0-100)")
    st.caption(
        "Norm Uyumu %30 · Personel Devri %20 · Devamsızlık %20 · Fazla Mesai %15 · Performans %15. "
        "'Eğitim' kriteri kişi bazlı kayıt olmadığı için modele dahil edilmemiştir."
    )
    try:
        from services.cached_excel_reader import read_sheet_cached
        _skor = read_sheet_cached(INPUT, "Magaza_KPI_Skor_Karti", header=1)

        # Excel formülleri henüz hesaplanmamışsa pandas bu hücreleri None/NaN
        # olarak okuyabilir. CEO ekranında norm alanlarını doğrudan Python
        # motorunun güncel ``detail`` tablosundan güvenli biçimde tamamla.
        _skor = _skor.replace({"None": pd.NA, "NONE": pd.NA, "none": pd.NA, "": pd.NA})
        if "Mağaza" in _skor.columns and not detail.empty and "Mağaza" in detail.columns:
            _norm_map = detail.groupby("Mağaza", as_index=False).agg(
                **{
                    "_Norm Kadro": ("Norm", "sum"),
                    "_Norm Eksiği": ("Eksik", "sum"),
                    "_Norm Fazlası": ("Fazla", "sum"),
                }
            )
            _skor = _skor.merge(_norm_map, on="Mağaza", how="left")
            for _target, _source in (
                ("Norm Kadro", "_Norm Kadro"),
                ("Norm Eksiği", "_Norm Eksiği"),
                ("Norm Fazlası", "_Norm Fazlası"),
            ):
                if _target not in _skor.columns:
                    _skor[_target] = pd.NA
                _skor[_target] = pd.to_numeric(_skor[_target], errors="coerce").fillna(
                    pd.to_numeric(_skor[_source], errors="coerce")
                ).fillna(0)
            _skor.drop(columns=["_Norm Kadro", "_Norm Eksiği", "_Norm Fazlası"], inplace=True)

            # Norm uyumu: norm içindeki eksik ve fazla sapmalar çıkarılır.
            _norm = pd.to_numeric(_skor["Norm Kadro"], errors="coerce").fillna(0)
            _eksik = pd.to_numeric(_skor["Norm Eksiği"], errors="coerce").fillna(0)
            _fazla = pd.to_numeric(_skor["Norm Fazlası"], errors="coerce").fillna(0)
            _hesaplanan_uyum = ((1 - ((_eksik + _fazla) / _norm.where(_norm.ne(0)))) * 100).clip(0, 100).fillna(0)
            if "Norm Uyumu Puanı" not in _skor.columns:
                _skor["Norm Uyumu Puanı"] = _hesaplanan_uyum
            else:
                _skor["Norm Uyumu Puanı"] = pd.to_numeric(
                    _skor["Norm Uyumu Puanı"], errors="coerce"
                ).fillna(_hesaplanan_uyum)

        _skor = _skor.dropna(subset=["Mağaza"]).sort_values("MAĞAZA SKORU (0-100)", ascending=False)
        skc1, skc2 = st.columns(2)
        with skc1:
            st.markdown("**🟢 En Yüksek 10**")
            st.dataframe(_skor[["Mağaza", "MAĞAZA SKORU (0-100)", "Sınıf"]].head(10), use_container_width=True, hide_index=True)
        with skc2:
            st.markdown("**🔴 En Düşük 10 (öncelikli izlenmeli)**")
            st.dataframe(_skor[["Mağaza", "MAĞAZA SKORU (0-100)", "Sınıf"]].tail(10).iloc[::-1], use_container_width=True, hide_index=True)
        with st.expander("Tüm mağazalar ve bileşen puanları"):
            st.dataframe(_skor, use_container_width=True, hide_index=True)
    except Exception:
        st.info("Mağaza KPI Skor Kartı verisi okunamadı.")

