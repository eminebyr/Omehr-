"""Raporlar sekmesi.

Bu modül, web/app.py içindeki eski "with tabs[N]:" bloğundan otomatik
olarak çıkarılmıştır. Kod davranışı değiştirilmeden taşınmıştır; tüm
paylaşılan durum (sheets, kullanıcı/rol bilgisi, fm/detail/stores/kpis,
servis fonksiyonları) web.context.PageContext üzerinden gelir.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

from web.context import PageContext
from services.safe_exec import log_swallowed


def render(ctx: PageContext) -> None:
    """Raporlar sekmesinin içeriğini çizer."""
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

    def _log_indirme(dosya_adi: str) -> None:
        # KVKK — DENETLENEBİLİRLİK: raporlarda personel adı/adres/performans
        # gibi kişisel veriler bulunduğu için, HANGİ kullanıcının HANGİ
        # raporu NE ZAMAN indirdiği kalıcı olarak kaydedilir.
        try:
            from services.download_audit import kaydet as _kaydet_indirme
            _kaydet_indirme(username, dosya_adi, role)
        except Exception as _exc:
            log_swallowed("web.tab_modules.raporlar._log_indirme: beklenmeyen hata", _exc)
            pass
    st.subheader("PDF ve Excel Rapor Merkezi")
    st.caption("Yönetici, bölge ve analiz raporlarını burada yeniden üretin, indirin veya kontrollü biçimde Outlook/SMTP ile gönderin.")

    a1, a2, a3 = st.columns([1, 1, 1])
    if a1.button("🔄 PDF ve Excel raporlarını yeniden üret", use_container_width=True, key="rapor_yeniden_uret"):
        with st.spinner("Input Excel yeniden hesaplanıyor ve tüm raporlar üretiliyor..."):
            try:
                job_id, ok, error = _enqueue_and_process("RUN_REPORTS", {}, tenant_code(), timeout=360)
                if ok:
                    read_input.clear()
                    st.success("PDF ve Excel raporları başarıyla yenilendi.")
                    st.rerun()
                elif ok is None:
                    st.warning(error)
                else:
                    st.error(f"Rapor üretimi başarısız: {error}")
            except Exception as exc:
                st.error(f"Rapor üretimi başarısız: {exc}")

    _raporlar = sorted(
        [p for p in OUTPUT.rglob("*") if p.is_file() and p.suffix.lower() in {".pdf", ".xlsx", ".xlsm"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    a2.metric("Hazır rapor", len(_raporlar))
    a3.metric("Son güncelleme", _raporlar[0].stat().st_mtime_ns and pd.to_datetime(_raporlar[0].stat().st_mtime, unit="s").strftime("%d.%m.%Y %H:%M") if _raporlar else "—")

    if not _raporlar:
        st.warning("Henüz PDF/Excel raporu yok. Yukarıdaki 'yeniden üret' düğmesini kullanın.")
    else:
        _ana = [p for p in _raporlar if p.parent == OUTPUT]
        _bolge = [p for p in _raporlar if p.parent != OUTPUT]
        st.markdown("#### Yönetici ve ana raporlar")
        for pth in _ana:
            c1, c2, c3 = st.columns([4, 1.2, 1.4])
            c1.write(f"**{pth.name}**")
            c2.caption(f"{pth.stat().st_size/1024/1024:.1f} MB")
            c3.download_button(
                "İndir", pth.read_bytes(), file_name=pth.name,
                use_container_width=True, key=f"indir_{pth.name}_{pth.stat().st_mtime_ns}",
                on_click=_log_indirme, args=(pth.name,),
            )
        if _bolge:
            with st.expander(f"Bölge/şube raporları ({len(_bolge)})", expanded=False):
                for pth in _bolge:
                    if is_global or norm_text(scope) in norm_text(pth.stem):
                        st.download_button(
                            f"{pth.relative_to(OUTPUT)} indir", pth.read_bytes(), file_name=pth.name,
                            use_container_width=True, key=f"indir_alt_{pth.relative_to(OUTPUT)}_{pth.stat().st_mtime_ns}",
                            on_click=_log_indirme, args=(pth.name,),
                        )

        st.markdown("#### Outlook / SMTP ile rapor gönderimi")
        _secilebilir = {p.name: p for p in _ana}
        _varsayilan = [n for n in _secilebilir if n.lower().endswith((".pdf", ".xlsx"))][:2]
        _ekler = st.multiselect("Gönderilecek raporlar", list(_secilebilir), default=_varsayilan, key="rapor_mail_ekleri")
        _alici = st.text_input("Alıcılar (; ile ayırın)", value=email if email and "@" in email else "", key="rapor_mail_alici")
        _konu = st.text_input("Konu", value="OMEHR Norm Kadro ve İş Gücü Raporları", key="rapor_mail_konu")
        _govde = st.text_area("E-posta metni", value="Merhaba,\n\nGüncel norm kadro ve iş gücü raporları ekte sunulmuştur.\n\nİyi çalışmalar.", height=150, key="rapor_mail_govde")
        _onay = st.checkbox("Alıcıları ve ekleri kontrol ettim; gönderimi onaylıyorum", key="rapor_mail_onay")
        if st.button("📧 Seçili raporları gönder", disabled=not _onay, use_container_width=True, key="rapor_mail_gonder"):
            recipients = [x.strip() for x in _alici.replace(",", ";").split(";") if x.strip()]
            attachments = [str(_secilebilir[n]) for n in _ekler if n in _secilebilir]
            if not recipients:
                st.error("En az bir geçerli alıcı girin.")
            elif not attachments:
                st.error("En az bir PDF veya Excel raporu seçin.")
            else:
                job_id, ok, error = _enqueue_and_process(
                    "SEND_EMAIL",
                    {"subject": _konu, "body": _govde, "recipients": recipients, "attachments": attachments, "report_type": "WEB_REPORT_CENTER"},
                    tenant_code(), timeout=120,
                )
                if ok:
                    st.success("Rapor e-postası gönderildi.")
                elif ok is None:
                    st.warning(error)
                else:
                    st.error(f"Gönderim başarısız: {error}")

    st.markdown("---")
    st.markdown("#### Power BI'a Hazır Model")
    st.caption(
        "Dim_Magaza/Dim_Unvan/Fact_Norm/Fact_Mevcut sayfalarını, Power BI "
        "Desktop'ta doğrudan bağlanabileceğiniz TEMİZ bir star şemaya "
        "dönüştürür: yinelenen Dim satırları tekilleştirilir, ID sütunları "
        "ilişkiler için tutarlı metne sabitlenir, Dim tablosunda karşılığı "
        "olmayan (yetim) kayıtlar sessizce atılmaz, ayrı bir sayfada "
        "raporlanır. Bir takvim (Dim_Tarih) boyutu ve ilişki rehberi de "
        "eklenir. Bu, veriyi Power BI'a OTOMATİK GÖNDERMEZ — üretilen "
        "dosyayı Power BI Desktop'ta 'Veri Al > Excel' ile açıp "
        "bağlamanız gerekir."
    )
    if st.button("📊 Power BI modelini üret", key="powerbi_uret"):
        try:
            from services.powerbi_export import export_powerbi_workbook
            _sonuc = export_powerbi_workbook(sheets, OUTPUT)
            st.session_state["powerbi_sonuc"] = _sonuc
            st.success(
                f"Model üretildi: {_sonuc['dim_magaza_sayisi']} mağaza, "
                f"{_sonuc['dim_unvan_sayisi']} unvan, "
                f"{_sonuc['fact_norm_sayisi']} norm satırı, "
                f"{_sonuc['fact_mevcut_sayisi']} personel satırı."
            )
            if _sonuc["yetim_norm_sayisi"] or _sonuc["yetim_mevcut_sayisi"]:
                st.warning(
                    f"⚠️ {_sonuc['yetim_norm_sayisi']} Fact_Norm ve "
                    f"{_sonuc['yetim_mevcut_sayisi']} Fact_Mevcut satırı, "
                    "Dim_Magaza/Dim_Unvan'da karşılığı olmadığı için modele "
                    "dahil edilmedi — bu satırlar üretilen dosyadaki "
                    "Yetim_Kayitlar_* sayfalarında listeleniyor, kaynak "
                    "Excel'de düzeltilmesi önerilir."
                )
        except Exception as _exc:
            log_swallowed("web.tab_modules.raporlar.powerbi_uret: beklenmeyen hata", _exc)
            st.error(f"Power BI modeli üretilemedi: {_exc}")
    _powerbi_sonuc = st.session_state.get("powerbi_sonuc")
    if _powerbi_sonuc and Path(_powerbi_sonuc["file"]).is_file():
        st.download_button(
            "Power BI modelini indir (OMEHR_PowerBI_Model.xlsx)",
            Path(_powerbi_sonuc["file"]).read_bytes(),
            file_name=Path(_powerbi_sonuc["file"]).name,
            use_container_width=True,
            on_click=_log_indirme, args=("OMEHR_PowerBI_Model.xlsx",),
        )

    if can_view_personal_address:
        st.markdown("---")
        st.markdown("#### Yedekleme ve Geri Yükleme (yalnız İK/Admin)")
        with st.expander("📥 İndirme Denetim Kaydı (KVKK — kişisel veri içeren raporları kim indirdi)"):
            try:
                from services.download_audit import son_kayitlar as _indirme_kayitlari
                _kayitlar = _indirme_kayitlari(200)
                if _kayitlar:
                    st.dataframe(pd.DataFrame(_kayitlar)[["zaman", "kullanici", "rol", "dosya_adi"]], use_container_width=True, hide_index=True)
                else:
                    st.caption("Henüz hiç indirme kaydedilmedi.")
            except Exception:
                st.caption("İndirme kayıtları okunamadı.")
        st.caption(
            "Input dosyası her açılışta otomatik olarak zaman damgalı yedeklenir "
            "(son 20 yedek saklanır). Bir sorun olursa aşağıdan eski bir sürüme dönebilirsiniz."
        )
        try:
            from services.backup import list_backups, restore_backup
            yedekler = list_backups(INPUT)
        except Exception as _exc:
            log_swallowed("web.tab_modules.raporlar._log_indirme: beklenmeyen hata", _exc)
            yedekler = []
        if not yedekler:
            st.info("Henüz bir yedek oluşmadı.")
        else:
            secenekler = {p.name: p for p in yedekler}
            secili_ad = st.selectbox("Geri yüklenecek yedek", list(secenekler), key="yedek_secim")
            if st.button("⚠️ Seçili yedeği geri yükle (mevcut dosyanın üzerine yazar)", key="yedek_geri_yukle"):
                st.session_state["yedek_onay_bekliyor"] = secenekler[secili_ad]
            if st.session_state.get("yedek_onay_bekliyor"):
                st.warning(f"'{st.session_state['yedek_onay_bekliyor'].name}' dosyası geri yüklenecek, bu işlem GERİ ALINAMAZ. Emin misiniz?")
                oc1, oc2 = st.columns(2)
                if oc1.button("Evet, geri yükle", key="yedek_onay_evet"):
                    if restore_backup(st.session_state["yedek_onay_bekliyor"], INPUT, kullanici=username):
                        st.success("Yedek geri yüklendi. Sayfa yenileniyor...")
                        del st.session_state["yedek_onay_bekliyor"]
                        read_input.clear()
                        st.rerun()
                    else:
                        st.error("Geri yükleme başarısız oldu.")
                if oc2.button("Vazgeç", key="yedek_onay_hayir"):
                    del st.session_state["yedek_onay_bekliyor"]
                    st.rerun()

