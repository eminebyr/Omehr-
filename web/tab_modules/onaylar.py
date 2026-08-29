"""Onaylar sekmesi.

Bu modül, web/app.py içindeki eski "with tabs[N]:" bloğundan otomatik
olarak çıkarılmıştır. Kod davranışı değiştirilmeden taşınmıştır; tüm
paylaşılan durum (sheets, kullanıcı/rol bilgisi, fm/detail/stores/kpis,
servis fonksiyonları) web.context.PageContext üzerinden gelir.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import time

from datetime import date, datetime

from web.context import PageContext
from web.transfer_email import transfer_bilgi_govdesi as _transfer_bilgi_govdesi


def render(ctx: PageContext) -> None:
    """Onaylar sekmesinin içeriğini çizer."""
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

    st.subheader("Bölge ve İK Onayları")
    con=db(); all_pending=pd.read_sql_query("SELECT * FROM transfers ORDER BY id DESC",con); con.close()
    if not is_global: all_pending=all_pending[(all_pending["region"].astype(str).map(norm_text)==norm_text(scope))|(all_pending["target_region"].astype(str).map(norm_text)==norm_text(scope))]
    st.dataframe(all_pending,use_container_width=True,hide_index=True)
    if role=="REGION":
        rp=all_pending[all_pending["status"].eq("Bölge Müdürleri Onayı Bekliyor")]
        if not rp.empty:
            rid=st.selectbox("Talep",rp["id"].tolist(),key="rid"); dec=st.selectbox("Bölge kararı",["Onayladı","Reddetti"])
            if st.button("Bölge kararını kaydet"):
                con=db(); con.row_factory=sqlite3.Row; row=dict(con.execute("SELECT * FROM transfers WHERE id=?",(int(rid),)).fetchone()); now=datetime.now().isoformat(timespec="seconds")
                if norm_text(scope)==norm_text(row.get("region")): con.execute("UPDATE transfers SET source_region_decision=?,source_region_decision_by=?,source_region_decision_at=? WHERE id=?",(dec,username,now,int(rid)))
                if norm_text(scope)==norm_text(row.get("target_region")): con.execute("UPDATE transfers SET target_region_decision=?,target_region_decision_by=?,target_region_decision_at=? WHERE id=?",(dec,username,now,int(rid)))
                con.commit(); row=dict(con.execute("SELECT * FROM transfers WHERE id=?",(int(rid),)).fetchone()); same=norm_text(row.get("region"))==norm_text(row.get("target_region")); new="Bölge Müdürü Reddetti" if dec=="Reddetti" else ("İK Onayı Bekliyor" if row.get("source_region_decision")=="Onayladı" and (same or row.get("target_region_decision")=="Onayladı") else "Bölge Müdürleri Onayı Bekliyor"); con.execute("UPDATE transfers SET status=?,updated_at=? WHERE id=?",(new,now,int(rid))); con.commit(); con.close()
                recipients=transfer_recipients(acc,row,sheets)
                _govde=_transfer_bilgi_govdesi(row,f"Bölge kararı: {dec}",f"Kararı veren: {username} | Yeni durum: {new}")
                _job_id,_ok,_err=_enqueue_and_process("SEND_EMAIL",{"subject":f"Transfer Talebi #{rid}: Bölge Kararı {dec}","body":_govde,"recipients":recipients,"transfer_id":int(rid)},tenant_code())
                if _ok is False:
                    st.error(f"⚠️ E-posta gönderilemedi: {_err}")
                elif _ok is None:
                    st.warning(f"ℹ️ {_err}")
                else:
                    st.success("E-posta gönderildi.")
                con=db(); con.execute("UPDATE transfers SET updated_at=? WHERE id=?",(now,int(rid))); con.commit(); con.close(); st.rerun()
    if can_approve:
        rp_hr=all_pending[all_pending["status"].eq("Bölge Müdürleri Onayı Bekliyor")]
        if not rp_hr.empty:
            with st.expander("İK Doğrudan Yetkisi — Bölge Onayı Bekleyen Talepleri Atla"):
                st.caption("Bu bölüm yalnız İK/yönetim yetkisine sahip kullanıcılara görünür. Kullanımı, bölge müdürü onayı beklenmeden talebi doğrudan İK onaylı hale getirir.")
                hrid=st.selectbox("Bölge onayı bekleyen talep",rp_hr["id"].tolist(),key="hr_override_id")
                hr_override_note=st.text_area("Geçersiz kılma gerekçesi (zorunlu)",key="hr_override_note")
                if st.button("İK doğrudan yetkisiyle onayla (bölge onayını atla)"):
                    if not hr_override_note.strip():
                        st.error("Geçersiz kılma gerekçesi zorunludur.")
                    else:
                        now=datetime.now().isoformat(timespec="seconds")
                        con=db(); con.row_factory=sqlite3.Row
                        con.execute(
                            "UPDATE transfers SET status='İK Onayladı',fact_status='Fact_Mevcut Güncellemesi Bekleniyor',decision_by=?,decision_note=?,decision_at=?,updated_at=? WHERE id=?",
                            (username,f"İK doğrudan yetkisiyle onaylandı (bölge onayı atlandı). Gerekçe: {hr_override_note}",now,now,int(hrid)),
                        )
                        row=dict(con.execute("SELECT * FROM transfers WHERE id=?",(int(hrid),)).fetchone()); con.commit(); con.close()
                        recipients=transfer_recipients(acc,row,sheets)
                        _govde=_transfer_bilgi_govdesi(row,"İK Doğrudan Onayladı",f"Gerekçe: {hr_override_note}",rotasyon_var=True)
                        _job_id,_ok,_err=_enqueue_and_process("TRANSFER_DECISION",{"transfer_id":int(hrid),"row":row,"approved":True,"subject":f"Transfer Talebi #{hrid}: İK Doğrudan Onayladı","body":_govde,"recipients":recipients},tenant_code())
                        con=db(); con.execute("UPDATE transfers SET updated_at=? WHERE id=?",(now,int(hrid))); con.commit(); con.close()
                        log(username,"TRANSFER_HR_OVERRIDE_REGION",f"{hrid}: {hr_override_note}")
                        try:
                            from services.management_center import reconcile_transfer_requests
                            _reconcile = reconcile_transfer_requests(fm)
                            if _reconcile.get("applied", 0):
                                from web.queue_utils import enqueue_report_refresh
                                enqueue_report_refresh()
                        except Exception as _rec_exc:
                            from services.safe_exec import log_swallowed
                            log_swallowed("onaylar.py: İK doğrudan onay sonrası reconcile_transfer_requests hatası", _rec_exc, level="ERROR")
                        if _ok is False:
                            st.error(f"⚠️ Onay kaydedildi AMA rotasyon evrakı/e-posta gönderilemedi: {_err}")
                        elif _ok is None:
                            st.warning(f"ℹ️ Onay kaydedildi. {_err}")
                        else:
                            st.success("Talep, İK doğrudan yetkisiyle bölge onayı atlanarak onaylandı — rotasyon evrakı ve e-posta gönderildi.")
                        st.rerun()
    hp=all_pending[all_pending["status"].isin(["İK Onayı Bekliyor","Revizyon İstendi"])]
    if not hp.empty:
        hid=st.selectbox("İK talep no",hp["id"].tolist()); dec=st.selectbox("İK kararı",["İK Onayladı","Reddedildi","Revizyon İstendi"]); note=st.text_area("İK notu")
        _evrak_turu = "Kalıcı Rotasyon Belgesi"
        _gecici_alanlar = {}
        if dec == "İK Onayladı":
            _evrak_turu = st.radio(
                "Onay evrakı türü", ["Kalıcı Rotasyon Belgesi", "Geçici Görevlendirme / Şube Destek Formu"],
                horizontal=True, key="ik_evrak_turu",
                help="Geçici seçilirse personelin norm/asıl mağaza kaydı DEĞİŞMEZ — yalnız bir destek belgesi üretilir.",
            )
            if _evrak_turu == "Geçici Görevlendirme / Şube Destek Formu":
                from services.gecici_gorevlendirme import NEDEN_SECENEKLERI
                _gc1, _gc2 = st.columns(2)
                _bitis_tarihi = _gc1.date_input("Görevlendirme Bitiş Tarihi", key="ik_gecici_bitis")
                _sure_metni = _gc2.text_input("Toplam Süre (ör. '2 hafta')", key="ik_gecici_sure")
                _neden = st.selectbox("Görevlendirme Nedeni", NEDEN_SECENEKLERI, key="ik_gecici_neden")
                _neden_diger = st.text_input("Diğer (belirtiniz)", key="ik_gecici_neden_diger") if _neden == "Diğer" else ""
                _sicil_no = st.text_input("Sicil No (varsa)", key="ik_gecici_sicil")
                _gecici_alanlar = {
                    "end_date": _bitis_tarihi.strftime("%d.%m.%Y") if _bitis_tarihi else "",
                    "total_duration": _sure_metni, "reason": _neden, "reason_other": _neden_diger,
                    "person_id": _sicil_no,
                }
        if st.button("İK kararını kaydet"):
            now=datetime.now().isoformat(timespec="seconds"); fact="Fact_Mevcut Güncellemesi Bekleniyor" if dec=="İK Onayladı" else "Beklemiyor"
            _mevcut_satir = hp[hp["id"]==hid].iloc[0]
            _beklenen_version = int(_mevcut_satir.get("version") or 0)
            _beklenen_status = str(_mevcut_satir["status"])
            from services.web_runtime import optimistic_update_transfer
            _basarili = optimistic_update_transfer(
                int(hid), _beklenen_status, _beklenen_version,
                {"status":dec,"decision_by":username,"decision_note":note,"decision_at":now,"fact_status":fact,"updated_at":now,"approval_source":"web_ik_karari"},
            )
            if not _basarili:
                st.error(
                    "🚫 Bu talep, siz bu formu açtıktan SONRA başka biri tarafından zaten işlenmiş "
                    "(çakışma önlendi — üzerine yazılmadı). Lütfen sayfayı yenileyip güncel durumu kontrol edin."
                )
                st.rerun()
            else:
                con=db(); con.row_factory=sqlite3.Row; row=dict(con.execute("SELECT * FROM transfers WHERE id=?",(int(hid),)).fetchone()); con.close()
                if dec=="İK Onayladı" and _evrak_turu != "Geçici Görevlendirme / Şube Destek Formu":
                    # DÜZELTME: İK onayı kaydedildikten hemen sonra Fact_Mevcut'u
                    # otomatik güncelle (bkz. services/management_center.py:
                    # reconcile_transfer_requests). Geçici görevlendirmede
                    # norm/asıl mağaza kaydı kasıtlı olarak DEĞİŞMEZ, bu yüzden
                    # burada çağrılmıyor.
                    try:
                        from services.management_center import reconcile_transfer_requests
                        _reconcile = reconcile_transfer_requests(fm)
                        if _reconcile.get("applied", 0):
                            from web.queue_utils import enqueue_report_refresh
                            enqueue_report_refresh()
                    except Exception as _rec_exc:
                        from services.safe_exec import log_swallowed
                        log_swallowed("onaylar.py: İK kararı sonrası reconcile_transfer_requests hatası", _rec_exc, level="ERROR")
                recipients=transfer_recipients(acc,row,sheets)
                _govde=_transfer_bilgi_govdesi(row,dec,note,rotasyon_var=(dec=="İK Onayladı"))
                _job_id,_ok,_err=_enqueue_and_process("TRANSFER_DECISION",{"transfer_id":int(hid),"row":row,"approved":dec=="İK Onayladı","subject":f"Transfer Talebi #{hid}: {dec}","body":_govde,"recipients":recipients,"document_type":("TEMPORARY" if _evrak_turu=="Geçici Görevlendirme / Şube Destek Formu" else "PERMANENT"),"temp_fields":_gecici_alanlar},tenant_code())
                if _ok is False:
                    st.error(f"⚠️ Karar kaydedildi AMA rotasyon evrakı/e-posta gönderilemedi: {_err}")
                elif _ok is None:
                    st.warning(f"ℹ️ Karar kaydedildi. {_err}")
                else:
                    st.success("Karar kaydedildi — rotasyon evrakı (varsa) ve e-posta devreden/devralan şubelere gönderildi.")
                st.rerun()
    actionable=all_pending[all_pending["status"].eq("İK Onayladı")]
    if not actionable.empty:
        with st.expander("Rotasyon Evrakını Yeniden Oluştur / Gönder", expanded=False):
            st.caption(
                "Doğrudan İK onaylı oluşturulan veya ilk gönderimi başarısız olan bir talep için "
                "rotasyon PDF/DOCX belgelerini yeniden üretir ve devreden/devralan şubelere e-posta gönderir."
            )
            resend_id = st.selectbox(
                "Onaylanmış transfer talebi",
                actionable["id"].tolist(),
                key="rotation_resend_id",
            )
            resend_note = st.text_input(
                "Yeniden gönderim notu",
                value="Rotasyon evrakı yeniden oluşturuldu ve gönderildi.",
                key="rotation_resend_note",
            )
            if st.button("Rotasyon evrakını yeniden oluştur ve gönder", type="primary", key="rotation_resend_button"):
                con=db(); con.row_factory=sqlite3.Row
                _record=con.execute("SELECT * FROM transfers WHERE id=?",(int(resend_id),)).fetchone()
                row=dict(_record) if _record else {}
                con.close()
                if not row:
                    st.error("Seçilen transfer talebi bulunamadı.")
                else:
                    recipients=transfer_recipients(acc,row,sheets)
                    _govde=_transfer_bilgi_govdesi(
                        row,
                        "İK Onayladı — Rotasyon Evrakı Yeniden Gönderimi",
                        resend_note,
                        rotasyon_var=True,
                    )
                    _token=datetime.now().strftime("%Y%m%d%H%M%S%f")
                    _job_id,_ok,_err=_enqueue_and_process(
                        "TRANSFER_DECISION",
                        {
                            "transfer_id":int(resend_id),
                            "row":row,
                            "approved":True,
                            "subject":f"Transfer Talebi #{resend_id}: Rotasyon Evrakı",
                            "body":_govde,
                            "recipients":recipients,
                            "force_resend":True,
                            "resend_token":_token,
                        },
                        tenant_code(),
                    )
                    log(username,"TRANSFER_ROTATION_RESEND",f"{resend_id}: {resend_note}")
                    if _ok is False:
                        st.error(f"⚠️ Rotasyon evrakı/e-posta yeniden gönderilemedi: {_err}")
                    elif _ok is None:
                        st.warning(f"ℹ️ Yeniden gönderim kuyruğa alındı. {_err}")
                    else:
                        st.success("Rotasyon PDF/DOCX evrakı yeniden oluşturuldu ve e-posta gönderildi.")
                    st.rerun()
    st.subheader("Onay Sonrası İptal / Başka Hedefe Yönlendirme")
    action_id=st.selectbox("İşlem yapılacak talep",actionable["id"].tolist(),key="post_approval_id")
    action=st.radio("İşlem",["Transferi İptal Et","Başka Yere Transfer Et"],horizontal=True)
    action_reason=st.text_area("İptal / yönlendirme gerekçesi",key="post_approval_reason")
    if action=="Transferi İptal Et":
        if st.button("Transferi iptal et ve mail gönder",type="primary"):
            if not action_reason.strip():
                st.error("İptal gerekçesi zorunludur.")
            else:
                cancel_transfer_request(action_id,username,action_reason,acc,sheets)
                st.success("Transfer iptal edildi ve iptal bildirimi gönderildi."); st.rerun()
    else:
        targets=sheets["Fact_Norm"][["Mağaza","Bölge Sorumlusu"]].drop_duplicates().sort_values("Mağaza")
        new_store=st.selectbox("Yeni hedef mağaza",targets["Mağaza"].tolist(),key="redirect_store")
        new_title=st.selectbox("Yeni hedef departman/unvan",sorted(sheets["Fact_Norm"]["Unvan"].dropna().astype(str).unique()),key="redirect_title")
        new_region=targets[targets["Mağaza"].eq(new_store)]["Bölge Sorumlusu"].iloc[0]
        if st.button("Eski talebi iptal et ve yeni transferi oluştur",type="primary"):
            if not action_reason.strip():
                st.error("Yönlendirme gerekçesi zorunludur.")
            else:
                new_id,_=redirect_transfer_request(
                    action_id,username,new_store,new_title,new_region,action_reason,acc,sheets
                )
                st.success(f"Eski talep iptal edildi; yeni transfer talebi #{new_id} oluşturuldu."); st.rerun()
