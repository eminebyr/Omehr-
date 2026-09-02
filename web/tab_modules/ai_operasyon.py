"""AI Operasyon & Verimlilik sekmesi.

Bu modül, web/app.py içindeki eski "with tabs[N]:" bloğundan otomatik
olarak çıkarılmıştır. Kod davranışı değiştirilmeden taşınmıştır; tüm
paylaşılan durum (sheets, kullanıcı/rol bilgisi, fm/detail/stores/kpis,
servis fonksiyonları) web.context.PageContext üzerinden gelir.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from services.cached_excel_reader import read_sheet_cached
import plotly.express as px
import plotly.graph_objects as go

from web.context import PageContext
from services.safe_exec import log_swallowed


def render(ctx: PageContext) -> None:
    """AI Operasyon & Verimlilik sekmesinin içeriğini çizer."""
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

    st.subheader("AI Operasyon, Verimlilik ve Norm Karar Desteği")
    ai_path=OUTPUT/"V19_AI_Norm_Sonuclari.xlsx"
    analytics_path=OUTPUT/"V19_Istatistik_ML_Operasyon_Analizi.xlsx"
    if not ai_path.is_file():
        st.info("AI analizi için önce Tüm tabloları şimdi yenile düğmesini çalıştırın.")
    else:
        ai_view=read_sheet_cached(ai_path, "AI_Norm_Sonuclari")
        if not is_global:
            ai_view=ai_view[ai_view["Bölge"].astype(str).map(norm_text).eq(norm_text(scope))]
        confidence_values=pd.to_numeric(ai_view["Güven Skoru"],errors="coerce").dropna()
        model_r2=None
        if analytics_path.is_file():
            try:
                model_scores=read_sheet_cached(analytics_path, "Model_Karsilastirma")
                if not model_scores.empty and "CV R²" in model_scores:
                    model_r2=float(pd.to_numeric(model_scores["CV R²"],errors="coerce").max())
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                model_r2=None
        ai_fark = pd.to_numeric(ai_view["AI-Mevcut Fark"], errors="coerce").fillna(0)
        ai_toplam_norm = pd.to_numeric(ai_view["AI Önerilen Norm"], errors="coerce").fillna(0).sum()
        ai_brut_acik = ai_fark.clip(lower=0).sum()
        ai_brut_fazla = (-ai_fark.clip(upper=0)).sum()
        ai_net_fark = ai_brut_acik - ai_brut_fazla
        k1,k2,k3,k4,k5,k6=st.columns(6)
        k1.metric("AI Önerilen Toplam Norm",tr_number(ai_toplam_norm))
        k2.metric("AI Brüt Açık",tr_number(ai_brut_acik),help="AI önerisinin mevcuttan yüksek olduğu mağaza–unvan satırlarındaki pozitif farkların toplamı.")
        k3.metric("AI Brüt Fazla",tr_number(ai_brut_fazla),help="Mevcudun AI önerisinden yüksek olduğu satırlardaki fazlaların toplamı.")
        k4.metric("AI Net Fark",f"{tr_number(abs(ai_net_fark))} kişi {'açık' if ai_net_fark>0 else ('fazla' if ai_net_fark<0 else 'dengede')}")
        k5.metric("Ortalama Veri Güveni",("Hesaplanmadı" if confidence_values.empty else f"%{tr_number(confidence_values.mean(),1)}"))
        k6.metric("En İyi Model CV R²",("Hesaplanmadı" if model_r2 is None else f"%{tr_number(100*model_r2,1)}"))
        st.caption("AI brüt açık ve brüt fazla dağılımı gösterir; net fark = brüt açık − brüt fazla. Bu değerler resmî normu otomatik değiştirmez.")
        left,right=st.columns(2)
        store_ai=ai_view.groupby("Mağaza",as_index=False).agg(
            **{"Aktif Mevcut":("Aktif Mevcut","sum"),"Yönetim Normu":("Yönetim Normu","sum"),"AI Önerilen Norm":("AI Önerilen Norm","sum")}
        ).sort_values("AI Önerilen Norm",ascending=False).head(15)
        compare=px.bar(
            store_ai.melt(id_vars="Mağaza",value_vars=["Aktif Mevcut","Yönetim Normu","AI Önerilen Norm"],var_name="Gösterge",value_name="Kişi"),
            x="Kişi",y="Mağaza",color="Gösterge",orientation="h",barmode="group",text="Kişi",
            color_discrete_map={"Aktif Mevcut":"#102F64","Yönetim Normu":"#118B94","AI Önerilen Norm":"#4472C4"},
            title="Mağaza Bazında Mevcut, Yönetim Normu ve AI Önerisi"
        )
        compare.update_traces(textposition="outside",cliponaxis=False)
        left.plotly_chart(compare,use_container_width=True)
        title_ai=ai_view.groupby("Unvan",as_index=False)["AI-Mevcut Fark"].sum()
        title_ai=title_ai.reindex(title_ai["AI-Mevcut Fark"].abs().sort_values(ascending=False).index).head(15)
        title_chart=px.bar(
            title_ai,x="AI-Mevcut Fark",y="Unvan",orientation="h",text="AI-Mevcut Fark",
            color="AI-Mevcut Fark",color_continuous_scale=["#70AD47","#F2F2F2","#4472C4"],
            title="Unvan Bazında AI Kapasite Açığı / Fazlası"
        )
        title_chart.update_traces(textposition="outside",cliponaxis=False)
        right.plotly_chart(title_chart,use_container_width=True)
        biggest_store=store_ai.assign(
            fark=store_ai["AI Önerilen Norm"]-store_ai["Aktif Mevcut"]
        ).sort_values("fark",ascending=False).iloc[0]
        biggest_title=title_ai.sort_values("AI-Mevcut Fark",ascending=False).iloc[0]
        st.info(
            f"Akıllı yorum: AI modelinde en yüksek mağaza kapasite ihtiyacı "
            f"{biggest_store['Mağaza']} için {tr_number(biggest_store['fark'])} kişi; "
            f"unvan bazında en yüksek toplam açık {biggest_title['Unvan']} için "
            f"{tr_number(biggest_title['AI-Mevcut Fark'])} kişi görünüyor. "
            "Bu değerler yönetim normunu değiştirmez; iş yükü ve saha etüdüyle doğrulanmalıdır."
        )
        low_confidence_count=int(pd.to_numeric(ai_view["Güven Skoru"],errors="coerce").lt(50).sum())
        if low_confidence_count:
            st.warning(
                f"{tr_number(low_confidence_count)} mağaza/unvan kaydında veri güveni %50'nin altında. "
                "Bu mağazalarda veri kalitesi düşük; AI önerisi dikkatli kullanılmalı ve saha zaman etüdüyle doğrulanmalıdır."
            )
        ai_display_columns=[
            "Bölge","Mağaza","Unvan","Aktif Mevcut","Yönetim Normu",
            "AI Ham İş Yükü Normu","AI Önerilen Norm","AI-Mevcut Fark","Güven Skoru",
            "Veri Kalitesi Uyarısı","Önerilen Aksiyon",
        ]
        ai_display_columns=[column for column in ai_display_columns if column in ai_view.columns]
        ai_sort_columns=[column for column in ["Öncelik Seviyesi","AI-Mevcut Fark"] if column in ai_view.columns]
        ai_sorted=ai_view.sort_values(
            ai_sort_columns,
            ascending=[True if column=="Öncelik Seviyesi" else False for column in ai_sort_columns],
        ) if ai_sort_columns else ai_view
        if not ai_sorted.empty and "Yönetici Açıklaması" in ai_sorted.columns:
            # NOT: pandas index label'larına güvenilmez (AI_Norm_Sonuclari raporunda
            # aynı index'in birden fazla satırda tekrarlanması ya da filtre/sort
            # sonrası index'in düzensiz kalması, seçim kutusunda ne seçilirse
            # seçilsin hep AYNI (genelde ilk/AKEVLER-BAKLİYAT) satırın gösterilmesine
            # yol açıyordu. Bunun yerine sıfırlanmış, garantili benzersiz satır
            # POZİSYONU (.iloc) kullanılır. Ayrıca Mağaza/Unvan bilgisi boş olan
            # (rapor motorundan gelen geçersiz/artık) satırlar listeden çıkarılır.
            ai_valid = ai_sorted[
                ai_sorted["Mağaza"].notna() & ai_sorted["Unvan"].notna()
            ]
            ai_reset = ai_valid.reset_index(drop=True)
            label_counts: dict[str, int] = {}
            explanation_options: dict[str, int] = {}
            for position, row in ai_reset.iterrows():
                base_label = f"{row.get('Mağaza','')} | {row.get('Unvan','')}"
                label_counts[base_label] = label_counts.get(base_label, 0) + 1
                label = base_label if label_counts[base_label] == 1 else f"{base_label} ({label_counts[base_label]})"
                explanation_options[label] = position
            selected_explanation=st.selectbox(
                "Yönetici açıklamasını tam görüntüle",
                list(explanation_options),
                key="ai_full_explanation",
            )
            selected_row=ai_reset.iloc[explanation_options[selected_explanation]]
            st.markdown(
                f"### {selected_row.get('Mağaza','')} / {selected_row.get('Unvan','')} — Tam AI Karar Açıklaması"
            )
            st.text_area(
                "Önerilen aksiyon",
                value=str(selected_row.get("Önerilen Aksiyon","")),
                height=80,
                disabled=True,
                key=f"ai_selected_action_{explanation_options[selected_explanation]}",
            )
            st.text_area(
                "Yönetici açıklaması",
                value=str(selected_row.get("Yönetici Açıklaması","")),
                height=140,
                disabled=True,
                key=f"ai_selected_explanation_{explanation_options[selected_explanation]}",
            )
        st.dataframe(
            ai_sorted[ai_display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Önerilen Aksiyon":st.column_config.TextColumn("Önerilen Aksiyon",width="large"),
            },
        )
        executive_path=OUTPUT/"OMEHR_Executive_Data.xlsx"
        if executive_path.is_file():
            st.markdown("### Operasyon Analizi")
            try:
                operation_view=read_sheet_cached(executive_path, "Yönetici Operasyonel Analiz")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                operation_view=pd.DataFrame()
            if not operation_view.empty:
                op_numeric=[c for c in ["Aylık Fiş","Aylık Ciro","Online Sipariş","Mal Kabul","İş Yükü Endeksi"] if c in operation_view]
                op_metric=st.columns(max(1,min(4,len(op_numeric))))
                for column,box in zip(op_numeric[:4],op_metric):
                    box.metric(column,tr_number(pd.to_numeric(operation_view[column],errors="coerce").fillna(0).sum()))
                if "Aylık Ciro" in operation_view:
                    op_chart=operation_view.nlargest(15,"Aylık Ciro")
                    st.plotly_chart(px.bar(op_chart,x="Aylık Ciro",y="Mağaza",orientation="h",text_auto=".3s",title="Mağaza Bazında Aylık Ciro"),use_container_width=True)
                st.dataframe(operation_view,use_container_width=True,hide_index=True)
            else:
                st.warning("Operasyon analizi henüz üretilmedi. Tüm tabloları şimdi yenileyin.")

            st.markdown("### Maliyet ve Verimlilik Analizi")
            try:
                financial_view=read_sheet_cached(executive_path, "Yönetici Finansal Analiz")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                financial_view=pd.DataFrame()
            if not financial_view.empty:
                available_units=[u for u in ["Mağaza","Depo","Merkez"] if u in set(financial_view.get("Birim Tipi",pd.Series(dtype=str)).dropna())]
                selected_unit=st.radio(
                    "Karşılaştırma grubu",
                    available_units or ["Tümü"],
                    horizontal=True,
                    key="financial_unit_group",
                )
                group_view=financial_view if selected_unit=="Tümü" else financial_view[financial_view["Birim Tipi"].eq(selected_unit)].copy()
                total_revenue=pd.to_numeric(group_view.get("Aylık Ciro",0),errors="coerce").fillna(0).sum()
                total_cost=pd.to_numeric(group_view.get("Toplam İş Gücü Maliyeti",0),errors="coerce").fillna(0).sum()
                cost_ratio=total_cost/total_revenue*100 if total_revenue else 0
                c1,c2,c3=st.columns(3)
                c1.metric("Toplam Aylık Ciro",tr_money_compact(total_revenue))
                c2.metric("Toplam İş Gücü Maliyeti",tr_money_compact(total_cost))
                c3.metric("İş Gücü Maliyeti / Ciro",f"%{tr_number(cost_ratio,2)}")
                financial_chart=group_view.nlargest(15,"Aylık Ciro")
                finance_long=financial_chart.melt(
                    id_vars="Mağaza",value_vars=["Aylık Ciro","Toplam İş Gücü Maliyeti"],
                    var_name="Gösterge",value_name="TL"
                )
                st.plotly_chart(px.bar(finance_long,x="TL",y="Mağaza",color="Gösterge",orientation="h",barmode="group",title=f"{selected_unit} Grubunda Ciro ve İş Gücü Maliyeti"),use_container_width=True)
                top_financial=group_view.nlargest(1,"Aylık Ciro").iloc[0]
                st.info(
                    f"Akıllı yorum: En yüksek aylık ciro {top_financial['Mağaza']} mağazasında "
                    f"{tr_number(top_financial['Aylık Ciro'],suffix=' TL')} olarak görülüyor. "
                    "İş gücü maliyeti/ciro oranı mağaza tipi ve gelir yapısıyla birlikte değerlendirilmelidir."
                )
                st.caption("Merkez, depo ve mağaza satırları farklı iş modelleri nedeniyle yalnız kendi grubu içinde karşılaştırılır.")
                st.dataframe(group_view,use_container_width=True,hide_index=True)
            else:
                st.warning("Maliyet analizi henüz üretilmedi. Tüm tabloları şimdi yenileyin.")

        if analytics_path.is_file():
            st.markdown("### Model Performansı ve İstatistiksel Testler")
            try:
                model_comparison=read_sheet_cached(analytics_path, "Model_Karsilastirma")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                model_comparison=pd.DataFrame()
            try:
                class_metrics=read_sheet_cached(analytics_path, "Siniflandirma_Metrikleri")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                class_metrics=pd.DataFrame()
            try:
                lifecycle=read_sheet_cached(analytics_path, "Model_Yasam_Dongusu")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: model yaşam döngüsü okunamadı", _exc)
                lifecycle=pd.DataFrame()
            try:
                test_results=read_sheet_cached(analytics_path, "Hipotez_Testleri")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                test_results=pd.DataFrame()

            # Bazı veri setlerinde tek dönemli model sayfası bilinçli olarak boş
            # kalabilir. Bu durumda GroupKFold derin karşılaştırma çıktısını kullan.
            deep_path=OUTPUT/"V19_1_Derin_Model_Karsilastirmasi.xlsx"
            if model_comparison.empty and deep_path.is_file():
                try:
                    model_comparison=read_sheet_cached(deep_path, "Regresyon_Model_Karsilastirma")
                except Exception as _exc:
                    log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                    model_comparison=pd.DataFrame()
            mae_column=next(
                (
                    column for column in
                    ["CV MAE","GroupKFold MAE","MAE","Test MAE"]
                    if column in model_comparison.columns
                ),
                None,
            )

            class_chart=class_metrics.copy()
            if {"Metrik","Değer"}.issubset(class_chart.columns):
                class_chart["Değer"]=pd.to_numeric(class_chart["Değer"],errors="coerce")
                class_chart=class_chart.dropna(subset=["Değer"])
            else:
                class_chart=pd.DataFrame()
            lifecycle_map={}
            if {"Gösterge","Değer"}.issubset(lifecycle.columns):
                lifecycle_map=dict(zip(lifecycle["Gösterge"].astype(str),lifecycle["Değer"]))
                stage=lifecycle_map.get("Model yaşam evresi","Belirlenemedi")
                release=lifecycle_map.get("Üretim yayını","Kapalı")
                days=lifecycle_map.get("Benzersiz gerçek veri günü",0)
                message=(
                    f"Model yaşam evresi: **{stage}** · gerçek veri günü: **{days}** · "
                    f"üretim yayını: **{release}**. Mağaza bazlı CV, zamansal backtest yerine geçmez."
                )
                if str(release).casefold()=="açık":
                    st.success(message)
                else:
                    st.warning(message)
            m1,m2=st.columns(2)
            if mae_column and "Model" in model_comparison.columns:
                regression_chart=model_comparison[["Model",mae_column]].copy()
                regression_chart[mae_column]=pd.to_numeric(
                    regression_chart[mae_column],errors="coerce"
                )
                regression_chart=regression_chart.dropna(subset=[mae_column])
                if not regression_chart.empty:
                    m1.plotly_chart(
                        px.bar(
                            regression_chart.sort_values(mae_column,ascending=True),
                            x=mae_column,y="Model",orientation="h",text_auto=".3f",
                            title="Model Karşılaştırması — Düşük MAE Daha İyi",
                        ),
                        use_container_width=True,
                    )
                else:
                    m1.info("Regresyon modeli performans değeri henüz oluşmadı.")
            else:
                m1.info("Model karşılaştırması henüz oluşmadı; rapor motorunu yenileyin.")
            if not class_chart.empty:
                m2.plotly_chart(
                    px.bar(
                        class_chart,x="Metrik",y="Değer",text_auto=".3f",
                        range_y=[0,1],title="Sınıflandırma Modeli Performansı",
                    ),
                    use_container_width=True,
                )
            else:
                m2.info(
                    "Sınıflandırma bilinçli olarak çalıştırılmadı. AI-Mevcut Fark bağımsız hedef değildir; "
                    "sonradan gerçekleşen/onaylanan kadro ihtiyacı etiketi birikince Precision, Recall ve F1 yayımlanacaktır."
                )
            with st.expander("İstatistiksel testler ve model metodolojisi"):
                if not test_results.empty:
                    st.dataframe(test_results,use_container_width=True,hide_index=True)
                else:
                    st.info("İstatistiksel test sonuçları henüz oluşmadı.")
                if not lifecycle.empty:
                    st.markdown("**Model yaşam döngüsü ve yayın kapıları**")
                    st.dataframe(lifecycle,use_container_width=True,hide_index=True)
                st.caption("AI önerisi karar desteğidir; resmî KPI ve yönetim normunu otomatik değiştirmez. Dummy işaretli veriler saha zaman etüdüyle güncellenmelidir.")

            st.markdown("---")
            st.markdown("#### En İyi Modele Dayalı Öneri Sistemi")
            st.caption(
                "Yukarıdaki karşılaştırmada en düşük hatayı veren model (aşağıda adı gösterilir), "
                "her mağaza/unvan için mağaza-dışı GroupKFold tahmini üretir. Bu karşılaştırma model geliştirme "
                "kanıtıdır; üretim kadro önerisi ayrıca zamansal backtest ve veri olgunluk kapısını geçmelidir."
            )
            en_iyi_model_adi=None
            if mae_column and "Model" in model_comparison.columns and not model_comparison.empty:
                gecerli=model_comparison.copy()
                gecerli[mae_column]=pd.to_numeric(gecerli[mae_column],errors="coerce")
                gecerli=gecerli.dropna(subset=[mae_column])
                gecerli=gecerli[~gecerli["Model"].astype(str).str.contains("Naif",case=False,na=False)]
                if not gecerli.empty:
                    en_iyi_model_adi=gecerli.sort_values(mae_column).iloc[0]["Model"]
            try:
                tahmin_detay=read_sheet_cached(deep_path, "Grup_Disi_Tahminler")
            except Exception as _exc:
                log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                tahmin_detay=pd.DataFrame()
            if en_iyi_model_adi and not tahmin_detay.empty and "Grup-Dışı Tahmin" in tahmin_detay.columns:
                st.success(f"En iyi model: **{en_iyi_model_adi}** (MAE={tr_number(gecerli[mae_column].min(),3)}) — öneriler bu modelin tahminlerine dayanıyor.")
                if "Aşırı Öğrenme Durumu" in model_comparison.columns:
                    _asiri_ogrenme_satir = model_comparison[model_comparison["Model"] == en_iyi_model_adi]
                    if not _asiri_ogrenme_satir.empty:
                        _durum = _asiri_ogrenme_satir.iloc[0].get("Aşırı Öğrenme Durumu")
                        _r2_farki = _asiri_ogrenme_satir.iloc[0].get("R² Farkı (Eğitim-CV)")
                        if _durum and "YÜKSEK" in str(_durum):
                            st.error(f"🚫 Aşırı öğrenme kontrolü: **{_durum}** (Eğitim R² ile mağaza-dışı R² farkı: {tr_number(_r2_farki,3) if pd.notna(_r2_farki) else '-'}) — bu modele temkinli yaklaşılmalı.")
                        elif _durum and "ORTA" in str(_durum):
                            st.warning(f"⚠️ Aşırı öğrenme kontrolü: **{_durum}** (fark: {tr_number(_r2_farki,3) if pd.notna(_r2_farki) else '-'})")
                        elif _durum:
                            st.caption(f"✅ Aşırı öğrenme kontrolü: {_durum} (eğitim ile mağaza-dışı doğrulama skoru farkı: {tr_number(_r2_farki,3) if pd.notna(_r2_farki) else '-'}) — model gerçekten genelliyor, ezberlemiyor.")
                oneri=tahmin_detay.copy()
                oneri["Fark (Tahmin-Gerçek)"]=oneri["Grup-Dışı Tahmin"]-oneri["İş Yükü FTE"]
                oneri_kritik=oneri[oneri["Fark (Tahmin-Gerçek)"]>0.3].sort_values("Fark (Tahmin-Gerçek)",ascending=False).head(20)
                if not oneri_kritik.empty:
                    st.markdown("**Modelin, gerçek norm üzerinde ek FTE ihtiyacı öngördüğü ilk 20 kayıt:**")
                    goster_kolonlar=[c for c in ["Bölge","Mağaza","Unvan","İş Yükü FTE","Grup-Dışı Tahmin","Fark (Tahmin-Gerçek)"] if c in oneri_kritik.columns]
                    st.dataframe(oneri_kritik[goster_kolonlar],use_container_width=True,hide_index=True)
                else:
                    st.info("Modelin gerçek normdan belirgin şekilde farklı tahmin ürettiği kayıt bulunamadı — model mevcut normla uyumlu.")
                try:
                    onem=read_sheet_cached(deep_path, "Degisken_Onemi")
                    if not onem.empty and {"Değişken","Permütasyon Önemi"}.issubset(onem.columns):
                        with st.expander(f"{en_iyi_model_adi} — Hangi değişkenler tahmine en çok etki ediyor?"):
                            onem_fig=px.bar(
                                onem.sort_values("Permütasyon Önemi",ascending=True).tail(12),
                                x="Permütasyon Önemi",y="Değişken",orientation="h",
                                title="Değişken Önemi (Permütasyon)",
                            )
                            st.plotly_chart(onem_fig,use_container_width=True)
                except Exception as _exc:
                    log_swallowed("web.tab_modules.ai_operasyon.render: beklenmeyen hata", _exc)
                    pass
            else:
                st.info("En iyi model tahmin detayları henüz oluşmadı; derin model karşılaştırma raporunu (model_benchmark.py) çalıştırın.")
