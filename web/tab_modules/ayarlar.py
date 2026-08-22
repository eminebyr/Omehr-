"""Ayarlar sekmesi — gerçek ürün ayar ekranı.

Kapsam ve bilinçli sınırlar için bkz. services/app_settings.py modül
docstring'i. Özetle: burada JSON dosyalarını elle düzenlemek yerine
şirket bilgisi, mail sunucusu, AI özellik anahtarları ve yedekleme
sıklığı web panelinden değiştirilebilir. Parola/güvenlik ayarları,
AI güvenlik tavanları ve "lisans" gibi henüz var olmayan kavramlar
BİLEREK bu ekranın dışında tutuldu.
"""
from __future__ import annotations

import streamlit as st

from web.context import PageContext


def render(ctx: PageContext) -> None:
    """Ayarlar sekmesinin içeriğini çizer."""
    role = ctx.role
    is_global = ctx.is_global
    sheets = ctx.sheets

    if role not in {"ADMIN", "HR_DIRECTOR"}:
        st.info("Bu sekme yalnız Sistem Yöneticisi ve İK Direktörü rolüne açıktır.")
        return

    from services.app_settings import (
        FEATURE_LABELS,
        get_feature_flags,
        get_settings,
        input_file_info,
        set_feature_flags,
        update_settings,
    )
    from services.exceptions import ConfigurationError

    settings = get_settings()

    st.subheader("Şirket bilgisi")
    with st.form("ayarlar_sirket"):
        ad = st.text_input("Şirket adı", value=settings["company"].get("name", ""))
        logo = st.text_input(
            "Logo dosya yolu (isteğe bağlı, PDF/Excel raporlarında kullanılır)",
            value=settings["company"].get("logo_path", ""),
        )
        if st.form_submit_button("Şirket bilgisini kaydet"):
            try:
                update_settings({"company": {"name": ad.strip(), "logo_path": logo.strip()}})
                st.success("Şirket bilgisi kaydedildi.")
                st.rerun()
            except ConfigurationError as exc:
                st.error(f"Kaydedilemedi: {exc}")

    st.divider()
    st.subheader("Mail sunucusu (SMTP)")
    st.caption("Outlook COM kullanılıyorsa bu ayarlara gerek yoktur; yalnız SMTP fallback için geçerlidir.")
    smtp = settings["notifications"]["smtp"]
    with st.form("ayarlar_smtp"):
        c1, c2 = st.columns(2)
        enabled = c1.checkbox("SMTP etkin", value=smtp.get("enabled", False))
        use_tls = c2.checkbox("TLS kullan", value=smtp.get("use_tls", True))
        host = st.text_input("Sunucu (host)", value=smtp.get("host", ""))
        c3, c4 = st.columns(2)
        port = c3.number_input("Port", value=int(smtp.get("port", 587)), min_value=1, max_value=65535)
        smtp_user = c4.text_input("Kullanıcı adı", value=smtp.get("username", ""))
        gonderen = st.text_input("Gönderen adresi (From)", value=smtp.get("from", ""))
        st.caption("Parola buradan görüntülenmez/kaydedilmez; sunucuda OMEHR_SMTP_PASSWORD ortam değişkeni ile tanımlayın.")
        if st.form_submit_button("SMTP ayarlarını kaydet"):
            try:
                update_settings({
                    "notifications": {
                        "smtp": {
                            "enabled": enabled, "use_tls": use_tls, "host": host.strip(),
                            "port": int(port), "username": smtp_user.strip(), "from": gonderen.strip(),
                        }
                    }
                })
                st.success("SMTP ayarları kaydedildi.")
                st.rerun()
            except ConfigurationError as exc:
                st.error(f"Kaydedilemedi: {exc}")

    st.divider()
    st.subheader("AI ve rapor özellikleri")
    st.caption("Kapatılan bir özellik, ilgili sekme/hesaplamayı devre dışı bırakır; AI güvenlik tavanları (ör. 1,20x norm sınırı) burada DEĞİŞTİRİLEMEZ.")
    mevcut_bayraklar = get_feature_flags()
    with st.form("ayarlar_ozellikler"):
        yeni_bayraklar = {}
        for anahtar, etiket in FEATURE_LABELS.items():
            yeni_bayraklar[anahtar] = st.checkbox(etiket, value=mevcut_bayraklar.get(anahtar, True), key=f"feat_{anahtar}")
        if st.form_submit_button("Özellik ayarlarını kaydet"):
            try:
                set_feature_flags(yeni_bayraklar)
                st.success("Özellik ayarları kaydedildi. Bazı değişikliklerin tam etkili olması için sistemin yeniden başlatılması önerilir.")
                st.rerun()
            except ConfigurationError as exc:
                st.error(f"Kaydedilemedi: {exc}")

    st.divider()
    st.subheader("Yedekleme")
    with st.form("ayarlar_yedekleme"):
        max_yedek = st.number_input(
            "Tutulacak input yedeği sayısı",
            value=int(settings["backup"].get("max_backups", 20)),
            min_value=1, max_value=500,
            help="Bu sayıyı aşan en eski yedekler otomatik silinir.",
        )
        if st.form_submit_button("Yedekleme ayarını kaydet"):
            try:
                update_settings({"backup": {"max_backups": int(max_yedek)}})
                st.success("Yedekleme ayarı kaydedildi.")
                st.rerun()
            except ConfigurationError as exc:
                st.error(f"Kaydedilemedi: {exc}")

    st.divider()
    st.subheader("Bildirim eşiği")
    with st.form("ayarlar_bildirim"):
        esik = st.number_input(
            "Kritik norm eksiği eşiği (bu sayıyı aşan mağazalar kritik sayılır)",
            value=int(settings["notifications"].get("critical_deficit_threshold", 5)),
            min_value=1, max_value=1000,
        )
        webhook = st.text_input("Teams webhook URL (isteğe bağlı)", value=settings["notifications"].get("teams_webhook_url", ""))
        if st.form_submit_button("Bildirim ayarını kaydet"):
            try:
                update_settings({"notifications": {"critical_deficit_threshold": int(esik), "teams_webhook_url": webhook.strip()}})
                st.success("Bildirim ayarı kaydedildi.")
                st.rerun()
            except ConfigurationError as exc:
                st.error(f"Kaydedilemedi: {exc}")

    st.divider()
    st.subheader("Salt okunur bilgiler")

    info = input_file_info()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Ana input dosyası**")
        st.code(info["file_name"])
        st.caption(
            "✅ Dosya bulundu" if info["exists"] else "⚠️ Dosya bulunamadı"
        )
        st.caption(
            "Dosya adını değiştirmek için services/settings.py veya "
            "OMEHR_INPUT_FILE ortam değişkeni kullanılır (sistem "
            "yöneticisi işlemi, yeniden başlatma gerektirir)."
        )
    with c2:
        st.markdown("**Rapor alıcıları**")
        st.caption(
            "Rapor ve bildirim alıcıları, çift kaynak oluşmaması için "
            "burada değil, input dosyasındaki **Mail_Listesi** sayfasında "
            "yönetilir."
        )
        ml = sheets.get("Mail_Listesi")
        if ml is not None and not ml.empty:
            st.caption(f"Şu an tanımlı: {len(ml)} kayıt")
        else:
            st.caption("Mail_Listesi sayfası okunamadı.")

    from services.personnel_permissions import can as _can_permission
    _email_l = str(ctx.email or "").strip().casefold()
    if _can_permission(ctx.input_path, _email_l, "permissions_admin", role):
        st.divider()
        st.subheader("Kullanıcı veri giriş yetkileri")
        st.caption("Bu yetkiler merkezi Excel dosyasının yanında saklanır; aynı Excel'i kullanan tüm PC'lerde aynıdır.")
        from services.personnel_permissions import PERMISSIONS, load_permissions, save_user_permissions
        ml = sheets.get("Mail_Listesi")
        emails = []
        if ml is not None and not ml.empty:
            email_col = next((c for c in ("E-posta", "Email") if c in ml.columns), None)
            if email_col:
                emails = sorted({str(x).strip().casefold() for x in ml[email_col].dropna() if "@" in str(x)})
        if emails:
            current = load_permissions(ctx.input_path)
            with st.form("kullanici_veri_yetkileri"):
                target = st.selectbox("Kullanıcı", emails)
                selected = []
                existing = set(current.get(target.casefold(), []))
                cols = st.columns(2)
                for i, (key, label) in enumerate(PERMISSIONS.items()):
                    if cols[i % 2].checkbox(label, value=key in existing, key=f"perm_{target}_{key}"):
                        selected.append(key)
                if st.form_submit_button("Kullanıcı yetkilerini kaydet", type="primary"):
                    save_user_permissions(ctx.input_path, {target: selected})
                    st.success(f"{target} yetkileri kaydedildi. Diğer PC'ler sonraki yenilemede aynı yetkiyi kullanır.")
                    st.rerun()
        else:
            st.caption("Mail_Listesi'nde e-posta adresi bulunan aktif kullanıcı yok.")
        st.caption(
            "Varsayılan: Sistem Yöneticisi/İK Direktörü rolündeki kullanıcılar tam yetkilidir; "
            "diğerleri yalnız görüntüleme yapabilir. Belirli bir kullanıcıyı yukarıdan özelleştirebilirsiniz."
        )

    if not is_global:
        return  # bölge kullanıcıları buradan sonrasını (aşağıda tenant bilgisi) görmez

    st.divider()
    st.subheader("Kiracı (tenant) bilgisi")
    try:
        from services.tenant_manager import registry

        for kod, bilgi in registry().get("tenants", {}).items():
            st.caption(f"**{kod}** — {bilgi.get('name', '')} — {'aktif' if bilgi.get('active') else 'pasif'}")
    except Exception:
        st.caption("Kiracı kaydı okunamadı.")

    st.caption(
        "Lisans/abonelik bilgisi bu sürümde henüz bir kavram olarak "
        "yok — bu ekrana eklenmesi önce bir ürün kararı gerektirir."
    )

    st.divider()
    st.subheader("Excel Verisi Yükle")
    st.caption(
        "Kalıcı bir dosya sisteminin olmadığı dağıtımlarda (ör. ücretsiz "
        "bulut barındırma) ana Excel dosyanızı buradan yükleyebilirsiniz."
    )
    yuklenen_dosya = st.file_uploader(
        "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx (ya da kendi şirketinizin aynı yapıdaki dosyası)",
        type=["xlsx"], key="excel_yukleme",
    )
    if yuklenen_dosya is not None and st.button("Yükle ve etkinleştir", key="excel_yukle_dugmesi"):
        import tempfile
        from pathlib import Path as _Path
        from common_veri_okuma import _db_modu

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as _tmp:
            _tmp.write(yuklenen_dosya.getvalue())
            _gecici_yol = _Path(_tmp.name)
        try:
            # DÜZELTME (KRİTİK — bizzat canlıda bulundu, 20.08.2026): bu ekran
            # önceden KOŞULSUZ migrate_excel_to_db() çağırıyordu (veriyi HER
            # ZAMAN veritabanına yazıyordu). Ama dashboard'un gerçek okuma
            # yolu (common_veri_okuma.read_all -> _db_modu()) yalnız
            # OMEHR_INPUT_SOURCE=db İKEN veritabanını okur; dosya modunda
            # (OMEHR_INPUT_SOURCE=excel) dashboard doğrudan input DOSYASINI
            # okur. Sonuç: "X/Y sayfa başarıyla aktarıldı" mesajı doğruydu
            # ama veri dashboard'un hiç bakmadığı bir yere yazılıyordu —
            # dashboard sonsuza dek eski veriyi gösterirdi. Artık gerçek
            # moda göre doğru hedefe yazılıyor.
            if _db_modu():
                from services.input_excel_migration import migrate_excel_to_db
                from services.multitenant.tenant_context import current_tenant_id
                with st.spinner("Excel veritabanına aktarılıyor, bu birkaç saniye sürebilir..."):
                    _sonuc = migrate_excel_to_db(
                        str(_gecici_yol), kullanici=getattr(ctx, "username", "web"), tenant_id=current_tenant_id(),
                    )
                _basarili = sum(1 for v in _sonuc.values() if v.get("durum") == "OK")
                st.success(f"{_basarili}/{len(_sonuc)} sayfa başarıyla veritabanına aktarıldı.")
            else:
                from services.runtime_paths import runtime_root
                from services.settings import input_path as _input_path_helper
                _hedef = _input_path_helper(runtime_root())
                _hedef.parent.mkdir(parents=True, exist_ok=True)
                import shutil as _shutil
                _shutil.copyfile(_gecici_yol, _hedef)
                st.success(f"Dosya etkinleştirildi: {_hedef.name} (dashboard artık bu veriyi kullanacak).")
            st.cache_data.clear()
        except Exception as _exc:
            st.error(f"Aktarım başarısız: {_exc}")
        finally:
            _gecici_yol.unlink(missing_ok=True)
