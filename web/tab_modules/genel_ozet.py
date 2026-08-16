"""Genel Özet sekmesi.

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

import math
from web.geo_transfer import transfer_distance_map
from web.context import PageContext


def render(ctx: PageContext) -> None:
    """Genel Özet sekmesinin içeriğini çizer."""
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

    # KPI MUTABAKAT PANELİ - web/PDF/kılavuz aynı kavramları kullanır.
    aktif = int(kpis.get("Aktif Mevcut", 0))
    toplam_norm = int(kpis.get("Toplam Norm", 0))
    eksik = int(kpis.get("Norm Eksiği", 0))
    fazla = int(kpis.get("Norm Fazlası", 0))
    net_ihtiyac = int(kpis.get("Net İhtiyaç", fazla-eksik))
    try:
        kapsam_mevcut = int(pd.to_numeric(detail.get("Mevcut", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    except Exception:
        kapsam_mevcut = aktif
    kapsam_disi = max(0, aktif-kapsam_mevcut)
    brut_fark = aktif-toplam_norm
    mutabakat_farki = net_ihtiyac-brut_fark
    st.markdown("### KPI Mutabakat Paneli")
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Kapsam Dışı Personel", kapsam_disi)
    m2.metric("Brüt Fark (Mevcut-Norm)", brut_fark)
    m3.metric("Net İhtiyaç (Fazla-Eksik)", net_ihtiyac)
    m4.metric("Dağılım / Mutabakat Farkı", mutabakat_farki)
    st.caption("Brüt fark şirket toplamını; net ihtiyaç mağaza-unvan dağılımındaki eksik ve fazlaların netini gösterir. Bu iki değer farklı olabilir.")

    # NORM KARŞILAMA + TURNOVER YÖNETİM PANELİ
    st.markdown("### Norm Karşılama ve Turnover")
    norm_tab, turnover_tab = st.tabs(["Norm Karşılama", "Turnover"])

    with norm_tab:
        brut_oran = (aktif / toplam_norm * 100.0) if toplam_norm else 0.0
        dagilim_karsilanan = max(0, toplam_norm - eksik)
        dagilim_oran = (dagilim_karsilanan / toplam_norm * 100.0) if toplam_norm else 0.0
        n1, n2 = st.columns(2)
        for target, title, value, subtitle, color in [
            (n1, "Brüt Karşılama", brut_oran, f"{aktif} / {toplam_norm}", "#4472C4"),
            (n2, "Dağılım Bazlı Karşılama", dagilim_oran, f"{dagilim_karsilanan} / {toplam_norm}", "#70AD47"),
        ]:
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=value,
                number={"suffix":"%", "valueformat":".1f"},
                title={"text":f"{title}<br><span style='font-size:0.75em'>{subtitle}</span>"},
                gauge={
                    "axis":{"range":[0,110]}, "bar":{"color":color},
                    "steps":[{"range":[0,90],"color":"#FCE4D6"},{"range":[90,100],"color":"#FFF2CC"},{"range":[100,110],"color":"#E2F0D9"}],
                    "threshold":{"line":{"color":"#C00000","width":3},"value":100},
                },
            ))
            fig.update_layout(height=300, margin={"l":30,"r":30,"t":70,"b":20})
            target.plotly_chart(fig, use_container_width=True)
        st.caption(f"Norm Eksiği: {eksik} | Norm Fazlası: {fazla} | Net İhtiyaç: {net_ihtiyac}")

        branch_norm = stores.copy()
        for c in ["Mevcut","Norm","Eksik","Fazla"]:
            branch_norm[c] = pd.to_numeric(branch_norm.get(c,0), errors="coerce").fillna(0)
        branch_norm["Brüt Karşılama %"] = branch_norm.apply(lambda r: round(100*r["Mevcut"]/r["Norm"],1) if r["Norm"] else 0.0, axis=1)
        branch_norm["Dağılım Bazlı %"] = branch_norm.apply(lambda r: round(100*max(0,r["Norm"]-r["Eksik"])/r["Norm"],1) if r["Norm"] else 0.0, axis=1)
        branch_norm["Net Fark"] = branch_norm["Fazla"] - branch_norm["Eksik"]
        st.markdown("#### Şube Bazlı Norm Karşılama")
        show_cols=[c for c in ["Mağaza","Bölge Sorumlusu","Mevcut","Norm","Eksik","Fazla","Net Fark","Brüt Karşılama %","Dağılım Bazlı %"] if c in branch_norm.columns]
        st.dataframe(branch_norm[show_cols].sort_values(["Dağılım Bazlı %","Mağaza"]), use_container_width=True, hide_index=True)
        branch_options=sorted(branch_norm["Mağaza"].dropna().astype(str).unique().tolist())
        if branch_options:
            selected_branch=st.selectbox("Detayını görmek istediğiniz şube", branch_options, key="norm_branch_detail")
            row=branch_norm[branch_norm["Mağaza"].astype(str)==selected_branch].iloc[0]
            b1,b2,b3,b4=st.columns(4)
            b1.metric("Mevcut", int(row["Mevcut"]))
            b2.metric("Norm", int(row["Norm"]))
            b3.metric("Eksik / Fazla", f"{int(row['Eksik'])} / {int(row['Fazla'])}")
            b4.metric("Dağılım Bazlı", f"%{row['Dağılım Bazlı %']:.1f}")
            bd=detail[detail["Mağaza"].astype(str)==selected_branch].copy() if "Mağaza" in detail.columns else pd.DataFrame()
            if not bd.empty:
                st.dataframe(bd[[c for c in ["Unvan","Mevcut","Norm","Eksik","Fazla"] if c in bd.columns]], use_container_width=True, hide_index=True)

    with turnover_tab:
        work=fm.copy()
        entry_col=next((c for c in ["İşe Giriş","Ise Giris","İşe Giriş Tarihi"] if c in work.columns), None)
        exit_col=next((c for c in ["İşten Çıkış","Isten Cikis","İşten Çıkış Tarihi"] if c in work.columns), None)
        store_col=next((c for c in ["Mağaza","Magaza"] if c in work.columns), None)
        if not exit_col or not entry_col or not store_col:
            st.warning("Turnover hesaplamak için Fact_Mevcut içinde Mağaza, İşe Giriş ve İşten Çıkış sütunları gereklidir.")
        else:
            work[entry_col]=pd.to_datetime(work[entry_col], errors="coerce")
            work[exit_col]=pd.to_datetime(work[exit_col], errors="coerce")
            today=pd.Timestamp.today().normalize()
            default_start=today-pd.DateOffset(months=12)
            td1,td2=st.columns(2)
            start=td1.date_input("Dönem başlangıcı", value=default_start.date(), key="turnover_start")
            end=td2.date_input("Dönem sonu", value=today.date(), key="turnover_end")
            start_ts,end_ts=pd.Timestamp(start),pd.Timestamp(end)+pd.Timedelta(days=1)-pd.Timedelta(seconds=1)
            exits=work[work[exit_col].between(start_ts,end_ts, inclusive="both")].copy()
            entries=work[work[entry_col].between(start_ts,end_ts, inclusive="both")].copy()
            active_end=int(work[exit_col].isna().sum())
            start_hc=max(0, active_end-len(entries)+len(exits))
            avg_hc=(start_hc+active_end)/2 if (start_hc+active_end)>0 else 0
            turnover=(len(exits)/avg_hc*100) if avg_hc else 0.0
            early=exits[(exits[entry_col].notna()) & ((exits[exit_col]-exits[entry_col]).dt.days<=90)]
            early_share=(len(early)/len(exits)*100) if len(exits) else 0.0
            t1,t2=st.columns(2)
            t1.metric("Dönemsel Turnover", f"%{turnover:.1f}", help="İşten ayrılan / ortalama çalışan sayısı")
            t2.metric("İlk 90 Gün Ayrılış Payı", f"%{early_share:.1f}", help="İlk 90 günde ayrılanların toplam ayrılış içindeki payı")
            st.caption(f"Giriş: {len(entries)} | Çıkış: {len(exits)} | Dönem sonu aktif: {active_end} | Tahmini dönem başı mevcut: {start_hc}")

            all_stores=sorted(work[store_col].dropna().astype(str).unique().tolist())
            rows=[]
            for mag in all_stores:
                w=work[work[store_col].astype(str)==mag]
                x=w[w[exit_col].between(start_ts,end_ts, inclusive="both")]
                e=w[w[entry_col].between(start_ts,end_ts, inclusive="both")]
                ae=int(w[exit_col].isna().sum())
                sh=max(0,ae-len(e)+len(x)); av=(sh+ae)/2 if (sh+ae)>0 else 0
                er=x[(x[entry_col].notna()) & ((x[exit_col]-x[entry_col]).dt.days<=90)]
                rows.append({"Mağaza":mag,"Giriş":len(e),"Çıkış":len(x),"Aktif":ae,"Turnover %":round(100*len(x)/av,1) if av else 0.0,"İlk 90 Gün Çıkış":len(er)})
            turnover_df=pd.DataFrame(rows).sort_values(["Turnover %","Mağaza"], ascending=[False,True])
            st.markdown("#### Şube Bazlı Turnover")
            st.dataframe(turnover_df, use_container_width=True, hide_index=True)
            if all_stores:
                turnover_branch=st.selectbox("Turnover detayını görmek istediğiniz şube", all_stores, key="turnover_branch_detail")
                tr=turnover_df[turnover_df["Mağaza"]==turnover_branch].iloc[0]
                q1,q2,q3,q4=st.columns(4)
                q1.metric("Giriş", int(tr["Giriş"]))
                q2.metric("Çıkış", int(tr["Çıkış"]))
                q3.metric("Turnover", f"%{tr['Turnover %']:.1f}")
                q4.metric("İlk 90 Gün Çıkış", int(tr["İlk 90 Gün Çıkış"]))
            if len(exits)==0:
                st.info("Seçilen dönemde İşten Çıkış tarihi bulunan kayıt yok. Turnover oranı bu nedenle %0 görünür; geçmişten ayrılan personel satırları Fact_Mevcut içinde korunmalıdır.")

    a,b=st.columns(2)
    region_summary=stores.groupby("Bölge Sorumlusu")[["Mevcut","Norm","Eksik","Fazla"]].sum().reset_index()
    region_fig=px.bar(region_summary,x="Bölge Sorumlusu",y=["Eksik","Fazla"],barmode="group",
                      text_auto=True,title="Bölge Bazlı Norm Eksiği / Fazlası")
    region_fig.update_traces(textfont_size=16,textposition="outside",cliponaxis=False)
    a.plotly_chart(region_fig,use_container_width=True)
    coverage=kpis["Aktif Mevcut"]/kpis["Toplam Norm"]*100
    coverage_fig=go.Figure(go.Indicator(
        mode='gauge+number',value=coverage,number={'suffix':'%','valueformat':'.1f'},
        title={'text':'Norm Karşılama Oranı'},
        gauge={
            'axis':{'range':[0,max(110,math.ceil(coverage/10)*10)]},
            'bar':{'color':'#4472C4'},
            'steps':[{'range':[0,100],'color':'#E8F1FA'},{'range':[100,max(110,math.ceil(coverage/10)*10)],'color':'#FCE4D6'}],
            'threshold':{'line':{'color':'#118B94','width':4},'value':100},
        },
    ))
    coverage_fig.update_layout(margin={'l':35,'r':35,'t':60,'b':20},height=380)
    b.plotly_chart(coverage_fig,use_container_width=True)
    c,d=st.columns(2)
    risk=stores.copy()
    risk=risk.dropna(subset=["Bölge Sorumlusu","Mağaza"]).copy()
    risk=risk[(risk["Bölge Sorumlusu"].astype(str).str.strip()!="") & (risk["Mağaza"].astype(str).str.strip()!="")]
    risk=risk[risk["Eksik"]>0].copy()
    risk["Kök"]="OMEHR"
    if not risk.empty:
        fig=px.treemap(
            risk,path=["Kök","Bölge Sorumlusu","Mağaza"],values="Eksik",
            color="Eksik",hover_data={"Eksik":True},
            title="Mağaza Risk Ağaç Haritası"
        )
        fig.update_traces(
            root_color="#102F64",
            texttemplate="<b>%{label}</b><br>Norm Eksiği: %{value:.0f}",
            hovertemplate="<b>%{label}</b><br>Norm Eksiği: %{value:.0f}<extra></extra>",
        )
        c.plotly_chart(fig,use_container_width=True)
    else:
        c.info("Risk haritası için geçerli mağaza kaydı bulunamadı.")
    title_summary=detail.groupby("Unvan")[["Eksik","Fazla"]].sum().reset_index().sort_values("Eksik",ascending=False).head(20)
    title_fig=px.bar(title_summary,x="Eksik",y="Unvan",orientation="h",text_auto=True,title="Unvan Bazlı En Yüksek Açıklar")
    title_fig.update_traces(textfont_size=15,textposition="outside",cliponaxis=False)
    d.plotly_chart(title_fig,use_container_width=True)
    e,f=st.columns(2)
    scatter_fig=px.scatter(
        stores,x="Norm",y="Mevcut",size="Eksik",hover_name="Mağaza",
        hover_data={"Bölge Sorumlusu":True,"Norm":True,"Mevcut":True,"Eksik":True,"Fazla":True},
        title="Mevcut - Norm Saçılımı"
    )
    e.plotly_chart(scatter_fig,use_container_width=True)
    heat=detail.pivot_table(index="Bölge Sorumlusu",columns="Unvan",values="Eksik",aggfunc="sum",fill_value=0)
    heat=heat.loc[:,(heat!=0).any(axis=0)]  # tamamen sıfır olan unvan sütunlarını at (aşırı geniş/ince hücre sorununu önler)
    if not heat.empty:
        heat_fig=px.imshow(heat,aspect="auto",text_auto=True,title="Norm Eksiği Isı Haritası")
        heat_fig.update_traces(textfont_size=13)
        # Hücrelerin sütun-şeklinde (çok ince/uzun) görünmesini önlemek için yükseklik
        # HEM satır HEM sütun sayısına göre ayarlanır — az satır + çok sütun durumunda
        # (Bölge Sorumlusu az, Unvan çok) önceden yükseklik sadece satırdan hesaplanınca
        # hücreler aşırı ince kalıyordu.
        heat_fig.update_layout(height=max(420,55*len(heat.index)+120),font=dict(size=13))
        st.plotly_chart(heat_fig,use_container_width=True)
    surplus_heat=detail.pivot_table(index="Bölge Sorumlusu",columns="Unvan",values="Fazla",aggfunc="sum",fill_value=0)
    surplus_heat=surplus_heat.loc[:,(surplus_heat!=0).any(axis=0)]
    if not surplus_heat.empty:
        surplus_fig=px.imshow(surplus_heat,aspect="auto",text_auto=True,color_continuous_scale="Oranges",title="Norm Fazlası Isı Haritası")
        surplus_fig.update_traces(textfont_size=13)
        surplus_fig.update_layout(height=max(420,55*len(surplus_heat.index)+120),font=dict(size=13))
        st.plotly_chart(surplus_fig,use_container_width=True)
    transfer_map=transfer_distance_map(fm,detail,sheets)
    if transfer_map is not None:
        st.plotly_chart(transfer_map,use_container_width=True)
    else:
        st.info("Transfer haritası için koordinatlı uygun personel eşleşmesi bulunamadı (mağaza/ev koordinatları eksik olabilir).")
