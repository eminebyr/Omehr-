"""Transfer Merkezi sekmesi.

Bu modül, web/app.py içindeki eski "with tabs[N]:" bloğundan otomatik
olarak çıkarılmıştır. Kod davranışı değiştirilmeden taşınmıştır; tüm
paylaşılan durum (sheets, kullanıcı/rol bilgisi, fm/detail/stores/kpis,
servis fonksiyonları) web.context.PageContext üzerinden gelir.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

import time
from datetime import date, datetime
from web.geo_transfer import store_coordinates, person_address_lookup
from web.formatting import haversine_km
from web.context import PageContext
from web.transfer_email import transfer_bilgi_govdesi as _transfer_bilgi_govdesi


def render(ctx: PageContext) -> None:
    """Transfer Merkezi sekmesinin içeriğini çizer."""
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

    st.subheader("Transfer Talebi Oluştur")
    st.caption("Personeli, hedef mağazayı ve hedef unvanı seçerek talebi kaydedin. Zorunlu alanlar yıldızlıdır.")

    # Kapsama göre görülebilen aktif personel listesi. Boş/eksik alanlar yüzünden
    # formun sessizce kullanılamaz hale gelmesini önlemek için güvenli kolonlar oluşturulur.
    people = fm.copy()
    for col in ["PersonelID", "İsim Soyisim", "Mağaza", "Unvan", "Bölge Sorumlusu"]:
        if col not in people.columns:
            people[col] = ""
    people = people.dropna(subset=["İsim Soyisim"]).copy()
    people["İsim Soyisim"] = people["İsim Soyisim"].astype(str).str.strip()
    people = people[people["İsim Soyisim"].ne("")]
    people = people.sort_values(["Mağaza", "İsim Soyisim"], na_position="last")
    label_map = {
        f"{r['İsim Soyisim']} | {r.get('Mağaza','')} | {r.get('Unvan','')}": r
        for _, r in people.iterrows()
    }

    # Hedef mağazaları önce Dim_Magaza'dan, o yoksa Fact_Norm'dan üret.
    # Böylece Fact_Norm'daki boş/bozuk mağaza kolonları formu kilitlemez.
    target_frames = []
    dm = sheets.get("Dim_Magaza", pd.DataFrame()).copy()
    if not dm.empty and "Mağaza" in dm.columns:
        if "Bölge Sorumlusu" not in dm.columns:
            dm["Bölge Sorumlusu"] = ""
        target_frames.append(dm[["Mağaza", "Bölge Sorumlusu"]])
    fn = sheets.get("Fact_Norm", pd.DataFrame()).copy()
    if not fn.empty and "Mağaza" in fn.columns:
        if "Bölge Sorumlusu" not in fn.columns:
            fn["Bölge Sorumlusu"] = ""
        target_frames.append(fn[["Mağaza", "Bölge Sorumlusu"]])
    targets = pd.concat(target_frames, ignore_index=True) if target_frames else pd.DataFrame(columns=["Mağaza", "Bölge Sorumlusu"])
    targets["Mağaza"] = targets["Mağaza"].astype(str).str.strip()
    targets = targets[targets["Mağaza"].ne("")].drop_duplicates(subset=["Mağaza"], keep="first").sort_values("Mağaza")

    if not label_map:
        st.error("Aktif personel listesi oluşturulamadı. Fact_Mevcut sayfasındaki PersonelID, İsim Soyisim, Mağaza ve Unvan alanlarını kontrol edin.")
    if targets.empty:
        st.error("Hedef mağaza listesi oluşturulamadı. Dim_Magaza veya Fact_Norm sayfasındaki Mağaza alanlarını kontrol edin.")

    col_person, col_target = st.columns(2)
    with col_person:
        selected = st.selectbox("Personel *", list(label_map), index=None, placeholder="Personel seçin") if label_map else None
    selected_row = label_map.get(selected) if selected else None
    source_store = str(selected_row.get("Mağaza", "")).strip() if selected_row is not None else ""
    available_targets = targets[~targets["Mağaza"].eq(source_store)] if source_store else targets
    with col_target:
        target_options = available_targets["Mağaza"].tolist()
        target = st.selectbox("Hedef mağaza *", target_options, index=None, placeholder="Hedef mağaza seçin", disabled=not bool(target_options))

    # Canlı ev-hedef mağaza mesafe önizlemesi.
    preview_km = None
    preview_route = None
    if selected and target:
        r_prev = label_map[selected]
        pid_prev = str(r_prev.get("PersonelID", "")).strip()
        people_addr = person_address_lookup(sheets)
        home = people_addr.get((pid_prev, norm_text(r_prev.get("İsim Soyisim", "")))) or people_addr.get((pid_prev, "")) or {}
        home_lat, home_lon = home.get("lat"), home.get("lon")
        coords = store_coordinates(sheets)
        cmap = {}
        if not coords.empty:
            for _, rr in coords.iterrows():
                cmap[str(rr.get("Mağaza", ""))] = (rr.get("Enlem"), rr.get("Boylam"))
        target_coord = cmap.get(target)
        if pd.notna(home_lat) and pd.notna(home_lon) and target_coord and all(pd.notna(v) for v in target_coord):
            preview_km = haversine_km(home_lat, home_lon, *target_coord)
            preview_route = maps_route(home_lat, home_lon, *target_coord)
        if preview_km is not None:
            if can_view_personal_address:
                st.info(f"📍 Evden **{target}** mağazasına mesafe: **{preview_km:.1f} km** · [Google Maps rotası]({preview_route})")
            else:
                st.info(f"📍 Evden **{target}** mağazasına mesafe: **{preview_km:.1f} km**")
        else:
            st.caption("Adres veya koordinat eksik olduğu için ev-hedef mağaza mesafesi hesaplanamadı; talep yine de oluşturulabilir.")

    # Hedef unvanlar Fact_Norm + Dim_Unvan birleşiminden hazırlanır.
    titles = []
    for frame_name in ("Fact_Norm", "Dim_Unvan"):
        frame = sheets.get(frame_name, pd.DataFrame())
        if not frame.empty and "Unvan" in frame.columns:
            titles.extend(frame["Unvan"].dropna().astype(str).str.strip().tolist())
    title_options = sorted({x for x in titles if x})
    if selected_row is not None:
        current_title = str(selected_row.get("Unvan", "")).strip()
        if current_title and current_title not in title_options:
            title_options.append(current_title)
            title_options.sort()

    with st.form("transfer_request_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            target_title = st.selectbox("Hedef unvan *", title_options, index=(title_options.index(str(selected_row.get('Unvan','')).strip()) if selected_row is not None and str(selected_row.get('Unvan','')).strip() in title_options else None), placeholder="Hedef unvan seçin", disabled=not bool(title_options))
        with c2:
            planned = st.date_input("Başlangıç tarihi *", value=date.today(), format="DD.MM.YYYY")
        reason = st.text_area("Gerekçe *", placeholder="Transfer gerekçesini açık ve anlaşılır şekilde yazın.", height=110, max_chars=1000)
        hr_direct = False
        if can_approve:
            hr_direct = st.checkbox(
                "İK doğrudan yetkisiyle onayla (Bölge Müdürü onayı beklenmeden)",
                help="İşaretlenirse talep doğrudan İK onaylı oluşturulur ve Fact_Mevcut güncellemesi bekler.",
            )
        submit = st.form_submit_button("Transfer Talebini Oluştur", type="primary", use_container_width=True, disabled=not (selected and target and title_options))

    if submit:
        errors = []
        if not selected or selected not in label_map:
            errors.append("Personel seçilmedi.")
        if not target:
            errors.append("Hedef mağaza seçilmedi.")
        if selected_row is not None and target == source_store:
            errors.append("Hedef mağaza mevcut mağazayla aynı olamaz.")
        if not target_title:
            errors.append("Hedef unvan seçilmedi.")
        if not str(reason or "").strip():
            errors.append("Gerekçe boş bırakılamaz.")
        if errors:
            st.error("Talep oluşturulamadı:\n- " + "\n- ".join(errors))
        else:
            r = label_map[selected]
            tr_match = targets[targets["Mağaza"].eq(target)]
            tr = tr_match.iloc[0] if not tr_match.empty else pd.Series({"Bölge Sorumlusu": ""})
            now = datetime.now().isoformat(timespec="seconds")
            pa = sheets.get("Personel_Adresleri", pd.DataFrame())
            source_home_km = source_home_route = None
            if not pa.empty and "PersonelID" in pa.columns:
                match = pa[pa["PersonelID"].astype(str) == str(r.get("PersonelID", ""))]
                if not match.empty:
                    source_home_km = pd.to_numeric(match.iloc[0].get("Ev-Mevcut Mağaza Mesafesi (km)"), errors="coerce")
                    source_home_km = None if pd.isna(source_home_km) else float(source_home_km)
                    source_home_route = match.iloc[0].get("Ev-Mevcut Mağaza Google Maps Rota") or None
            hr_bypass_roles = {"REGION", "HR_DIRECTOR", "ADMIN", "CEO", "EXECUTIVE", "MANAGEMENT"}
            if hr_direct and can_approve:
                status, fact_status = "İK Onayladı", "Fact_Mevcut Güncellemesi Bekleniyor"
            elif role in hr_bypass_roles:
                status, fact_status = "İK Onayı Bekliyor", "Bekliyor"
            else:
                status, fact_status = "Bölge Müdürleri Onayı Bekliyor", "Bekliyor"
            try:
                from services.web_runtime import yeni_transfer_no
                transfer_no = yeni_transfer_no()
                con = db()
                cur = con.execute(
                    """INSERT INTO transfers(created_at,created_by,region,source_store,target_store,person_id,person_name,current_title,target_title,target_region,planned_date,reason,status,fact_status,outlook_status,updated_at,decision_by,decision_note,decision_at,source_home_km,source_home_route,target_home_km,target_home_route,transfer_no) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (now, username, r.get("Bölge Sorumlusu", ""), r.get("Mağaza", ""), target, r.get("PersonelID", ""), r.get("İsim Soyisim", ""), r.get("Unvan", ""), target_title, tr.get("Bölge Sorumlusu", ""), str(planned), str(reason).strip(), status, fact_status, "PENDING", now, (username if hr_direct and can_approve else None), ("İK doğrudan yetkisiyle, bölge müdürü onayı alınmadan oluşturuldu." if hr_direct and can_approve else None), (now if hr_direct and can_approve else None), source_home_km, source_home_route, preview_km, preview_route, transfer_no),
                )
                tid = cur.lastrowid
                con.commit()
                con.close()
                con = db(); con.row_factory = __import__("sqlite3").Row
                row = dict(con.execute("SELECT * FROM transfers WHERE id=?", (int(tid),)).fetchone())
                con.close()
                recipients = transfer_recipients(acc, row, sheets)
                extra_note = "\n(İK doğrudan yetkisiyle oluşturuldu; bölge müdürü onayı gerekmedi.)" if hr_direct and can_approve else ""
                distance_note = f"\nEv-Hedef Mağaza Mesafesi: {preview_km:.1f} km" if preview_km is not None else ""

                if hr_direct and can_approve:
                    # Doğrudan İK onaylı oluşturulan taleplerde normal onay akışındaki
                    # aynı rotasyon PDF/DOCX + Outlook gönderim görevini anında çalıştır.
                    body = _transfer_bilgi_govdesi(
                        row,
                        "İK Doğrudan Onayladı",
                        f"Gerekçe: {str(reason).strip()}{distance_note}",
                        rotasyon_var=True,
                    )
                    _job_id, _ok, _err = _enqueue_and_process(
                        "TRANSFER_DECISION",
                        {
                            "transfer_id": int(tid),
                            "row": row,
                            "approved": True,
                            "subject": f"Transfer Talebi #{tid}: İK Doğrudan Onayladı",
                            "body": body,
                            "recipients": recipients,
                        },
                        tenant_code(),
                    )
                    log(username, "TRANSFER_CREATE_HR_DIRECT", str(tid))
                    if _ok is False:
                        st.error(f"⚠️ Talep oluşturuldu AMA rotasyon evrakı/e-posta gönderilemedi: {_err}")
                    elif _ok is None:
                        st.warning(f"ℹ️ Talep oluşturuldu. {_err}")
                    else:
                        st.success(
                            f"Transfer talebi #{tid} doğrudan İK onaylı oluşturuldu; "
                            "rotasyon PDF/DOCX evrakı ve e-posta gönderildi."
                        )
                else:
                    mail_job = enqueue(
                        "SEND_EMAIL",
                        {
                            "subject": f"Transfer Talebi #{tid}",
                            "body": f"{r.get('İsim Soyisim')} için {r.get('Mağaza')} -> {target}\nDurum: {status}\nGerekçe: {str(reason).strip()}{extra_note}{distance_note}",
                            "recipients": recipients,
                            "transfer_id": tid,
                        },
                        tenant_code(),
                    )
                    con = db(); con.execute("UPDATE transfers SET outlook_status=? WHERE id=?", (f"QUEUED:{mail_job}", tid)); con.commit(); con.close()
                    log(username, "TRANSFER_CREATE", str(tid))
                    st.success(f"Transfer talebi #{tid} oluşturuldu. Durum: {status}. Bildirim kuyruğa alındı.")
                st.rerun()
            except Exception as exc:
                st.exception(RuntimeError(f"Transfer talebi kaydedilemedi: {exc}"))

    st.divider()
    st.subheader("Transfer Talebi Geçmişi")
    con=db(); q="SELECT * FROM transfers" if is_global else "SELECT * FROM transfers WHERE region=? OR target_region=?"; params=() if is_global else (scope,scope); tf=pd.read_sql_query(q+" ORDER BY id DESC",con,params=params); con.close(); st.dataframe(tf,use_container_width=True,hide_index=True)
