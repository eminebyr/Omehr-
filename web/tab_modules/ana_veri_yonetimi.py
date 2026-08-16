"""Ana veri yönetimi: Excel açmadan panelden CRUD ve toplu düzenleme."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from web.context import PageContext


def _editor(label: str, df: pd.DataFrame, key: str, help_text: str) -> pd.DataFrame:
    st.markdown(f"### {label}")
    st.caption(help_text)
    return st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=key,
    )


def render(ctx: PageContext) -> None:
    if ctx.role not in {"ADMIN", "HR_DIRECTOR", "IK_DIREKTORU"}:
        st.info("Ana veri yönetimi yalnız Sistem Yöneticisi ve İK Direktörü rolüne açıktır.")
        return

    from services.master_data_admin import read_tables, save_tables, validate_tables

    st.header("Ana Veri Yönetimi")
    st.write(
        "Fact_Mevcut, Fact_Norm, Dim_Magaza ve Dim_Unvan verilerini Excel'i açmadan "
        "buradan ekleyebilir, düzeltebilir veya silebilirsiniz. Kaydetme öncesinde otomatik "
        "yedek ve veri doğrulaması yapılır."
    )
    st.warning("Satır silmek için tablonun solundaki satırı seçip Delete tuşunu kullanın. Kaydetmeden yapılan değişiklikler sisteme geçmez.")

    if "master_data_tables" not in st.session_state:
        st.session_state["master_data_tables"] = read_tables(ctx.input_path)
    tables = st.session_state["master_data_tables"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Personel", "Norm Kadro", "Mağazalar", "Unvanlar", "Kontrol ve Kaydet"])
    with tab1:
        tables["Fact_Mevcut"] = _editor(
            "Personel / Fact_Mevcut", tables["Fact_Mevcut"], "edit_fact_mevcut",
            "İsim Soyisim benzersiz anahtardır. Departman norm hesabında, UnvanID gerçek unvanın getirilmesinde kullanılır."
        )
    with tab2:
        tables["Fact_Norm"] = _editor(
            "Norm Kadro / Fact_Norm", tables["Fact_Norm"], "edit_fact_norm",
            "Aynı MağazaID + UnvanID yalnız bir kez bulunabilir. Norm Kadro sıfır veya pozitif tam sayı olmalıdır. Açıklama alanına yazılan notlar PDF Mevcut Durum bölümüne ve Excel hücre notlarına aktarılır."
        )
    with tab3:
        tables["Dim_Magaza"] = _editor(
            "Mağaza Sözlüğü / Dim_Magaza", tables["Dim_Magaza"], "edit_dim_magaza",
            "MağazaID benzersizdir. Mağaza adı veya bölge sorumlusu burada değiştiğinde Fact tablolarına otomatik yansır."
        )
    with tab4:
        tables["Dim_Unvan"] = _editor(
            "Unvan Sözlüğü / Dim_Unvan", tables["Dim_Unvan"], "edit_dim_unvan",
            "UnvanID benzersizdir. Unvan adı burada değiştiğinde Fact tablolarına otomatik yansır."
        )
    with tab5:
        errors = validate_tables(tables)
        if errors:
            st.error("Kaydetmeden önce aşağıdaki hataları düzeltin:")
            for err in errors:
                st.write(f"• {err}")
        else:
            st.success("Veri doğrulaması başarılı. Kayıt yapılabilir.")
        c1, c2, c3 = st.columns(3)
        if c1.button("Değişiklikleri Kaydet", type="primary", disabled=bool(errors), use_container_width=True):
            try:
                backup = save_tables(ctx.root, ctx.input_path, tables, ctx.username)
                st.session_state.pop("master_data_tables", None)
                st.success(f"Ana veriler kaydedildi. Otomatik yedek: {backup.name}")
                st.info("Web KPI'larını yenilemek için üst bölümdeki 'Tüm tabloları şimdi yenile' düğmesini kullanın.")
            except Exception as exc:
                st.error(f"Kaydetme başarısız: {exc}")
        if c2.button("Excel'den Yeniden Yükle", use_container_width=True):
            st.session_state["master_data_tables"] = read_tables(ctx.input_path)
            st.rerun()
        with open(ctx.input_path, "rb") as f:
            c3.download_button(
                "Güncel Inputu İndir", data=f.read(), file_name=ctx.input_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.session_state["master_data_tables"] = tables
