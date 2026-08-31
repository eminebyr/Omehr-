from __future__ import annotations
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st


def render(ctx):
    st.subheader("30 / 60 / 90 Günlük İş Gücü Tahmin Adayı")
    st.caption("Mağaza ve unvan bazında açıklanabilir karar desteği. Yönetim normunu veya transfer kararını otomatik değiştirmez.")
    path = Path(ctx.output_path) / "OMEHR_Magaza_Unvan_Isgucu_Tahmini.xlsx"
    c1,c2=st.columns([1,2])
    if c1.button("Tahmini şimdi hesapla", type="primary", use_container_width=True):
        from services.workforce_forecast import run
        with st.spinner("Operasyon, aktivite, kapasite ve kayıp verileri hesaplanıyor..."):
            result=run(ctx.sheets, ctx.output_path)
        if result.get("status")=="SUCCESS":
            st.success(f"Tahmin üretildi: {result.get('stores',0)} mağaza, {result.get('titles',0)} unvan.")
            st.rerun()
        else:
            st.error(f"Tahmin üretilemedi: {result.get('reason','Bilinmeyen hata')}")
    c2.info("Kullanılan girdiler: ciro/fiş/online eğilimi, aktivite iş yükü, standart süre, vardiya kapasitesi, fazla mesai, devamsızlık, izin, sezon-kampanya, özel gün ve turnover.")
    if not path.is_file():
        st.warning("Henüz tahmin raporu yok. 'Tahmini şimdi hesapla' düğmesini kullanın veya ana motoru çalıştırın.")
        return
    try:
        from services.cached_excel_reader import read_sheet_cached
        summary=read_sheet_cached(path,"Yönetici Özeti")
        detail=read_sheet_cached(path,"Mağaza_Unvan_Tahmini")
    except Exception as exc:
        st.error(f"Tahmin raporu okunamadı: {exc}")
        return
    horizon=st.radio("Tahmin ufku",[30,60,90],horizontal=True)
    view=detail[pd.to_numeric(detail["Tahmin Ufku Gün"],errors="coerce").eq(horizon)].copy()
    row=summary[pd.to_numeric(summary["Tahmin Ufku Gün"],errors="coerce").eq(horizon)]
    if not row.empty:
        r=row.iloc[0]; cols=st.columns(5)
        avg_conf=float(r['Ortalama Güven %'])
        cols[0].metric("Ham Tahmin Adayı",int(r["Tahmini Gerekli Kadro"]),help="Resmî norm değildir; veri kalitesi ve saha doğrulaması sonrası değerlendirilir.")
        cols[1].metric("Aktif Mevcut",int(r["Aktif Mevcut"]))
        cols[2].metric("Tahmini Açık",int(r["Toplam Tahmini Açık"]))
        cols[3].metric("Tahmini Fazla",int(r["Toplam Tahmini Fazla"]))
        cols[4].metric("Ortalama Güven",f"%{avg_conf:.1f}")
        if avg_conf < 60:
            st.error("Bu tahminin ortalama güveni %60 altında. Sayı yönetim kararı, işe alım veya transfer için yayımlanabilir sonuç değildir; yalnız ham senaryo adayıdır.")
    regions=[]
    if "Bölge" in view: regions=sorted(view["Bölge"].dropna().astype(str).unique())
    stores=sorted(view.get("Mağaza",pd.Series(dtype=str)).dropna().astype(str).unique())
    titles=sorted(view.get("Unvan",pd.Series(dtype=str)).dropna().astype(str).unique())
    f1,f2=st.columns(2)
    selected_stores=f1.multiselect("Mağaza filtresi",stores)
    selected_titles=f2.multiselect("Unvan filtresi",titles)
    if selected_stores: view=view[view["Mağaza"].astype(str).isin(selected_stores)]
    if selected_titles: view=view[view["Unvan"].astype(str).isin(selected_titles)]
    chart=(view.groupby("Mağaza",as_index=False)["Tahmini Açık/Fazla"].sum()
           .sort_values("Tahmini Açık/Fazla",ascending=False).head(20))
    if not chart.empty:
        fig=px.bar(chart,x="Tahmini Açık/Fazla",y="Mağaza",orientation="h",text="Tahmini Açık/Fazla",title=f"{horizon} Günlük Mağaza Bazında Tahmini Açık / Fazla")
        fig.update_traces(textposition="outside",cliponaxis=False)
        st.plotly_chart(fig,use_container_width=True)

    st.markdown("### Turnover Riski")
    st.caption("Yalnız gerçek gözleme dayalı (Yüksek/Orta/Düşük veri durumu) satırlar gösterilir; "
               "'Varsayılan' (gözlemsiz) kayıtlar asılsız alarm üretmesin diye hariç tutulur.")
    turnover_view = view[view.get("Turnover Veri Durumu", pd.Series(dtype=object)).isin(["Yüksek", "Orta", "Düşük"])].copy()
    if turnover_view.empty:
        st.info("Seçilen filtre için gözleme dayalı turnover riski verisi yok.")
    else:
        turnover_view["Turnover Riski FTE"] = pd.to_numeric(turnover_view.get("Turnover Riski FTE"), errors="coerce").fillna(0)
        turnover_chart = (turnover_view.groupby("Mağaza", as_index=False)["Turnover Riski FTE"].sum()
                           .sort_values("Turnover Riski FTE", ascending=False).head(20))
        if not turnover_chart.empty:
            fig2 = px.bar(turnover_chart, x="Turnover Riski FTE", y="Mağaza", orientation="h",
                          text="Turnover Riski FTE", title=f"{horizon} Günlük Mağaza Bazında Turnover Riski (FTE)")
            fig2.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False, marker_color="#d64545")
            st.plotly_chart(fig2, use_container_width=True)
        # Panelde gösterilen "eşik üstü" satırlar, mail uyarısını (services/
        # turnover_alert.py) tetikleyen AYNI eşik mantığıyla hesaplanır —
        # panel ile mail arasında tutarsızlık olmaması için threshold burada
        # tekrar yazılmaz, doğrudan aynı fonksiyon çağrılır.
        try:
            from services.turnover_alert import high_risk_rows
            alert_rows = high_risk_rows(Path(ctx.output_path))
            if not alert_rows.empty:
                alert_rows = alert_rows[pd.to_numeric(alert_rows.get("Tahmin Ufku Gün"), errors="coerce").eq(horizon)]
        except Exception:
            alert_rows = pd.DataFrame()
        if not alert_rows.empty:
            st.warning(f"{len(alert_rows)} mağaza-unvan kombinasyonu otomatik uyarı eşiğini aşıyor — İK/bölge sorumlularına mail kuyruklanır.")
            st.dataframe(alert_rows[["Mağaza", "Unvan", "Turnover Riski FTE", "Tahmin Güveni %", "Turnover Veri Durumu"]],
                         use_container_width=True, hide_index=True)
        else:
            st.caption("Bu ufuk için otomatik uyarı eşiğini aşan mağaza-unvan kombinasyonu yok.")

    st.markdown("### Açıklanabilir tahmin ayrıntısı")
    st.dataframe(view,use_container_width=True,hide_index=True,height=520,
                 column_config={"Karar Durumu":st.column_config.TextColumn(width="large"),"Takvim Açıklaması":st.column_config.TextColumn(width="medium")})

    st.markdown("### Tahmin doğrulaması")
    try:
        from services.cached_excel_reader import read_sheet_cached
        validation_summary=read_sheet_cached(path,"Operasyon_Backtest_Ozet")
    except Exception:
        validation_summary=pd.DataFrame()
    if validation_summary.empty:
        st.info("Operasyon backtest sonucu henüz oluşmadı. Tahmini yeniden hesaplayın.")
    elif "Durum" in validation_summary.columns:
        st.warning(str(validation_summary.iloc[0].get("Açıklama", "Backtest için veri yetersiz.")))
    else:
        overall=validation_summary[validation_summary.get("MağazaID",pd.Series(dtype=str)).astype(str).eq("TÜMÜ")].copy()
        if overall.empty: overall=validation_summary.copy()
        st.dataframe(overall,use_container_width=True,hide_index=True)
        st.caption("Bu tablo ciro/fiş/online operasyon tahminini doğrular; kadro tahmininin doğruluğunu doğrudan kanıtlamaz. Kadro için ayrı tarihsel snapshot backtesti gerekir.")
    try:
        from services.cached_excel_reader import read_sheet_cached
        kadro_validation=read_sheet_cached(path,"Kadro_Backtest_Ozet")
    except Exception:
        kadro_validation=pd.DataFrame()
    if not kadro_validation.empty:
        if "Durum" in kadro_validation.columns:
            st.info(str(kadro_validation.iloc[0].get("Açıklama", "Tarihsel kadro snapshot verisi yok.")))
        else:
            st.markdown("#### Mağaza–unvan kadro doğruluğu")
            st.dataframe(kadro_validation,use_container_width=True,hide_index=True,height=300)

    # Turnover ORANI tahmininin kendisinin doğruluğu — headcount_backtest
    # yalnız TOPLAM kadroyu ölçtüğü için turnover bileşeni ayrıca hiç
    # doğrulanmıyordu; bu bölüm doğrudan Fact_Mevcut'taki İşe Giriş/İşten
    # Çıkış tarihlerinden rolling-origin backtest ile üretilir (ek bir
    # geçmiş-snapshot sayfasına ihtiyaç DUYMAZ, bu yüzden Kadro Backtest'in
    # aksine üretimde fiilen çalışır).
    try:
        from services.cached_excel_reader import read_sheet_cached
        turnover_validation=read_sheet_cached(path,"Turnover_Backtest_Ozet")
    except Exception:
        turnover_validation=pd.DataFrame()
    if turnover_validation.empty:
        st.info("Turnover oranı backtest sonucu henüz oluşmadı. Tahmini yeniden hesaplayın.")
    elif "Durum" in turnover_validation.columns:
        st.info(str(turnover_validation.iloc[0].get("Açıklama", "Turnover backtest için veri yetersiz.")))
    else:
        st.markdown("#### Turnover oranı tahmin doğruluğu")
        st.caption("Geçmişteki bir tarihte (cutoff) o ana kadar bilinen veriyle tahmin edilen 90 günlük "
                   "turnover oranı, cutoff'tan SONRAKİ 90 günde GERÇEKTE gözlenen oranla karşılaştırılır.")
        overall_to=turnover_validation[turnover_validation.get("MağazaID",pd.Series(dtype=str)).astype(str).eq("TÜMÜ")].copy()
        if overall_to.empty: overall_to=turnover_validation.copy()
        st.dataframe(overall_to,use_container_width=True,hide_index=True)
        with st.expander("Mağaza-unvan bazında turnover backtest detayı"):
            st.dataframe(turnover_validation,use_container_width=True,hide_index=True,height=300)

    with open(path,"rb") as f:
        st.download_button("Tahmin Excel raporunu indir",f,file_name=path.name,mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    st.warning("Tahmin, resmî yönetim normunun yerine geçmez. Düşük güvenli satırlar saha zaman etüdü ve yönetici değerlendirmesi olmadan uygulanmamalıdır.")