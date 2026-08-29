"""Personel Kartları — düz tablo yerine kart görünümü, tekli/toplu yeni
personel ekleme ve tekli/toplu işten çıkış işlemi için web panelinden
özel bir akış. Her işlem sonrası ilgili taraflara otomatik bildirim
gönderilir (services/personnel_notifications.py).

DÜZELTME: Bu sayfa önceden YALNIZ veritabanı modunda çalışıyor, Excel
modunda (VARSAYILAN durum) tamamen devre dışı kalıyordu. Artık TÜM veri
okuma/yazma mantığı services/personnel_exit.py'de merkezileştirildi ve
bu modül hangi kaynağın aktif olduğunu bilmeden, ikisinde de aynı
şekilde çalışır.

DÜZELTME (toplu işlemler entegrasyonu): Toplu işe giriş ve toplu işten
çıkış (kişi başına FARKLI çıkış kodu/nedeni seçilebilir, Excel/veritabanına
TEK yazma işlemiyle kaydedilir) eklendi. Bildirim modülünde önceden var
olan, çok kiracılı SaaS için YANLIŞ olan bir davranış (her bildirime
sabit bir kişinin e-postasının otomatik eklenmesi) bu entegrasyon
sırasında KALDIRILDI — bkz. services/personnel_notifications.py.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from web.context import PageContext
from services.personnel_exit import (
    load_personnel_view, is_active, add_personnel, update_personnel,
    process_exit, add_personnel_bulk, process_exits_bulk, undo_exit,
)
from services.personnel_notifications import (
    selectable_extra_contacts, personnel_event_recipients, send_personnel_event_mail,
)
from services.atama_bildirimi import create_assignment_notice


def _personel_degisikligi_sonrasi_raporlari_yenile() -> None:
    """DÜZELTME (yeni özellik — kullanıcı isteği): personel eklendiğinde/
    çıkarıldığında/atandığında kutucuklu PDF/Excel raporları artık
    OTOMATİK olarak yeniden üretiliyor — önceden bu, kimse manuel
    'yeniden üret' butonuna basmadıkça ya da zamanlayıcı (10:00/17:15)
    çalışmadıkça olmuyordu, bu yüzden yeni eklenen personel raporlarda
    görünmüyordu. web.app._enqueue_without_waiting NON-BLOCKING olduğu
    için (bkz. o fonksiyonun docstring'i) sayfayı DONDURMAZ — iş arka
    planda kuyruğa alınır, 1-3 dakika içinde tamamlanır. Bu çağrı
    kasıtlı olarak sessizdir (try/except) — rapor tetikleme başarısız
    olsa bile personel kaydının kendisi ETKİLENMEMELİDİR.
    """
    try:
        from web.queue_utils import enqueue_report_refresh
        enqueue_report_refresh()
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed(
            "personel_kartlari: personel değişikliği sonrası otomatik "
            "rapor tetikleme başarısız — personel kaydı ETKİLENMEDİ",
            _exc, level="WARNING",
        )


def _kidem_metni(ise_giris) -> str:
    try:
        d = pd.to_datetime(ise_giris, errors="coerce")
        if pd.isna(d):
            return "—"
        gun = (pd.Timestamp.now() - d).days
        if gun < 0:
            return "—"
        yil = gun // 365
        ay = (gun % 365) // 30
        if yil > 0:
            return f"{yil} yıl {ay} ay"
        return f"{ay} ay"
    except Exception:
        return "—"


def _kart(satir: dict, index, magaza_df, unvan_df, staff_df, ctx) -> None:
    with st.container(border=True):
        st.markdown(f"**{satir.get('İsim Soyisim') or '(isimsiz)'}**")
        st.caption(f"{satir.get('Unvan') or '—'}  ·  {satir.get('Mağaza') or '—'}")
        c1, c2 = st.columns(2)
        c1.caption(f"İşe Giriş: {satir.get('İşe Giriş') or '—'}")
        c2.caption(f"Kıdem: {_kidem_metni(satir.get('İşe Giriş'))}")
        if str(satir.get("Açıklama") or "").strip():
            st.caption(f"Not: {satir.get('Açıklama')}")
        from services.personnel_permissions import can as _can
        if _can(ctx.input_path, ctx.email, "personnel_edit", ctx.role):
            with st.expander("Düzenle"):
                _kart_duzenle_formu(satir, index, magaza_df, unvan_df, staff_df, ctx)


def _kart_duzenle_formu(satir: dict, index, magaza_df, unvan_df, staff_df, ctx) -> None:
    magaza_secenekleri = magaza_df["Mağaza"].dropna().astype(str).tolist()
    unvan_secenekleri = unvan_df["Unvan"].dropna().astype(str).tolist()
    key_taban = f"kart_{index}_{satir.get('İsim Soyisim')}"

    with st.form(key=f"form_{key_taban}"):
        yeni_isim = st.text_input("İsim Soyisim", value=str(satir.get("İsim Soyisim") or ""), key=f"isim_{key_taban}")
        mevcut_magaza = str(satir.get("Mağaza") or "")
        yeni_magaza = st.selectbox(
            "Mağaza", magaza_secenekleri,
            index=magaza_secenekleri.index(mevcut_magaza) if mevcut_magaza in magaza_secenekleri else 0,
            key=f"magaza_{key_taban}",
        )
        mevcut_unvan = str(satir.get("Unvan") or "")
        yeni_unvan = st.selectbox(
            "Unvan", unvan_secenekleri,
            index=unvan_secenekleri.index(mevcut_unvan) if mevcut_unvan in unvan_secenekleri else 0,
            key=f"unvan_{key_taban}",
        )
        yeni_aciklama = st.text_area("Açıklama", value=str(satir.get("Açıklama") or ""), key=f"aciklama_{key_taban}")
        kaydet = st.form_submit_button("Kaydet", type="primary")

    if kaydet:
        magaza_id = magaza_df.loc[magaza_df["Mağaza"].astype(str).eq(yeni_magaza), "MağazaID"]
        unvan_id = unvan_df.loc[unvan_df["Unvan"].astype(str).eq(yeni_unvan), "UnvanID"]
        guncellemeler = {
            "İsim Soyisim": yeni_isim,
            "Mağaza": yeni_magaza,
            "MağazaID": magaza_id.iloc[0] if not magaza_id.empty else satir.get("MağazaID"),
            "Unvan": yeni_unvan,
            "UnvanID": unvan_id.iloc[0] if not unvan_id.empty else satir.get("UnvanID"),
            "Açıklama": yeni_aciklama,
        }
        try:
            update_personnel(
                input_path=ctx.input_path, root=ctx.root, staff=staff_df,
                index=index, guncellemeler=guncellemeler, username=getattr(ctx, "username", ""),
            )
            _personel_degisikligi_sonrasi_raporlari_yenile()
            st.success(f"{yeni_isim} güncellendi.")
            st.rerun()
        except Exception as exc:
            st.error(f"Kaydetme başarısız: {exc}")


def _sekme_kartlar(ctx: PageContext, staff, magaza, unvan) -> None:
    st.caption("Yalnız AKTİF (işten çıkışı olmayan) personel kart olarak listelenir.")
    aktif_mask = staff.apply(lambda r: is_active(r.to_dict()), axis=1)
    aktif = staff[aktif_mask]

    c1, c2, c3 = st.columns(3)
    magaza_filtre = c1.selectbox("Mağaza filtresi", ["(Tümü)"] + sorted(magaza["Mağaza"].dropna().astype(str).unique().tolist()), key="pk_magaza_filtre")
    unvan_filtre = c2.selectbox("Unvan filtresi", ["(Tümü)"] + sorted(unvan["Unvan"].dropna().astype(str).unique().tolist()), key="pk_unvan_filtre")
    arama = c3.text_input("İsimde ara", key="pk_arama")

    gosterilecek = aktif
    if magaza_filtre != "(Tümü)":
        gosterilecek = gosterilecek[gosterilecek["Mağaza"].astype(str).eq(magaza_filtre)]
    if unvan_filtre != "(Tümü)":
        gosterilecek = gosterilecek[gosterilecek["Unvan"].astype(str).eq(unvan_filtre)]
    if arama.strip():
        gosterilecek = gosterilecek[gosterilecek["İsim Soyisim"].astype(str).str.contains(arama, case=False, na=False)]

    st.caption(f"{len(gosterilecek)} personel gösteriliyor (toplam aktif: {len(aktif)}).")

    satirlar = list(gosterilecek.iterrows())
    SUTUN_SAYISI = 3
    for i in range(0, len(satirlar), SUTUN_SAYISI):
        cols = st.columns(SUTUN_SAYISI)
        for j, (idx, satir) in enumerate(satirlar[i:i + SUTUN_SAYISI]):
            with cols[j]:
                _kart(satir.to_dict(), idx, magaza, unvan, staff, ctx)


def _ek_alici_secimi(ctx: PageContext, key: str, magaza_adi: str, magaza_id: str = ""):
    contacts = selectable_extra_contacts(ctx.input_path)
    label_to_email = {label: email for label, email in contacts}
    try:
        auto = personnel_event_recipients(ctx.input_path, magaza_adi, magaza_id).get("automatic", [])
    except Exception:
        auto = []
    st.caption("Otomatik alıcılar: ilgili mağaza + ilgili bölge müdürü + aktif admin/İK yöneticileri.")
    if auto:
        st.caption("Otomatik: " + "; ".join(auto))
    selected = st.multiselect(
        "Ek alıcılar (isteğe bağlı)",
        list(label_to_email),
        key=key,
        help="Otomatik alıcılara ek olarak Mail_Listesi'ndeki aktif kişilerden seçim yapabilirsiniz.",
    )
    return [label_to_email[x] for x in selected if x in label_to_email]


def _common_extra_recipient_selection(ctx: PageContext, key: str) -> list[str]:
    contacts = selectable_extra_contacts(ctx.input_path)
    label_to_email = {label: email for label, email in contacts}
    selected = st.multiselect(
        "Tüm seçili personele eklenecek ek alıcılar (isteğe bağlı)",
        list(label_to_email),
        key=key,
        help="Her personel için mağaza + ilgili bölge müdürü + admin/İK otomatik belirlenir. Buradan seçtikleriniz bunlara eklenir.",
    )
    return [label_to_email[x] for x in selected if x in label_to_email]


def _sekme_yeni_personel(ctx: PageContext, staff, magaza, unvan) -> None:
    st.caption("Yeni personel kaydını kart biçiminde ekleyin.")
    magaza_secenekleri = sorted(magaza["Mağaza"].dropna().astype(str).unique().tolist())
    unvan_secenekleri = sorted(unvan["Unvan"].dropna().astype(str).unique().tolist())

    with st.form("form_yeni_personel"):
        isim = st.text_input("İsim Soyisim *")
        c1, c2 = st.columns(2)
        secilen_magaza = c1.selectbox("Mağaza *", magaza_secenekleri)
        secilen_unvan = c2.selectbox("Unvan *", unvan_secenekleri)
        departman = st.text_input("Departman", value=secilen_unvan)
        ise_giris = st.date_input("İşe Giriş Tarihi", value=date.today())
        aciklama = st.text_area("Açıklama (isteğe bağlı)")
        magaza_id_preview = magaza.loc[magaza["Mağaza"].astype(str).eq(secilen_magaza), "MağazaID"]
        _mid_preview = str(magaza_id_preview.iloc[0]) if not magaza_id_preview.empty else ""
        ek_alicilar = _ek_alici_secimi(ctx, "pk_yeni_ek_alicilar", secilen_magaza, _mid_preview)
        kaydet = st.form_submit_button("Personeli Ekle ve Bildir", type="primary")

    if kaydet:
        if not isim.strip():
            st.error("İsim Soyisim zorunludur.")
            return
        magaza_id = magaza.loc[magaza["Mağaza"].astype(str).eq(secilen_magaza), "MağazaID"]
        unvan_id = unvan.loc[unvan["Unvan"].astype(str).eq(secilen_unvan), "UnvanID"]
        yeni_satir = {c: None for c in staff.columns}
        yeni_satir.update({
            "İsim Soyisim": isim.strip(),
            "Mağaza": secilen_magaza,
            "MağazaID": magaza_id.iloc[0] if not magaza_id.empty else None,
            "Unvan": secilen_unvan,
            "UnvanID": unvan_id.iloc[0] if not unvan_id.empty else None,
            "Departman": departman.strip() or secilen_unvan,
            "İşe Giriş": ise_giris.isoformat(),
            "İşten Çıkış": None,
            "Açıklama": aciklama.strip(),
        })
        try:
            add_personnel(
                input_path=ctx.input_path, root=ctx.root, staff=staff,
                yeni_kayit=yeni_satir, username=getattr(ctx, "username", ""),
            )
            mail_result = send_personnel_event_mail(
                input_path=ctx.input_path, event="ISE_GIRIS", person=yeni_satir, extra_recipients=ek_alicilar
            )
            if str(mail_result.get("status", "")).startswith(("SENT", "SKIPPED", "QUEUED")):
                st.success(f"{isim} eklendi. Aktif mevcut ve norm hesapları güncellendi; bildirim: {mail_result.get('status')}")
            else:
                st.warning(f"{isim} kaydedildi ve hesaplar güncellendi; e-posta gönderimi başarısız: {mail_result.get('status')}")
            _personel_degisikligi_sonrasi_raporlari_yenile()
            st.rerun()
        except Exception as exc:
            st.error(f"Kaydetme başarısız: {exc}")


def _sekme_toplu_yeni_personel(ctx: PageContext, staff, magaza, unvan) -> None:
    st.caption(
        "Birden fazla işe girişi tek seferde hazırlayın. Kayıt tek işlemle yapılır; "
        "her personelin bildirimi kendi mağazası, bölge müdürü ve admin/İK'ya gider."
    )
    magaza_secenekleri = sorted(magaza["Mağaza"].dropna().astype(str).unique().tolist())
    unvan_secenekleri = sorted(unvan["Unvan"].dropna().astype(str).unique().tolist())
    default = pd.DataFrame([
        {"İsim Soyisim": "", "Mağaza": magaza_secenekleri[0] if magaza_secenekleri else "",
         "Unvan": unvan_secenekleri[0] if unvan_secenekleri else "", "Departman": "",
         "İşe Giriş": date.today(), "Açıklama": ""}
    ])
    edited = st.data_editor(
        default,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="pk_toplu_giris_editor",
        column_config={
            "İsim Soyisim": st.column_config.TextColumn("İsim Soyisim *", required=True),
            "Mağaza": st.column_config.SelectboxColumn("Mağaza *", options=magaza_secenekleri, required=True),
            "Unvan": st.column_config.SelectboxColumn("Unvan *", options=unvan_secenekleri, required=True),
            "Departman": st.column_config.TextColumn("Departman / Norm Ailesi"),
            "İşe Giriş": st.column_config.DateColumn("İşe Giriş *", required=True),
            "Açıklama": st.column_config.TextColumn("Açıklama"),
        },
    )
    ek_alicilar = _common_extra_recipient_selection(ctx, "pk_toplu_giris_ek_alicilar")
    st.caption("İpucu: Alttaki + satır ile istediğiniz kadar personel ekleyebilirsiniz.")
    onay = st.checkbox("Toplu işe giriş kayıtlarını onaylıyorum.", key="pk_toplu_giris_onay")
    if st.button("Toplu İşe Girişi Kaydet ve Bildir", type="primary", key="pk_toplu_giris_btn"):
        rows = edited.copy()
        rows = rows[rows["İsim Soyisim"].astype(str).str.strip().ne("")]
        if rows.empty:
            st.error("En az bir personel girin.")
            return
        if not onay:
            st.error("Devam etmek için onay kutusunu işaretleyin.")
            return

        records: list[dict] = []
        for _, r in rows.iterrows():
            secilen_magaza = str(r.get("Mağaza") or "").strip()
            secilen_unvan = str(r.get("Unvan") or "").strip()
            if not secilen_magaza or not secilen_unvan:
                st.error("Her satırda Mağaza ve Unvan seçilmelidir.")
                return
            magaza_id = magaza.loc[magaza["Mağaza"].astype(str).eq(secilen_magaza), "MağazaID"]
            unvan_id = unvan.loc[unvan["Unvan"].astype(str).eq(secilen_unvan), "UnvanID"]
            yeni = {c: None for c in staff.columns}
            dt = r.get("İşe Giriş")
            if hasattr(dt, "isoformat"):
                dt = dt.isoformat()
            yeni.update({
                "İsim Soyisim": str(r.get("İsim Soyisim") or "").strip(),
                "Mağaza": secilen_magaza,
                "MağazaID": magaza_id.iloc[0] if not magaza_id.empty else None,
                "Unvan": secilen_unvan,
                "UnvanID": unvan_id.iloc[0] if not unvan_id.empty else None,
                "Departman": str(r.get("Departman") or "").strip() or secilen_unvan,
                "İşe Giriş": dt,
                "İşten Çıkış": None,
                "Açıklama": str(r.get("Açıklama") or "").strip(),
            })
            records.append(yeni)

        try:
            result = add_personnel_bulk(
                input_path=ctx.input_path, root=ctx.root, staff=staff,
                yeni_kayitlar=records, username=getattr(ctx, "username", ""),
            )
            sent = failed = skipped = queued = 0
            failures = []
            for person in records:
                mr = send_personnel_event_mail(
                    input_path=ctx.input_path, event="ISE_GIRIS", person=person, extra_recipients=ek_alicilar
                )
                status = str(mr.get("status", ""))
                if status.startswith("QUEUED"):
                    queued += 1
                elif status.startswith("SENT"):
                    sent += 1
                elif status.startswith("SKIPPED"):
                    skipped += 1
                else:
                    failed += 1
                    failures.append(f"{person.get('İsim Soyisim')}: {status}")
            st.success(
                f"{result['eklenen']} personel tek işlemde eklendi. "
                f"Aktif mevcut ve norm dengesi yenilendi. Mail: {queued} kuyruğa alındı, {sent} gönderildi, {skipped} atlandı, {failed} hata."
            )
            if failures:
                st.warning("Mail hataları: " + " | ".join(failures[:8]))
            _personel_degisikligi_sonrasi_raporlari_yenile()
            st.rerun()
        except Exception as exc:
            st.error(f"Toplu işe giriş başarısız: {exc}")


def _sekme_isten_cikis(ctx: PageContext, staff, cikis_nedeni) -> None:
    st.caption("Aktif bir personel seçip işten çıkış bilgilerini kaydedin.")
    aktif_mask = staff.apply(lambda r: is_active(r.to_dict()), axis=1)
    aktif = staff[aktif_mask]
    if aktif.empty:
        st.info("İşten çıkış işlemi yapılacak aktif personel bulunamadı.")
        return

    label_to_idx = {}
    etiketler = []
    for idx, r in aktif.iterrows():
        label = f"{r.get('İsim Soyisim','')} — {r.get('Mağaza','')} / {r.get('Unvan','')}"
        if label in label_to_idx:
            label = f"{label} [satır {idx}]"
        label_to_idx[label] = idx
        etiketler.append(label)
    secim = st.selectbox("Personel *", etiketler, key="pk_cikis_personel")
    secilen_idx = label_to_idx[secim]
    secilen = staff.loc[secilen_idx]

    with st.container(border=True):
        st.markdown(f"**{secilen['İsim Soyisim']}**")
        st.caption(f"{secilen.get('Unvan','')}  ·  {secilen.get('Mağaza','')}  ·  İşe Giriş: {secilen.get('İşe Giriş','—')}")

    if cikis_nedeni is None or cikis_nedeni.empty:
        st.warning("Dim_CikisNedeni sayfası boş — çıkış nedeni sözlüğü olmadan işlem yapılamaz.")
        return

    reason_groups = cikis_nedeni["CikisGrubu"].astype(str).dropna().drop_duplicates().tolist()
    reason_labels = (cikis_nedeni["CikisNedeni"].astype(str) + "  (" + cikis_nedeni["CikisGrubu"].astype(str) + ")").tolist()

    with st.form("form_isten_cikis"):
        cikis_tarihi = st.date_input("İşten Çıkış Tarihi *", value=date.today())
        secilen_kod = st.selectbox("Çıkış Kodu *", reason_groups, key="pk_cikis_kodu")
        secilen_neden_i = st.selectbox(
            "Çıkış Nedeni *", range(len(reason_labels)),
            format_func=lambda i: reason_labels[i], key="pk_cikis_nedeni"
        )
        ek_alicilar = _ek_alici_secimi(
            ctx, "pk_cikis_ek_alicilar", str(secilen.get("Mağaza", "")), str(secilen.get("MağazaID", ""))
        )
        onay = st.checkbox("Bu personelin işten çıkışını onaylıyorum — bu işlem geri alınamaz.")
        kaydet = st.form_submit_button("İşten Çıkışı Kaydet ve Bildir", type="primary")

    if kaydet:
        if not onay:
            st.error("Devam etmek için onay kutusunu işaretleyin.")
            return
        neden_satiri = cikis_nedeni.iloc[secilen_neden_i]
        expected_group = str(neden_satiri.get("CikisGrubu", "")).strip()
        if str(secilen_kod).strip() != expected_group:
            st.error(
                f"Çıkış Kodu/Nedeni uyumsuz: '{secilen_kod}' koduna karşı seçilen neden "
                f"'{neden_satiri.get('CikisNedeni', '')}' '{expected_group}' grubundadır. "
                "Lütfen aynı gruptan seçim yapın."
            )
            return
        try:
            sonuc = process_exit(
                input_path=ctx.input_path, root=ctx.root,
                isim_soyisim=str(secilen["İsim Soyisim"]), magaza_id=str(secilen.get("MağazaID", "")),
                staff_index=secilen_idx,
                cikis_tarihi=cikis_tarihi, cikis_kodu=str(secilen_kod),
                cikis_nedeni_id=neden_satiri["CikisNedeniID"], cikis_nedeni_metni=str(neden_satiri["CikisNedeni"]),
                kullanici=getattr(ctx, "username", ""),
            )
            person_mail = secilen.to_dict()
            person_mail.update({
                "İşten Çıkış": cikis_tarihi.isoformat(),
                "Çıkış Kodu": str(secilen_kod),
                "Çıkış Nedeni": str(neden_satiri.get("CikisNedeni", "")),
            })
            mail_result = send_personnel_event_mail(
                input_path=ctx.input_path, event="ISTEN_CIKIS", person=person_mail, extra_recipients=ek_alicilar
            )
            if str(mail_result.get("status", "")).startswith(("SENT", "SKIPPED", "QUEUED")):
                st.success(
                    f"{secilen['İsim Soyisim']} işten çıkarıldı ({sonuc['guncellenen_satir']} satır). "
                    f"Aktif mevcut/norm dengesi güncellendi; bildirim: {mail_result.get('status')}"
                )
            else:
                st.warning(
                    f"{secilen['İsim Soyisim']} işten çıkış olarak kaydedildi ve hesaplar güncellendi; "
                    f"e-posta gönderimi başarısız: {mail_result.get('status')}"
                )
            _personel_degisikligi_sonrasi_raporlari_yenile()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Kaydetme başarısız: {exc}")


def _sekme_toplu_isten_cikis(ctx: PageContext, staff, cikis_nedeni) -> None:
    st.caption(
        "Birden fazla aktif personeli seçin; çıkış tarih/nedenlerini tabloda düzenleyip tek seferde işleyin. "
        "Her personel KENDİ çıkış kodu/nedenini taşıyabilir (hepsi aynı olmak zorunda değil)."
    )
    aktif_mask = staff.apply(lambda r: is_active(r.to_dict()), axis=1)
    aktif = staff[aktif_mask]
    if aktif.empty:
        st.info("İşten çıkış işlemi yapılacak aktif personel bulunamadı.")
        return
    if cikis_nedeni is None or cikis_nedeni.empty:
        st.warning("Dim_CikisNedeni sayfası boş — çıkış nedeni sözlüğü olmadan işlem yapılamaz.")
        return

    label_to_idx = {}
    labels = []
    for idx, r in aktif.iterrows():
        label = f"{r.get('İsim Soyisim','')} — {r.get('Mağaza','')} / {r.get('Unvan','')}"
        if label in label_to_idx:
            label = f"{label} [satır {idx}]"
        label_to_idx[label] = idx
        labels.append(label)
    selected_labels = st.multiselect("Çıkışı yapılacak personeller *", labels, key="pk_toplu_cikis_secim")
    if not selected_labels:
        st.info("Tabloyu açmak için en az bir personel seçin.")
        return

    reason_labels = (cikis_nedeni["CikisNedeni"].astype(str) + "  (" + cikis_nedeni["CikisGrubu"].astype(str) + ")").tolist()
    reason_groups = cikis_nedeni["CikisGrubu"].astype(str).dropna().drop_duplicates().tolist()
    default_reason = reason_labels[0] if reason_labels else ""
    default_group = str(cikis_nedeni.iloc[0].get("CikisGrubu", "")) if not cikis_nedeni.empty else ""
    exit_rows = []
    for label in selected_labels:
        idx = label_to_idx[label]
        r = staff.loc[idx]
        exit_rows.append({
            "Kayıt Satırı": idx,
            "İsim Soyisim": r.get("İsim Soyisim", ""),
            "Mağaza": r.get("Mağaza", ""),
            "Unvan": r.get("Unvan", ""),
            "İşten Çıkış": date.today(),
            "Çıkış Kodu": default_group,
            "Çıkış Nedeni": default_reason,
            "Açıklama": str(r.get("Açıklama") or ""),
        })
    exit_df = pd.DataFrame(exit_rows)
    edited = st.data_editor(
        exit_df,
        use_container_width=True,
        hide_index=True,
        key="pk_toplu_cikis_editor",
        disabled=["Kayıt Satırı", "İsim Soyisim", "Mağaza", "Unvan"],
        column_config={
            "Kayıt Satırı": None,
            "İsim Soyisim": st.column_config.TextColumn("İsim Soyisim"),
            "Mağaza": st.column_config.TextColumn("Mağaza"),
            "Unvan": st.column_config.TextColumn("Unvan"),
            "İşten Çıkış": st.column_config.DateColumn("İşten Çıkış *", required=True),
            "Çıkış Kodu": st.column_config.SelectboxColumn(
                "Çıkış Kodu *", options=reason_groups, required=True,
                help="Her personel için ayrı seçilebilir. Örn. İstifa / İşveren feshi / Diğer.",
            ),
            "Çıkış Nedeni": st.column_config.SelectboxColumn("Çıkış Nedeni *", options=reason_labels, required=True),
            "Açıklama": st.column_config.TextColumn("Açıklama"),
        },
    )
    ek_alicilar = _common_extra_recipient_selection(ctx, "pk_toplu_cikis_ek_alicilar")
    onay = st.checkbox(f"Seçili {len(edited)} personelin işten çıkışını onaylıyorum.", key="pk_toplu_cikis_onay")
    if st.button("Toplu İşten Çıkışı Kaydet ve Bildir", type="primary", key="pk_toplu_cikis_btn"):
        if not onay:
            st.error("Devam etmek için onay kutusunu işaretleyin.")
            return
        reason_map = {lab: cikis_nedeni.iloc[i] for i, lab in enumerate(reason_labels)}
        exits = []
        mail_people = {}
        on_dogrulama_hatalari = []
        for _, er in edited.iterrows():
            idx = er.get("Kayıt Satırı")
            isim_etiketi = str(er.get("İsim Soyisim") or f"[satır {idx}]")
            reason_label = str(er.get("Çıkış Nedeni") or "")
            if reason_label not in reason_map:
                on_dogrulama_hatalari.append(f"{isim_etiketi}: çıkış nedeni seçilmedi")
                continue
            reason = reason_map[reason_label]
            selected_group = str(er.get("Çıkış Kodu") or "").strip()
            expected_group = str(reason.get("CikisGrubu", "")).strip()
            if not selected_group:
                on_dogrulama_hatalari.append(f"{isim_etiketi}: çıkış kodu seçilmedi")
                continue
            if selected_group != expected_group:
                on_dogrulama_hatalari.append(
                    f"{isim_etiketi}: Çıkış Kodu/Nedeni uyumsuz ('{selected_group}' koduna karşı "
                    f"seçilen neden '{expected_group}' grubundadır)"
                )
                continue
            exits.append({
                "index": idx,
                "cikis_tarihi": er.get("İşten Çıkış"),
                "cikis_kodu": selected_group,
                "cikis_nedeni_id": reason.get("CikisNedeniID"),
                "cikis_nedeni_metni": str(reason.get("CikisNedeni", "")),
                "aciklama": str(er.get("Açıklama") or ""),
            })
            person = staff.loc[idx].to_dict()
            dt = er.get("İşten Çıkış")
            if hasattr(dt, "isoformat"):
                dt = dt.isoformat()
            person.update({
                "İşten Çıkış": dt,
                "Çıkış Kodu": selected_group,
                "Çıkış Nedeni": str(reason.get("CikisNedeni", "")),
                "Açıklama": str(er.get("Açıklama") or ""),
            })
            mail_people[idx] = person

        try:
            sonuc_hatalari = []
            basarili_sayisi = 0
            if exits:
                result = process_exits_bulk(
                    input_path=ctx.input_path, root=ctx.root, cikislar=exits,
                    kullanici=getattr(ctx, "username", ""),
                )
                basarili_sayisi = result["guncellenen_satir"]
                for h in result.get("hatalar", []):
                    sonuc_hatalari.append(f"{h.get('isim') or h.get('index')}: {h.get('hata')}")
                basarili_index_seti = {b["index"] for b in result.get("basarili", [])}
                gonderilecekler = [p for idx, p in mail_people.items() if idx in basarili_index_seti]
            else:
                gonderilecekler = []

            sent = failed = skipped = queued = 0
            failures = []
            for person in gonderilecekler:
                mr = send_personnel_event_mail(
                    input_path=ctx.input_path, event="ISTEN_CIKIS", person=person, extra_recipients=ek_alicilar
                )
                status = str(mr.get("status", ""))
                if status.startswith("QUEUED"):
                    queued += 1
                elif status.startswith("SENT"):
                    sent += 1
                elif status.startswith("SKIPPED"):
                    skipped += 1
                else:
                    failed += 1
                    failures.append(f"{person.get('İsim Soyisim')}: {status}")

            # DÜZELTME (Madde 15 — kullanıcı kararı): her satır bağımsız
            # işlem olduğu için sonuç raporu artık "15 başarılı, 2 çıkış
            # kodu eksik, 1 zaten çıkmış" gibi DETAYLI olabilir — tek bir
            # hata ARTIK tüm işlemi engellemez.
            tum_hatalar = on_dogrulama_hatalari + sonuc_hatalari
            if basarili_sayisi:
                st.success(
                    f"{basarili_sayisi} personelin çıkışı işlendi. Aktif mevcut ve norm eksik/fazla "
                    f"dengesi yenilendi. Mail: {queued} kuyruğa alındı, {sent} gönderildi, {skipped} atlandı, {failed} hata."
                )
            else:
                st.warning("Hiçbir kayıt işlenemedi — aşağıdaki hataları düzeltip tekrar deneyin.")
            if tum_hatalar:
                st.warning(f"{len(tum_hatalar)} kayıt işlenemedi:\n" + "\n".join(f"• {h}" for h in tum_hatalar[:15]))
            if basarili_sayisi:
                _personel_degisikligi_sonrasi_raporlari_yenile()
                st.rerun()
        except Exception as exc:
            st.error(f"Toplu işten çıkış başarısız: {exc}")


def _sekme_atama(ctx: PageContext, staff, magaza, unvan) -> None:
    st.caption(
        "Aktif bir personelin unvan/mağazasını değiştirin (terfi, rotasyon, görev değişikliği). "
        "İşlemin ardından imzalanabilir bir bildirim belgesi (DOCX+PDF) oluşturulur ve e-postayla gönderilir."
    )
    aktif_mask = staff.apply(lambda r: is_active(r.to_dict()), axis=1)
    aktif = staff[aktif_mask & staff["İsim Soyisim"].notna() & staff["İsim Soyisim"].astype(str).str.strip().ne("")]
    if aktif.empty:
        st.info("Atama işlemi yapılacak aktif personel bulunamadı.")
        return

    etiketler = [f"{r['İsim Soyisim']} — {r.get('Mağaza','')} / {r.get('Unvan','')}" for _, r in aktif.iterrows()]
    secim = st.selectbox("Personel *", etiketler, key="pk_atama_personel")
    secilen_idx = aktif.index[etiketler.index(secim)]
    secilen = staff.loc[secilen_idx]

    with st.container(border=True):
        st.markdown(f"**{secilen['İsim Soyisim']}**")
        st.caption(f"Mevcut: {secilen.get('Unvan','')} · {secilen.get('Mağaza','')}")

    magaza_secenekleri = sorted(magaza["Mağaza"].dropna().astype(str).unique().tolist())
    unvan_secenekleri = sorted(unvan["Unvan"].dropna().astype(str).unique().tolist())
    mevcut_magaza = str(secilen.get("Mağaza", ""))
    mevcut_unvan = str(secilen.get("Unvan", ""))

    with st.form("form_atama"):
        yeni_magaza = st.selectbox(
            "Yeni Mağaza *", magaza_secenekleri,
            index=magaza_secenekleri.index(mevcut_magaza) if mevcut_magaza in magaza_secenekleri else 0,
        )
        yeni_unvan = st.selectbox(
            "Yeni Unvan *", unvan_secenekleri,
            index=unvan_secenekleri.index(mevcut_unvan) if mevcut_unvan in unvan_secenekleri else 0,
        )
        atama_tarihi = st.date_input("Atama Tarihi *", value=date.today())
        ek_alicilar = _ek_alici_secimi(ctx, "pk_atama_ek_alicilar", yeni_magaza, "")
        kaydet = st.form_submit_button("Atamayı Kaydet ve Bildir", type="primary")

    if kaydet:
        if yeni_magaza == mevcut_magaza and yeni_unvan == mevcut_unvan:
            st.error("Yeni mağaza/unvan mevcutla aynı — bir değişiklik seçin.")
            return
        try:
            from services.appointment_lifecycle import create_appointment
            sonuc = create_appointment(
                input_path=ctx.input_path, root=ctx.root, person_name=str(secilen["İsim Soyisim"]),
                staff_index=secilen_idx, staff_df=staff, magaza_df=magaza, unvan_df=unvan,
                source_store=mevcut_magaza, source_title=mevcut_unvan,
                target_store=yeni_magaza, target_title=yeni_unvan,
                planned_date=atama_tarihi, created_by=getattr(ctx, "username", ""),
            )
            atama_no = sonuc["atama_no"]

            if sonuc["status"] == "PLANNED":
                # DÜZELTME (Madde 17): gelecek tarihli atama Fact_Mevcut'a
                # HENÜZ uygulanmadı — bildirim/belge de henüz üretilmez,
                # yalnız planlandığı bilgisi gösterilir.
                st.success(
                    f"{secilen['İsim Soyisim']} için atama PLANLANDI (Atama No: {atama_no}). "
                    f"{atama_tarihi.strftime('%d.%m.%Y')} tarihinde otomatik olarak yürürlüğe girecek; "
                    "o güne kadar mevcut mağaza/unvanı korunur."
                )
                st.rerun()
                return

            # DÜZELTME (Madde 18 — belge tekilleştirme): aynı ATAMA_NO
            # için belge daha önce üretildiyse TEKRAR üretilmez, mevcut
            # dosya kullanılır (services/report_registry.py).
            from services.report_registry import get_or_build
            veri_hash = f"{secilen_idx}_{yeni_magaza}_{yeni_unvan}_{atama_tarihi.isoformat()}"

            def _belge_uret():
                sonuc_belge = create_assignment_notice({
                    "isim_soyisim": str(secilen["İsim Soyisim"]), "yeni_pozisyon": yeni_unvan,
                    "yeni_magaza": yeni_magaza, "onceki_pozisyon": mevcut_unvan, "onceki_magaza": mevcut_magaza,
                    "tarih": atama_tarihi.strftime("%d.%m.%Y"), "onaylayan": getattr(ctx, "username", ""),
                })
                return sonuc_belge["pdf"]

            pdf_yolu, yeniden_uretildi = get_or_build(
                ctx.root, report_type="ATAMA_BILDIRIMI", scope_type="ATAMA_NO", scope_id=atama_no,
                data_version=veri_hash, template_version="V1", format="PDF", builder=_belge_uret,
            )
            kisi_mail = secilen.to_dict()
            kisi_mail.update({
                "Unvan": yeni_unvan, "Mağaza": yeni_magaza, "Önceki Unvan": mevcut_unvan,
                "Önceki Mağaza": mevcut_magaza, "Atama Tarihi": atama_tarihi.strftime("%d.%m.%Y"),
            })
            mail_result = send_personnel_event_mail(
                input_path=ctx.input_path, event="ATAMA", person=kisi_mail, extra_recipients=ek_alicilar,
                attachments=[pdf_yolu],
            )
            if str(mail_result.get("status", "")).startswith(("SENT", "SKIPPED", "QUEUED")):
                st.success(
                    f"{secilen['İsim Soyisim']} için atama uygulandı (Atama No: {atama_no}); "
                    f"bildirim: {mail_result.get('status')}"
                )
            else:
                st.warning(
                    f"Atama uygulandı (Atama No: {atama_no}); e-posta gönderimi başarısız: {mail_result.get('status')}"
                )
            with open(pdf_yolu, "rb") as fh:
                st.download_button("📄 Atama Belgesini İndir (PDF)", fh.read(), file_name=Path(pdf_yolu).name, key="pk_atama_pdf_indir")
            _personel_degisikligi_sonrasi_raporlari_yenile()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"İşlem başarısız: {exc}")


def _sekme_cikis_geri_al(ctx: PageContext, staff) -> None:
    st.caption("Yanlış işlenmiş bir çıkışı geri alır. Personel yeniden aktif olur; mevcut ve norm dengesi yeniden hesaplanır.")
    pasif_mask = ~staff.apply(lambda r: is_active(r.to_dict()), axis=1)
    pasif = staff[pasif_mask & staff["İsim Soyisim"].notna() & staff["İsim Soyisim"].astype(str).str.strip().ne("")]
    if pasif.empty:
        st.info("Geri alınabilecek bir çıkış kaydı bulunamadı.")
        return

    etiketler = [
        f"{r['İsim Soyisim']} — {r.get('Mağaza','')} / {r.get('Unvan','')} — Çıkış: {r.get('İşten Çıkış','')}"
        for _, r in pasif.iterrows()
    ]
    secim = st.selectbox("Geri alınacak çıkış *", etiketler, key="pk_cikis_geri_al_secim")
    secilen_idx = pasif.index[etiketler.index(secim)]
    secilen = staff.loc[secilen_idx]

    with st.container(border=True):
        st.markdown(f"**{secilen['İsim Soyisim']}**")
        st.caption(f"{secilen.get('Unvan','')} · {secilen.get('Mağaza','')} · Çıkış: {secilen.get('İşten Çıkış','')}")
        st.caption(f"Kod/Neden: {secilen.get('Çıkış Kodu','')} / {secilen.get('Çıkış Nedeni','')}")

    ek_alicilar = _ek_alici_secimi(
        ctx, "pk_cikis_geri_al_ek_alicilar", str(secilen.get("Mağaza", "")), str(secilen.get("MağazaID", ""))
    )
    onay = st.checkbox("Bu çıkış kaydını geri alıp personeli yeniden aktif yapmak istiyorum.", key="pk_cikis_geri_al_onay")
    if st.button("Çıkışı Geri Al", type="primary", key="pk_cikis_geri_al_btn"):
        if not onay:
            st.error("Devam etmek için onay kutusunu işaretleyin.")
            return
        try:
            undo_exit(
                input_path=ctx.input_path, root=ctx.root, staff_index=secilen_idx,
                isim_soyisim=str(secilen["İsim Soyisim"]), magaza_id=str(secilen.get("MağazaID", "")),
                kullanici=getattr(ctx, "username", ""),
            )
            mail_result = send_personnel_event_mail(
                input_path=ctx.input_path, event="CIKIS_GERI_ALINDI", person=secilen.to_dict(), extra_recipients=ek_alicilar
            )
            if str(mail_result.get("status", "")).startswith(("SENT", "SKIPPED", "QUEUED")):
                st.success(
                    f"{secilen['İsim Soyisim']} yeniden aktif edildi. Aktif mevcut/norm dengesi güncellendi; "
                    f"bildirim: {mail_result.get('status')}"
                )
            else:
                st.warning(
                    f"{secilen['İsim Soyisim']} yeniden aktif edildi ve hesaplar güncellendi; "
                    f"e-posta gönderimi başarısız: {mail_result.get('status')}"
                )
            _personel_degisikligi_sonrasi_raporlari_yenile()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"İşlem başarısız: {exc}")


def render(ctx: PageContext) -> None:
    st.header("Personel Kartları")

    from services.personnel_permissions import can as _can
    perms = {
        key for key in ("personnel_view", "personnel_entry", "personnel_exit", "personnel_edit")
        if _can(ctx.input_path, ctx.email, key, ctx.role)
    }
    if not perms:
        st.info("Bu kullanıcıya personel ekranı için veri giriş/görüntüleme yetkisi atanmadı.")
        return

    staff, magaza, unvan, cikis_nedeni = load_personnel_view(ctx.input_path)

    tabs = []
    if "personnel_view" in perms:
        tabs.append(("Personel Kartları", lambda: _sekme_kartlar(ctx, staff, magaza, unvan)))
    if "personnel_edit" in perms:
        tabs.append(("Atama / Görev Değişikliği", lambda: _sekme_atama(ctx, staff, magaza, unvan)))
    if "personnel_entry" in perms:
        tabs.append(("Yeni Personel Ekle", lambda: _sekme_yeni_personel(ctx, staff, magaza, unvan)))
        tabs.append(("Toplu İşe Giriş", lambda: _sekme_toplu_yeni_personel(ctx, staff, magaza, unvan)))
    if "personnel_exit" in perms:
        tabs.append(("İşten Çıkış İşlemi", lambda: _sekme_isten_cikis(ctx, staff, cikis_nedeni)))
        tabs.append(("Toplu İşten Çıkış", lambda: _sekme_toplu_isten_cikis(ctx, staff, cikis_nedeni)))
        tabs.append(("Çıkışı Geri Al", lambda: _sekme_cikis_geri_al(ctx, staff)))

    ui_tabs = st.tabs([x[0] for x in tabs])
    for tab, (_, renderer) in zip(ui_tabs, tabs):
        with tab:
            renderer()
