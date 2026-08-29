from __future__ import annotations

import json
import math
import os
import sqlite3
import subprocess
import sys
import time
from services.excel_read_shim import install as _install_excel_read_shim
_install_excel_read_shim()
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import openpyxl
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
from services.runtime_paths import runtime_root
from services.dashboard_model import build_dashboard_model, active_people as dashboard_active_people, CONTROL_FILENAME
from services.security import migrate_legacy_input, set_password, password_error
from services.home_proximity import refresh_home_proximity, maps_route
from services.web_runtime import connect_web_db as db, log_web_action as log
from services.job_queue import enqueue, status as job_status
from services.runtime_paths import tenant_code
from services.tenant_context import current_tenant_id, set_session_tenant
from services.input_data_access import input_source
from services.settings import input_path
from web.display_text import MAIN_TITLE
from web.queue_utils import _enqueue_without_waiting
def _root():
    return runtime_root()


def _input():
    return input_path(_root())


def _output():
    return _root() / "output"


def _db():
    return _root() / "data" / "v16_management.db"


def _input_version(tenant_id: str = "") -> float:
    """Excel için mtime, DB için kiracıya özgü monoton içerik sürümü."""
    if input_source() == "db":
        from services.input_data_access import tenant_content_version
        return float(tenant_content_version(tenant_id or None))
    return _input().stat().st_mtime


# DÜZELTME (tutarlılık — services/*.py ve src/*.py'de düzeltilen aynı
# desen): önceki modül-seviyesi anlık görüntü ataması KALDIRILDI —
# aşağıdaki TÜM kullanım yerleri artık _root()/_input()/_output()/_db()
# fonksiyonlarını DOĞRUDAN çağırıyor, her seferinde taze çözümleniyor.

# DÜZELTME (çok kiracılı SaaS): önceden burada 3 SABİT, gerçek bir
# firmaya (@omehrmarket.com) ait e-posta adresi onay yetkisi verirdi —
# ÇOK KİRACILI bir SaaS'ta bu, hem başka kiracıların gerçek yöneticileri
# için hiçbir işe yaramaz (adresleri asla eşleşmez) hem de mimari olarak
# yanlıştır (paylaşılan kodun içine tek bir firmanın e-postaları
# gömülmemelidir). can_approve zaten role tabanlı (HR_DIRECTOR/ADMIN/
# CEO/EXECUTIVE/MANAGEMENT + Onay Seviyesi>=2) kontrolle çalışıyor — bu
# GENEL, kiracıdan bağımsız yol tek başına yeterli ve doğru olandır.
APPROVERS: set[str] = set()

st.set_page_config(page_title="OMEHR Norm Kadro, Transfer ve İş Gücü Optimizasyon Platformu", page_icon="📊", layout="wide")

# GÜNLÜK OTOMATİK RAPOR ZAMANLAYICI (bkz. services/scheduler.py docstring'i):
# @st.cache_resource, bu fonksiyonu Streamlit SÜRECİ başına yalnızca BİR KEZ
# çalıştırır — sayfa yenilemelerinde veya yeni kullanıcı oturumlarında tekrar
# tekrar thread açılmaz. Varsayılan saatler 10:00 ve 17:15; OMEHR_REPORT_
# SCHEDULE_TIMES ortam değişkeniyle özelleştirilebilir.
@st.cache_resource
def _omehr_baslat_rapor_zamanlayici():
    from services.scheduler import start_daily_report_scheduler
    start_daily_report_scheduler()
    return True


_omehr_baslat_rapor_zamanlayici()

# Tüm Plotly grafiklerinde dışarı aktarma, büyütme/küçültme ve görünüm
# sıfırlama araçlarını görünür tut. Mevcut grafik kodları ve veriler değişmez.
_PLOTLY_MODEBAR_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
    "modeBarButtonsToAdd": [
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
        "toImage",
    ],
}

try:
    from streamlit.delta_generator import DeltaGenerator

    _ORIGINAL_PLOTLY_CHART = DeltaGenerator.plotly_chart

    def _plotly_chart_with_toolbar(self, figure_or_data, *args, **kwargs):
        existing = kwargs.get("config") or {}
        merged = dict(_PLOTLY_MODEBAR_CONFIG)
        merged.update(existing)
        existing_buttons = list(existing.get("modeBarButtonsToAdd", []))
        merged["modeBarButtonsToAdd"] = list(dict.fromkeys(
            _PLOTLY_MODEBAR_CONFIG["modeBarButtonsToAdd"] + existing_buttons
        ))
        kwargs["config"] = merged
        return _ORIGINAL_PLOTLY_CHART(self, figure_or_data, *args, **kwargs)

    DeltaGenerator.plotly_chart = _plotly_chart_with_toolbar
except (ImportError, AttributeError):
    # Eski/özel Streamlit dağıtımlarında uygulamanın açılmasını engelleme.
    pass


def _render_main_title() -> None:
    """OMEHR marka logosu — V19.21.28 güvenli dikey boşluk davranışı korunur.

    DÜZELTME: önceden use_container_width=True ile TAM SAYFA genişliğine
    yayılıyordu — geniş ekranlarda logo aşırı büyük görünüyordu (özellikle
    giriş sonrası ana ekranlarda). Artık dar, ortalanmış bir sütuna
    sığdırılıyor.
    """
    title_asset = CODE_ROOT / "web" / "assets" / "omehr_logo.png"
    st.markdown('<div class="omehr-title-top-gap"></div>', unsafe_allow_html=True)
    _sol, _orta, _sag = st.columns([1, 2, 1])
    with _orta:
        st.image(str(title_asset), use_container_width=True)
    st.markdown('<div class="omehr-title-gap"></div>', unsafe_allow_html=True)


from web.styles import get_theme_css
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
st.markdown(get_theme_css(st.session_state["dark_mode"]), unsafe_allow_html=True)

BD_RENK = {
    # DÜZELTME (marka değişikliği): eski "Çam & Amber" -> OMEHR lacivert/teal.
    "primary": "#102F64", "primary_light": "#1B4A7A", "accent": "#118B94",
    "danger": "#9B2D2D", "success": "#2F7A4F", "ink": "#1A2233", "muted": "#5B8CA0",
}
px.defaults.color_discrete_sequence = ["#102F64", "#118B94", "#D5A95C", "#9B2D2D", "#5B8CA0", "#2F7A4F"]
px.defaults.color_continuous_scale = ["#F5F7F9", "#118B94", "#102F64"]


from web.formatting import norm_text, tr_number, tr_money_compact
from services.safe_exec import log_swallowed

@st.cache_data(show_spinner=False)
def read_input(mtime: float, tenant_id: str = ""):
    import zipfile
    from services.exceptions import WorkbookError

    try:
        # DÜZELTME (kritik önbellek hatası): bu fonksiyon st.cache_data ile
        # önbelleğe alınır — Streamlit'in önbelleği İŞLEM GENELİNDEDİR, tek
        # bir oturuma özel DEĞİLDİR. Önceden önbellek anahtarı yalnızca
        # dosya değişiklik zamanıydı (mtime); OMEHR_INPUT_SOURCE=db
        # modunda iki farklı kiracının referans yol mtime'ı ÇAKIŞIRSA
        # (gerçekçi bir olasılık), Streamlit BİR kiracının önbelleğe
        # alınmış verisini BAŞKA bir kiracıya sessizce sunabilirdi — ciddi
        # bir çok-kiracılı veri sızıntısı riski. tenant_id artık AÇIKÇA
        # önbellek anahtarının bir parçası; çağıran (aşağıda) bunu her
        # zaman services.tenant_context.current_tenant_id() ile doldurur.
        from common_veri_okuma import read_all as _read_all_input
        return _read_all_input(_input())
    except (zipfile.BadZipFile, EOFError) as exc:
        # Bu hata, .xlsx dosyasının içindeki zip arşivinin YARIM/BOZUK
        # olduğu anlamına gelir — en sık nedeni: dosya OneDrive/bulut
        # senkronizasyonunda "yalnız çevrimiçi" bir yer tutucu olarak
        # duruyor (tam indirilmemiş), veya kopyalama/kayıt sırasında
        # kesintiye uğramış. Ham Python hata izi yerine kullanıcıya
        # doğrudan ne yapması gerektiğini söyleyen net bir mesaj veriyoruz.
        raise WorkbookError(
            f"Input dosyası ({_input().name}) açılamadı — dosya bozuk veya eksik görünüyor.\n\n"
            "En sık nedenler:\n"
            "1) Dosya OneDrive/bulut senkronizasyonunda 'yalnız çevrimiçi' bir yer "
            "tutucu olabilir — dosyaya sağ tıklayıp 'Bu cihazda her zaman tut' seçin "
            "ve tam indirilmesini bekleyin.\n"
            "2) Dosya kopyalanırken/kaydedilirken kesintiye uğramış olabilir — "
            "Excel'de açıp 'Farklı Kaydet' ile aynı konuma yeniden kaydedin.\n"
            "3) Dosya hâlâ Excel'de açık ve kaydedilmemiş olabilir."
        ) from exc


def active_people(frame):
    return dashboard_active_people(frame)


def _build_model_from_sheets(sheets):
    fm, detail, stores, kpis = build_dashboard_model(sheets, _root() / "reference" / CONTROL_FILENAME)
    # ÖNEMLİ: build_dashboard_model'in kendi kpis hesaplaması, engine_core.py'de
    # (main.py / testler / tüm raporlar) titizlikle doğrulanan resmi Norm
    # Eksiği/Fazlası mantığından TAMAMEN AYRI, eski bir kalibrasyon (Kalibrasyon/
    # NORM_KAPSAM_BAZI.json) yöntemi kullanıyordu. Bu yüzden ekranın en üstündeki
    # KPI kartları (Aktif Mevcut/Toplam Norm/Norm Eksiği/Norm Fazlası/Net İhtiyaç)
    # main.py'nin ürettiği resmi rakamlarla TUTARSIZ görünüyordu. Aşağıda bu 5
    # kart, tek doğru kaynak olan engine_core.py'nin state()/kpis() çıktısıyla
    # değiştirilir; "detail"/"stores"/"fm" ise diğer sekmelerde (ısı haritaları,
    # transfer önerileri) kullanıldığı için olduğu gibi bırakılır.
    try:
        import sys as _sys
        _sys.path.insert(0, str(_root() / "src"))
        import engine_core as _ec
        _p, _sheets2, _norm, _staff, _h = _ec.load()
        _st, _tt = _ec.state(_norm, _staff, _sheets2)
        # KPI kartları, mağaza/unvan detayları ve transfer sekmeleri aynı resmi
        # state çıktısını kullanır; ikinci bir eski dashboard hesabı kalmaz.
        #
        # engine_core şeması raporlama adlarını kullanır:
        #   Aktif Mevcut / Norm Kadro / Norm Eksiği / Norm Fazlası
        # Web sekmeleri ise tarihsel olarak şu kısa adları bekler:
        #   Mevcut / Norm / Eksik / Fazla
        # Her iki ad grubunu birlikte taşıyarak bütün sekmeleri aynı Python
        # hesabına bağlarız. Böylece LibreOffice/Excel formül önbelleğine bağlı
        # kalmadan Genel Özet dahil tüm sayfalar aynı 48/37 sonucunu kullanır.
        fm = _staff.copy()
        detail = _tt.copy()
        stores = _st.copy()
        _aliases = {
            "Aktif Mevcut": "Mevcut",
            "Norm Kadro": "Norm",
            "Norm Eksiği": "Eksik",
            "Norm Fazlası": "Fazla",
        }
        for _df in (detail, stores):
            for _source, _target in _aliases.items():
                if _source in _df.columns:
                    _df[_target] = pd.to_numeric(_df[_source], errors="coerce").fillna(0).astype(int)
        kpis = _ec.kpis(_st)
    except Exception as _exc:
        log_swallowed("web.app.build_model: beklenmeyen hata", _exc)
        pass  # engine_core çalışmazsa eski (dashboard_model) kpis ile devam et
    return fm, detail, stores, kpis


@st.cache_data(show_spinner=False)
def build_model_cached(mtime: float, tenant_id: str = ""):
    """Input değişmediği sürece ağır dashboard/model hesabını tekrar çalıştırmaz.
    DÜZELTME: tenant_id artık AÇIKÇA önbellek anahtarının parçası ve
    read_input()'a da geçirilir — aksi halde çok kiracılı modda bu
    fonksiyon da read_input() ile AYNI kiracılar-arası önbellek sızıntısı
    riskini taşırdı (bkz. read_input() üzerindeki not)."""
    cached_sheets = read_input(mtime, tenant_id=tenant_id)
    return _build_model_from_sheets(cached_sheets)


from web.accounts import (
    accounts, verify_password, transfer_recipients,
)


from web.transfers import cancel_transfer_request, redirect_transfer_request
from web.context import PageContext
from web.tab_modules import (
    genel_ozet, ceo_ozet, bolge_magaza, unvan_analizi,
    transfer_optimizasyon, transfer_merkezi, onaylar, raporlar,
    toplu_mail, isgucu_tahmini, ai_operasyon, operasyon_gorselleri,
    verimlilik_gorselleri, performans, ai_geri_bildirim, bildirimler,
    veri_toplama, ayarlar,
    ana_veri_yonetimi,
    personel_kartlari,
    tum_sayfalar_veri_yonetimi,
)



def bulk_branch_mail_panel(sheet_frames, current_user):
    """Webden seçilen sınırsız sayıdaki şubeye ayrı Outlook iletisi kuyruğa alır."""
    st.subheader("Şubelere Toplu Mail")
    st.caption("10, 15 veya tüm şubeleri seçebilirsiniz. Her şubeye ayrı mail gider; alıcılar birbirini görmez.")
    branch=sheet_frames.get("Sube_Mail_Listesi",pd.DataFrame()).copy()
    if branch.empty:
        st.error("Sube_Mail_Listesi bulunamadı."); return
    store_col=next((c for c in ("Mağaza","Magaza") if c in branch.columns),None)
    email_col=next((c for c in ("Mağaza E-posta","E-posta","Email") if c in branch.columns),None)
    id_col=next((c for c in ("MağazaID","MagazaID") if c in branch.columns),None)
    name_col=next((c for c in ("Alıcı Adı","Alici Adi") if c in branch.columns),None)
    if not store_col or not email_col:
        st.error("Şube mail listesinde Mağaza ve Mağaza E-posta sütunları bulunamadı."); return
    if "Aktif" in branch.columns:
        branch=branch[branch["Aktif"].astype(str).map(norm_text).isin({"EVET","E","YES","1","TRUE","AKTIF"})]
    branch=branch[branch[email_col].astype(str).str.contains("@",na=False)].copy()
    norm_frame=sheet_frames.get("Fact_Norm",pd.DataFrame())
    if not norm_frame.empty and {"Mağaza","Bölge Sorumlusu"}.issubset(norm_frame.columns):
        region_map=(norm_frame[["Mağaza","Bölge Sorumlusu"]].dropna()
                    .drop_duplicates("Mağaza").assign(_key=lambda x:x["Mağaza"].map(norm_text))
                    .set_index("_key")["Bölge Sorumlusu"].to_dict())
        branch["Bölge"]=branch[store_col].map(lambda x:region_map.get(norm_text(x),"Bölge bilgisi yok"))
    else:
        branch["Bölge"]="Bölge bilgisi yok"
    branch["_label"]=branch.apply(
        lambda r:f"{r.get(store_col,'')} | {r.get(id_col,'') if id_col else ''} | {r.get(email_col,'')}",axis=1
    )
    regions=["TÜM BÖLGELER"]+sorted(branch["Bölge"].dropna().astype(str).unique().tolist())
    selected_region=st.selectbox("Bölge filtresi",regions,key="bulk_mail_region")
    filtered=branch if selected_region=="TÜM BÖLGELER" else branch[branch["Bölge"].astype(str).eq(selected_region)]
    options=filtered["_label"].tolist()
    if "bulk_mail_selected" in st.session_state:
        st.session_state["bulk_mail_selected"]=[x for x in st.session_state["bulk_mail_selected"] if x in options]
    b1,b2,b3=st.columns(3)
    if b1.button("Filtredeki tümünü seç",use_container_width=True):
        st.session_state["bulk_mail_selected"]=options; st.rerun()
    if b2.button("Seçimi temizle",use_container_width=True):
        st.session_state["bulk_mail_selected"]=[]; st.rerun()
    b3.metric("Filtredeki şube",len(options))
    selected=st.multiselect(
        "Mail gönderilecek şubeleri işaretleyin",
        options,
        key="bulk_mail_selected",
        placeholder="Şube adı yazarak arayın ve seçim yapın",
    )
    st.info(f"Seçilen şube sayısı: {len(selected)}")
    subject=st.text_input("Mail konusu",key="bulk_mail_subject")
    message=st.text_area(
        "Mail metni",
        height=180,
        key="bulk_mail_body",
        help="Kullanılabilir alanlar: {MAGAZA}, {MAGAZA_ID}, {ALICI_ADI}, {TARIH}, {SAAT}",
    )
    uploads=st.file_uploader("Ek dosyalar (isteğe bağlı)",accept_multiple_files=True,key="bulk_mail_files")
    chosen=branch[branch["_label"].isin(selected)].copy()
    with st.expander("Alıcı önizlemesi",expanded=bool(selected)):
        preview_cols=[c for c in [id_col,store_col,email_col,"Bölge"] if c]
        st.dataframe(chosen[preview_cols],use_container_width=True,hide_index=True)
        if message and not chosen.empty:
            sample=chosen.iloc[0]
            sample_text=(message.replace("{MAGAZA}",str(sample.get(store_col,"")))
                         .replace("{MAGAZA_ID}",str(sample.get(id_col,"") if id_col else ""))
                         .replace("{ALICI_ADI}",str(sample.get(name_col,"Yetkili") if name_col else "Yetkili"))
                         .replace("{TARIH}",datetime.now().strftime("%d.%m.%Y"))
                         .replace("{SAAT}",datetime.now().strftime("%H:%M")))
            st.text_area("Örnek kişiselleştirilmiş mesaj",sample_text,height=140,disabled=True)
    confirmed=st.checkbox("Alıcıları, konuyu ve metni kontrol ettim; gönderimi onaylıyorum.",key="bulk_mail_confirm")
    if st.button("Seçilen şubelere Outlook mailini gönder",type="primary",use_container_width=True):
        if chosen.empty: st.error("En az bir şube seçin."); return
        if not subject.strip() or not message.strip(): st.error("Konu ve mail metni zorunludur."); return
        if not confirmed: st.error("Gönderim onay kutusunu işaretleyin."); return
        attachment_paths=[]
        if uploads:
            attachment_dir=_output()/"Toplu_Mail_Ekleri"/datetime.now().strftime("%Y%m%d_%H%M%S")
            attachment_dir.mkdir(parents=True,exist_ok=True)
            for upload in uploads:
                safe_name=Path(upload.name).name
                target=attachment_dir/safe_name
                target.write_bytes(upload.getvalue())
                attachment_paths.append(str(target))
        jobs=[]; now=datetime.now()
        for _,row in chosen.iterrows():
            personalized=(message.replace("{MAGAZA}",str(row.get(store_col,"")))
                          .replace("{MAGAZA_ID}",str(row.get(id_col,"") if id_col else ""))
                          .replace("{ALICI_ADI}",str(row.get(name_col,"Yetkili") if name_col else "Yetkili"))
                          .replace("{TARIH}",now.strftime("%d.%m.%Y"))
                          .replace("{SAAT}",now.strftime("%H:%M")))
            job_id=enqueue("SEND_EMAIL",{
                "report_type":"BULK_BRANCH_MAIL",
                "subject":subject.strip(),"body":personalized,
                "recipients":[str(row[email_col]).strip()],
                "attachments":attachment_paths,
            },tenant_code())
            jobs.append({"job_id":job_id,"mağaza":str(row.get(store_col,"")),"e_posta":str(row[email_col])})
        log_path=_root()/"logs"/"CURRENT_Toplu_Sube_Mail_Kuyruk.json"
        history=[]
        if log_path.is_file():
            try: history=json.loads(log_path.read_text(encoding="utf-8"))
            except Exception as _exc:
                log_swallowed("web.app.bulk_branch_mail_panel: beklenmeyen hata", _exc)
                history=[]
        history.append({"time":now.isoformat(timespec="seconds"),"created_by":current_user,
                        "subject":subject.strip(),"branch_count":len(jobs),"jobs":jobs})
        log_path.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
        log(current_user,"BULK_BRANCH_EMAIL",f"{len(jobs)} şube / {subject.strip()}")
        # ÖNEMLİ: enqueue() tek başına sadece kuyruğa ekler — sürekli çalışan
        # arka plan worker.py penceresi kapalıysa/hiç açılmamışsa, bu mailler
        # SESSİZCE sonsuza kadar gönderilmez (kullanıcı "kuyruğa alındı"
        # mesajını görür ama hiçbir şey gitmez). Bu yüzden 10-15 şube gibi
        # ÇOK SAYIDA görev burada aynı anda oluştuğunda, hepsini HEMEN işleyen
        # bir "--drain" alt-süreci başlatılır ve sonuç beklenir.
        with st.spinner(f"{len(jobs)} e-posta gönderiliyor..."):
            try:
                py = CODE_ROOT / ".venv" / "Scripts" / "python.exe"
                executable = str(py) if py.exists() else sys.executable
                subprocess.run([executable, str(CODE_ROOT / "worker.py"), "--drain"], cwd=CODE_ROOT, timeout=180)
            except Exception as _e:
                st.warning(f"ℹ️ Otomatik işleme başlatılamadı ({_e}); sürekli çalışan worker penceresi açıksa mailler yine de gönderilecektir.")
        basarili = sum(1 for j in jobs if (job_status(j["job_id"]) or {}).get("status") == "SUCCESS")
        basarisiz = sum(1 for j in jobs if (job_status(j["job_id"]) or {}).get("status") == "FAILED")
        if basarisiz:
            st.error(f"⚠️ {basarisiz}/{len(jobs)} e-posta gönderilemedi. Diğer {basarili} tanesi başarıyla gönderildi.")
        else:
            st.success(f"✅ {basarili}/{len(jobs)} şubeye e-posta başarıyla gönderildi.")




from web.formatting import haversine_km


from web.geo_transfer import (
    store_coordinates, person_address_lookup,
    transfer_recommendations, transfer_distance_map,
)



def _enqueue_and_process(job_type, payload, tenant, timeout=60):
    """enqueue() tek başına bir görevi sadece kuyruğa ekler ve döner — SÜREKLİ
    ÇALIŞAN bir arka plan worker.py süreci varsa bir gün işlenir. Ancak o süreç
    (OMEHR_CURRENT_BASLAT.bat ile başlatılan pencere) kapanmış/hiç açılmamışsa,
    görev SESSİZCE sonsuza kadar "QUEUED" durumunda kalır — transfer onayı sonrası
    rotasyon evrakı ve e-posta hiç gönderilmez, ama kullanıcıya hiçbir hata
    gösterilmez. Bu fonksiyon, tıpkı refresh_all()'daki gibi, görevi enqueue
    ettikten HEMEN SONRA bir "worker.py --once" alt-süreci başlatıp sonucu
    bekler; böylece gönderim sürekli worker'a bağımlı olmadan HER ZAMAN
    gerçekleşir ve başarısızlık kullanıcıya görünür olur."""
    job_id = enqueue(job_type, payload, tenant)
    try:
        py = CODE_ROOT / ".venv" / "Scripts" / "python.exe"
        executable = str(py) if py.exists() else sys.executable
        subprocess.Popen([executable, str(CODE_ROOT / "worker.py"), "--once"], cwd=CODE_ROOT)
    except Exception as _exc:
        log_swallowed("web.app._enqueue_and_process: beklenmeyen hata", _exc)
        pass  # Alt süreç başlatılamazsa, sürekli worker yine de görevi işleyebilir.
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = job_status(job_id) or {}
        if state.get("status") == "SUCCESS":
            return job_id, True, None
        if state.get("status") == "FAILED":
            return job_id, False, state.get("error", "Görev başarısız oldu.")
        time.sleep(0.5)
    return job_id, None, "Zaman aşımı — görev hâlâ işleniyor olabilir, birkaç dakika sonra tekrar kontrol edin."


# DÜZELTME (StreamlitDuplicateElementKey: 'dark_mode_toggle'): bu fonksiyon
# önceden burada tanımlıydı. raporlar.py çalışma zamanında
# `from web.app import _enqueue_without_waiting` yaptığı için, Streamlit
# app.py'yi ana script (`__main__`) olarak çalıştırdığından bu import farklı
# bir modül kimliği (`web.app`) arıyor, sys.modules önbelleğinde bulamayıp
# app.py'yi baştan sona İKİNCİ KEZ çalıştırıyordu — bu da aşağıdaki
# `st.checkbox(..., key="dark_mode_toggle")` satırının iki kez tetiklenip
# StreamlitDuplicateElementKey hatası vermesine yol açıyordu. Fonksiyon artık
# app.py'den TAMAMEN BAĞIMSIZ web/queue_utils.py modülünde tanımlı; hem
# app.py hem tab_modules/raporlar.py sadece oradan import ediyor, böylece
# app.py bir daha asla ikinci kez çalıştırılmıyor.


def refresh_all():
    job_id=enqueue("RUN_REPORTS",tenant=tenant_code())
    py = CODE_ROOT / ".venv" / "Scripts" / "python.exe"
    executable = str(py) if py.exists() else sys.executable
    subprocess.Popen([executable,str(CODE_ROOT/"worker.py"),"--once"],cwd=CODE_ROOT)
    deadline=time.time()+300
    while time.time()<deadline:
        state=job_status(job_id) or {}
        if state.get("status")=="SUCCESS": break
        if state.get("status")=="FAILED": raise RuntimeError(state.get("error","Rapor görevi başarısız."))
        time.sleep(1)
    else:
        raise TimeoutError("Rapor görevi 5 dakika içinde tamamlanmadı.")
    read_input.clear()
    build_model_cached.clear()


if input_source() != "db" and not _input().exists():
    # DÜZELTME (yeni özellik): önceden bu durumda uygulama SERT DURUYORDU
    # (st.stop()) ve HİÇBİR arayüz göstermiyordu — Excel yükleme ekranı
    # dahil (o ekran normalde Ayarlar sekmesinde, giriş yapılmış ve veri
    # zaten yüklenmiş olmayı gerektiren bir bağlamda yaşıyordu). Sonuç:
    # input/ dosyası hiç yokken (ör. Volume yeni bağlandığında, ya da ilk
    # kurulumda) kullanıcı arayüzden KENDİ BAŞINA kurtulamıyor, Railway
    # Console'dan manuel müdahale gerekiyordu. Bu, kendi kendine yeten,
    # bağımsız bir "ilk kurulum" yükleme formu sağlar.
    st.title("OMEHR — İlk Kurulum")
    st.warning(f"Input dosyası bulunamadı: {_input()}")
    st.write(
        "Sistemin çalışabilmesi için ana Excel dosyasını "
        "(OMEHR_AI_NORM_TRANSFER_INPUT.xlsx ya da kendi şirketinizin aynı "
        "yapıdaki dosyası) buradan yükleyin."
    )
    _bootstrap_dosya = st.file_uploader("Excel dosyası (.xlsx)", type=["xlsx"], key="bootstrap_excel_yukleme")
    if _bootstrap_dosya is not None and st.button("Yükle ve etkinleştir", key="bootstrap_excel_yukle_dugmesi"):
        import shutil as _bootstrap_shutil
        try:
            _hedef = _input()
            _hedef.parent.mkdir(parents=True, exist_ok=True)
            _hedef.write_bytes(_bootstrap_dosya.getvalue())
            st.success(f"Dosya etkinleştirildi: {_hedef.name}. Sayfa yeniden yükleniyor...")
            st.cache_data.clear()
            time.sleep(1.5)
            st.rerun()
        except Exception as _bootstrap_exc:
            st.error(f"Yükleme başarısız: {_bootstrap_exc}")
    st.stop()

if input_source() != "db":
    migrate_legacy_input(_input())

# PERFORMANS: Yedekleme + koordinat yenileme + LibreOffice formül yeniden
# hesaplama (bu SONUNCUSU tek başına saniyeler sürebilir) daha önce HER
# Streamlit etkileşiminde (sekme değişimi, buton tıklaması dahil) baştan
# çalışıyordu — oysa Streamlit bir etkileşimde tüm script'i yeniden çalıştırır.
# Bu yüzden panel her tıklamada gereksiz yere yavaşlıyordu. Artık bu ağır
# adımlar SADECE dosyanın son işlendiğimiz andan beri gerçekten değiştiği
# durumlarda (mtime farklıysa) çalışır; aynı oturumda sonraki her etkileşimde
# saniyeler içinde atlanır.
_mevcut_mtime = _input_version(current_tenant_id())
if input_source() == "db":
    # DB modunda Excel dosyası, dosya kilidi, yedekleme ve LibreOffice
    # yeniden hesaplaması yoktur. Önbellek anahtarı tenant sürüm sayacıdır.
    st.session_state["_son_islenen_mtime"] = _mevcut_mtime
elif st.session_state.get("_son_islenen_mtime") == _mevcut_mtime:
    pass  # Dosya bu oturumda daha önce işlendi ve o zamandan beri değişmedi, atla.
else:
    try:
        # EŞZAMANLI KULLANIM KORUMASI: Birden fazla kullanıcı web panelini aynı
        # anda açarsa, aşağıdaki yazma adımlarının (yedekleme, koordinat yenileme,
        # formül yeniden hesaplama) çakışmaması için dosya kilidi kullanılır.
        from services.file_lock import file_lock
        with file_lock(_input()) as _kilit_alindi:
            if not _kilit_alindi:
                st.session_state["_recalc_uyari"] = (
                    "ℹ️ Dosya şu an başka bir kullanıcı/işlem tarafından güncelleniyor gibi görünüyor; "
                    "bu açılışta yenileme adımları atlandı, mevcut veriler gösteriliyor."
                )
            else:
                try:
                    from services.backup import backup_input_file
                    backup_input_file(_input())
                except Exception as _exc:
                    log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
                    pass
                try:
                    refresh_home_proximity(_input())
                except Exception as _exc:
                    log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
                    pass  # koordinat eksikse/uygun değilse sessizce atla, ana akışı bozma
                try:
                    # ÖNEMLİ SIRA: Norm_Durumu/Magaza_KPI_Skor_Karti'yi Python'da
                    # statik değerle YENİDEN HESAPLAMA, LibreOffice'ten ÖNCE
                    # çalışır. openpyxl her kaydında formül önbelleğini sildiği
                    # için, bu adım LibreOffice'ten SONRA çalışsaydı onun az önce
                    # hesapladığı diğer formülleri (Fact_Mevcut/Fact_Norm vb.)
                    # sıfırlardı. LibreOffice EN SON çalışarak tüm formülleri
                    # (bu adımın yazdığı statik hücreler hariç) güncel tutar.
                    from services.formula_bagimsiz_hesapla import statiklestir
                    statiklestir(_input())
                except Exception as _exc:
                    log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
                    pass
                try:
                    # Fact_Mevcut/Fact_Norm'daki Mağaza/Unvan sütunları gerçek Excel formülü
                    # (VLOOKUP) içerir; openpyxl formülleri hesaplamadığı için (yukarıdaki
                    # refresh_home_proximity kaydı dahil) her açılışta LibreOffice ile zorla
                    # yeniden hesaplatılır. LibreOffice kurulu değilse artık kullanıcıya
                    # ayrıca bir bilgi mesajı GÖSTERİLMEZ — services/formula_bagimsiz_hesapla.py
                    # sayesinde tüm sayılar zaten Python tarafından bağımsız ve doğru şekilde
                    # hesaplanıyor; LibreOffice sadece kullanıcı Excel dosyasını manuel
                    # açtığında canlı formül görünümü için faydalıdır, artık kritik değildir.
                    from services.excel_recalc import recalculate_workbook, is_recalc_available
                    if is_recalc_available():
                        basarili=recalculate_workbook(_input())
                        if not basarili:
                            st.session_state["_recalc_uyari"] = (
                                "⚠️ Formül yeniden hesaplama bu seferinde başarısız oldu (zaman aşımı veya dosya "
                                "kilidi olabilir — örn. dosya başka bir programda açık). Gösterilen değerler eski "
                                "olabilir; sayfayı yenileyip tekrar deneyin."
                            )
                        else:
                            st.session_state.pop("_recalc_uyari", None)
                    else:
                        st.session_state.pop("_recalc_uyari", None)
                except Exception as _exc:
                    log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
                    pass
        read_input.clear()
        build_model_cached.clear()
    except Exception as _exc:
        log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
        pass
    # Bu oturumda dosyayı işledik; bir sonraki etkileşimde dosya gerçekten
    # değişmediyse (mtime aynıysa) tüm bu ağır adımlar atlanacak.
    try:
        st.session_state["_son_islenen_mtime"] = _input_version(current_tenant_id())
    except Exception as _exc:
        log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
        pass

# DÜZELTME (FAST V15 — 3 PC ortak Excel — TAMAMEN DEVRE DIŞI, 29 Ağustos 2026):
# Bu kontrol, "Excel yeniden hesaplama" adımının (statiklestir,
# recalculate_workbook) HER TAZE tarayıcı oturumunda (her F5'te, çünkü
# st.session_state oturuma özeldir) dosyayı fiziksel olarak yeniden yazdığını
# — bu yüzden içerik değişmese bile mtime'ın HER OTURUMDA değiştiğini —
# hesaba katmıyordu. Sonuç: bu kontrol neredeyse HER sayfa yüklemesinde
# "başka bir PC Excel'i değiştirdi" sanıp az önce üretilmiş raporları
# SİLİYORDU (sıralamayı değiştirmek de yetmedi, çünkü sorun sıra değil,
# mtime'ın doğası gereği her oturumda değişmesiydi). Artık tek sunuculu
# (Railway) mimaride "birden fazla PC aynı ağ Excel dosyasını paylaşıyor"
# varsayımı geçerli olmadığı için bu kontrol TAMAMEN devre dışı bırakılmıştır.
# try:
#     from services.multi_pc_sync import invalidate_local_reports_if_shared_input_changed
#     invalidate_local_reports_if_shared_input_changed(_root(), _input())
# except Exception as _exc:
#     log_swallowed("web.app.multi_pc_sync: paylaşımlı input değişikliği kontrol edilemedi", _exc)

if st.session_state.get("_recalc_uyari"):
    st.warning(st.session_state["_recalc_uyari"])

# ------------------------------------------------------------------
# GİRİŞ AKIŞI — SaaS çok kiracılı temel: kullanıcı, hangi FİRMA için
# giriş yaptığını AÇIKÇA seçer (veya varsayılan tek-kiracı 'OMEHR').
# Kiracı seçimi doğrulanan girişten HEMEN SONRA, herhangi bir kiracıya
# özgü veri (Mail_Listesi dahil) okunmadan ÖNCE oturuma yazılır —
# services.tenant_context::current_tenant_id() bunu önceliklendirir.
#
# DÜZELTME (kritik): önceden bu adım hiç yoktu — sheets/accounts
# giriş formundan ÖNCE, işlem-geneli (OMEHR_TENANT ortam değişkeni
# veya varsayılan) bağlamla okunuyordu. Gerçek bir SaaS'ta (tek
# çalışan sunucu, birden fazla firmanın kullanıcıları) bu, kiracı
# seçiminin HİÇ ÇALIŞMAMASI anlamına gelirdi.
# ------------------------------------------------------------------
if "user" not in st.session_state:
    _kiraci_secenekleri = ["OMEHR"]
    try:
        from services.tenant_registry import list_tenants
        _kayitlilar = [t["tenant_id"] for t in list_tenants() if t.get("durum") == "aktif"]
        if _kayitlilar:
            _kiraci_secenekleri = sorted(_kayitlilar)
    except Exception as _exc:
        log_swallowed("web.app: tenant_registry okunamadı, varsayılan OMEHR kullanılıyor", _exc)

    if input_source() != "db" and len(_kiraci_secenekleri) > 1:
        st.warning(
            "DİKKAT: Birden fazla firma kayıtlı ama sistem Excel modunda çalışıyor. "
            "Excel modu tek bir çalışan sunucu sürecinde AYNI ANDA birden fazla "
            "firmayı GÜVENLE ayıramaz (dosya yolları işlem-geneli çözümlenir). "
            "Gerçek çok kiracılı SaaS kullanımı için OMEHR_INPUT_SOURCE=db "
            "ZORUNLUDUR — aksi halde firmalar birbirinin verisini görebilir."
        )

    _render_main_title()

    _giris_modu = st.radio(
        "", ["Giriş Yap", "Yeni Firma Kaydı"], horizontal=True,
        label_visibility="collapsed", key="giris_veya_kayit",
    )

    if _giris_modu == "Yeni Firma Kaydı":
        st.subheader("Yeni Firma Kaydı")
        st.caption(
            "KURULUM.bat çalıştırmadan, doğrudan buradan firmanızı kaydedip ilk "
            "yönetici hesabınızı oluşturabilirsiniz. Mevcut bir Excel dosyanız "
            "varsa 3. adımda yükleyebilirsiniz — isterseniz boş başlayıp verileri "
            "sonradan 'Tüm Sayfalar' panelinden de girebilirsiniz."
        )
        from services import onboarding

        with st.form("kayit_firma"):
            st.markdown("**1) Firma Bilgileri**")
            k_tenant_id = st.text_input("Firma kodu (benzersiz, ör. AKMEMARKET)", max_chars=20)
            k_firma_adi = st.text_input("Firma adı")
            k_plan = st.selectbox("Plan", ["deneme", "temel", "standart", "kurumsal"])
            st.markdown("**2) İlk Yönetici Hesabı**")
            k_kullanici = st.text_input("Kullanıcı adı")
            k_eposta = st.text_input("E-posta")
            k_sifre1 = st.text_input("Şifre", type="password")
            k_sifre2 = st.text_input("Şifre (tekrar)", type="password")
            st.markdown("**3) Veri (isteğe bağlı)**")
            k_excel = st.file_uploader("Mevcut OMEHR input Excel dosyanız (isteğe bağlı)", type=["xlsx"])
            k_kaydet = st.form_submit_button("Firmayı Kaydet", type="primary")

        if k_kaydet:
            hata_var = False
            if k_sifre1 != k_sifre2:
                st.error("Şifreler eşleşmiyor.")
                hata_var = True
            if not hata_var:
                try:
                    onboarding.register_tenant(k_tenant_id, k_firma_adi, plan=k_plan)
                    onboarding.register_first_admin(k_tenant_id, k_kullanici, k_sifre1, e_posta=k_eposta)
                    if k_excel is not None:
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
                            tf.write(k_excel.getvalue())
                            gecici_yol = tf.name
                        onboarding.import_initial_data(k_tenant_id.strip().upper(), gecici_yol)
                    st.success(
                        f"'{k_firma_adi}' kaydedildi. Yukarıdan 'Giriş Yap' sekmesine geçip "
                        f"Firma: {k_tenant_id.strip().upper()}, Kullanıcı: {k_kullanici} ile giriş yapabilirsiniz."
                    )
                except ValueError as _kayit_hata:
                    st.error(str(_kayit_hata))
        st.stop()

    with st.form("login"):
        secilen_kiraci = (
            st.selectbox("Firma", _kiraci_secenekleri)
            if len(_kiraci_secenekleri) > 1
            else _kiraci_secenekleri[0]
        )
        username = st.text_input("Kullanıcı adı")
        password = st.text_input("Şifre", type="password")
        submit = st.form_submit_button("Giriş")
    if submit:
        # Kiracıyı DOĞRULAMADAN ÖNCE oturuma yaz — bu kiracının Mail_
        # Listesi'ni (kullanıcı dizinini) okuyabilmek için gereklidir.
        set_session_tenant(secilen_kiraci)
        _giris_sheets = read_input(_input_version(secilen_kiraci), tenant_id=secilen_kiraci)
        _giris_acc = accounts(_giris_sheets)
        match = _giris_acc[_giris_acc["Web Kullanıcı"].astype(str).str.strip().eq(username.strip())]
        if match.empty:
            st.error("Kullanıcı adı veya şifre hatalı")
        else:
            ok,message,must_change=verify_password(match.iloc[0], password, tenant_id=secilen_kiraci)
            if not ok: st.error(message)
            else:
                st.session_state.user = match.iloc[0].to_dict()
                st.session_state.must_change_password = must_change
                st.session_state["_son_aktivite"] = datetime.now().isoformat()
                log(username, "LOGIN"); st.rerun()
    st.stop()

# DÜZELTME (güvenlik sertleştirme — hassas personel verisi taşıyan bir
# sistem için): önceden oturum, kullanıcı elle "Çıkış" yapmadıkça
# SÜRESİZ açık kalıyordu — hiçbir zaman aşımı yoktu. Artık belirli bir
# süre (varsayılan 8 saat / 480 dakika) işlem yapılmazsa oturum otomatik
# sonlanır ve yeniden giriş istenir. Mantık services/session_guard.py'de
# (Streamlit'e bağımlı olmayan, doğrudan test edilebilir) saf bir
# fonksiyon olarak tutulur.
from services.session_guard import oturum_suresi_doldu_mu
_oturum_doldu, _idle_dakika = oturum_suresi_doldu_mu(st.session_state.get("_son_aktivite"))
if _oturum_doldu:
    _cikan_kullanici = str(st.session_state.user.get("Web Kullanıcı", ""))
    del st.session_state["user"]
    st.session_state.pop("_son_aktivite", None)
    st.session_state.pop("must_change_password", None)
    log(_cikan_kullanici, "SESSION_IDLE_TIMEOUT", f"{_idle_dakika:.0f} dakika işlemsizlik")
    st.warning(f"Uzun süreli işlemsizlik nedeniyle oturumunuz sonlandırıldı. Lütfen yeniden giriş yapın.")
    st.rerun()
st.session_state["_son_aktivite"] = datetime.now().isoformat()

# DÜZELTME (Madde 17/51): apply_due_appointments() önceden yalnız
# main.py'de çağrılıyordu — kullanıcı web panelini açtığında, main.py
# ayrıca çalıştırılmadığı sürece tarihi GELMİŞ bir PLANNED atama
# otomatik yürürlüğe girmiyordu. Artık web açılışında da (oturum
# başına YALNIZ BİR KEZ — her sayfa yenilemesinde DEĞİL, performans
# ilkesine uygun) kontrol edilir.
if not st.session_state.get("_atama_kontrolu_yapildi"):
    try:
        from services.appointment_lifecycle import apply_due_appointments
        _uygulanan_atamalar = apply_due_appointments(input_path=_input(), root=_root())
        if _uygulanan_atamalar:
            from web.queue_utils import enqueue_report_refresh
            enqueue_report_refresh()
    except Exception as _exc:
        log_swallowed("web.app: apply_due_appointments başarısız", _exc)
    st.session_state["_atama_kontrolu_yapildi"] = True

# DÜZELTME (ücretsiz katman dağıtımı — worker.py AYRI bir süreç olarak
# çalıştırılamayan platformlar, ör. Streamlit Community Cloud): normal
# Docker/VPS dağıtımında worker.py SÜREKLİ ayrı çalışır, kuyruğa giren
# işler (mail gönderimi vb.) hemen işlenir. Bu ortamlarda OMEHR_WORKER_
# INLINE=1 AYARLANMAZSA bu blok HİÇBİR ŞEY YAPMAZ (gereksiz tekrar
# olmasın diye). Yalnız AYRI worker süreci OLMAYAN platformlarda, HER
# sayfa yüklemesinde bekleyen işler senkron olarak (sınırlı sürede,
# kuyruk boşsa anında) işlenir — mükemmel gerçek-zamanlı değildir
# (kullanıcı panele TEKRAR girene kadar bekler) ama işlerin SONSUZA
# KADAR "QUEUED" kalmasını önler.
if os.getenv("OMEHR_WORKER_INLINE", "0") == "1":
    try:
        import worker as _worker
        _worker.run(drain=True)
    except Exception as _exc:
        log_swallowed("web.app: inline worker (OMEHR_WORKER_INLINE) başarısız", _exc)

sheets = read_input(_input_version(current_tenant_id()), tenant_id=current_tenant_id())
required = {"Fact_Mevcut", "Fact_Norm", "Mail_Listesi"}
if not required.issubset(sheets):
    st.error(f"Eksik input sayfaları: {sorted(required-set(sheets))}"); st.stop()
acc = accounts(sheets)

user = st.session_state.user
username = str(user.get("Web Kullanıcı", "")); role = str(user.get("Rol", "")).upper(); scope = str(user.get("Yetki Kapsamı", "")); email = str(user.get("E-posta", "")).casefold()
is_global = scope.upper() == "ALL" or role in {"HR_DIRECTOR", "EXECUTIVE", "CEO", "ADMIN"}
# KVKK: Personelin ev adresi/koordinatı ve buradan üretilen Google Maps rota linki
# kişisel veridir. "İhtiyaç kadar erişim" ilkesi gereği bu ham veriye sadece İK ve
# sistem yöneticisi erişebilir. Bölge müdürleri dahil diğer roller, transfer
# planlaması için gerekli olan MESAFE (km) bilgisini görebilir ama ham koordinatı,
# açık adresi veya doğrudan ev konumunu açan haritayı/rota linkini göremez.
can_view_personal_address = role in {"HR_DIRECTOR", "ADMIN"}
approval_level=int(pd.to_numeric(user.get("Onay Seviyesi", 0), errors="coerce") or 0)
can_approve = approval_level >= 2 and role in {"HR_DIRECTOR","ADMIN","CEO","EXECUTIVE","MANAGEMENT"}

if st.session_state.get("must_change_password", False):
    _render_main_title()
    st.subheader("Güvenli Şifre Oluşturma")
    st.warning("İlk girişte geçici şifrenizi değiştirmeniz zorunludur.")
    with st.form("mandatory_password_change"):
        new1=st.text_input("Yeni şifre",type="password")
        new2=st.text_input("Yeni şifre tekrar",type="password")
        save=st.form_submit_button("Yeni şifreyi kaydet")
    if save:
        error=password_error(new1)
        if new1!=new2:st.error("Şifreler aynı değil.")
        elif error:st.error(error)
        else:
            set_password(username,new1,must_change=False)
            st.session_state.must_change_password=False
            log(username,"MANDATORY_PASSWORD_CHANGE")
            st.success("Şifreniz güvenli biçimde değiştirildi.")
            st.rerun()
    st.stop()

with st.sidebar:
    _logo_col, _bilgi_col = st.columns([1, 5])
    with _logo_col:
        st.image(str(CODE_ROOT / "web" / "assets" / "omehr_logo_compact.png"), width=150)
    with _bilgi_col:
        st.markdown(f"**{user.get('Sorumlu','Kullanıcı')}**")
        st.caption(f"{role} · {scope}")
    _dark_on = st.checkbox("🌙 Karanlık Mod", value=st.session_state.get("dark_mode", False), key="dark_mode_toggle")
    if _dark_on != st.session_state.get("dark_mode", False):
        st.session_state["dark_mode"] = _dark_on
        st.rerun()
    if st.button("Tüm tabloları şimdi yenile", use_container_width=True):
        _enqueue_without_waiting("RUN_REPORTS", {}, tenant_code())
        st.success(
            "İşlem arka planda başlatıldı. Sayfa donmayacak — raporların "
            "üretilmesi 1-3 dakika sürebilir; birkaç dakika sonra bu "
            "butona veya Rapor Merkezi'ne tekrar bakın."
        )
    with st.expander("Şifremi değiştir"):
        new1 = st.text_input("Yeni şifre", type="password", key="p1")
        new2 = st.text_input("Yeni şifre tekrar", type="password", key="p2")
        if st.button("Şifreyi kaydet"):
            error=password_error(new1)
            if new1 != new2: st.error("Şifreler aynı olmalı")
            elif error:st.error(error)
            else:
                set_password(username,new1,must_change=False); log(username,"PASSWORD_CHANGE"); st.success("Şifre değiştirildi")
    if username.strip().casefold() == "admin":
        with st.expander("Kullanıcı şifresi sıfırla"):
            st.caption("Mevcut şifreler görüntülenmez. Kullanıcıya yeni geçici şifre verilir.")
            reset_users = sorted(
                {
                    str(value).strip()
                    for value in acc.get("Web Kullanıcı", pd.Series(dtype=str)).dropna()
                    if str(value).strip() and str(value).strip().casefold() != "admin"
                }
            )
            reset_username = st.selectbox("Kullanıcı", reset_users, key="admin_reset_user")
            reset_password = st.text_input("Yeni geçici şifre", type="password", key="admin_reset_password")
            reset_password_again = st.text_input(
                "Yeni geçici şifre tekrar", type="password", key="admin_reset_password_again"
            )
            if st.button("Geçici şifreyi tanımla", key="admin_reset_submit"):
                error = password_error(reset_password)
                if reset_password != reset_password_again:
                    st.error("Şifreler aynı olmalı.")
                elif error:
                    st.error(error)
                else:
                    set_password(reset_username, reset_password, must_change=True)
                    log(username, "ADMIN_PASSWORD_RESET", reset_username)
                    st.success(
                        f"{reset_username} için geçici şifre tanımlandı. "
                        "Kullanıcı ilk girişte bu şifreyi değiştirecek."
                    )
    if st.button("Çıkış", use_container_width=True): del st.session_state.user; st.rerun()

fm, detail, stores, kpis = build_model_cached(_input_version(current_tenant_id()), tenant_id=current_tenant_id())
if not is_global:
    fm=fm[fm["Bölge Sorumlusu"].astype(str).map(norm_text).eq(norm_text(scope))]
    detail=detail[detail["Bölge Sorumlusu"].astype(str).map(norm_text).eq(norm_text(scope))]
    stores=stores[stores["Bölge Sorumlusu"].astype(str).map(norm_text).eq(norm_text(scope))]

if not is_global:
    # Bölge kullanıcısında KPI değerleri kendi kapsamından dinamik hesaplanır.
    kpis={"Aktif Mevcut":int(len(fm)),"Toplam Norm":int(detail["Norm"].sum()),"Norm Eksiği":int(detail["Eksik"].sum()),"Norm Fazlası":int(detail["Fazla"].sum())}
    kpis["Net İhtiyaç"]=kpis["Norm Fazlası"]-kpis["Norm Eksiği"]
if kpis["Toplam Norm"]<=0:
    st.error("Toplam Norm 0 olamaz. Fact_Norm sayfasını kontrol edin."); st.stop()
st.markdown('<div class="omehr-title-top-gap"></div>', unsafe_allow_html=True)
try:
    from services.kpi_history import snapshot_n_days_ago, log_kpi_snapshot
    log_kpi_snapshot(kpis)  # web açılışında da bugünkü anlık görüntüyü kaydet
    _onceki_kpi = snapshot_n_days_ago(30)
except Exception as _exc:
    log_swallowed("web.app.modül: beklenmeyen hata", _exc)
    _onceki_kpi = None
_kpi_kolonlari=st.columns(5)
for c,(k,v) in zip(_kpi_kolonlari,kpis.items()):
    _delta_metni = None
    if _onceki_kpi and k in _onceki_kpi and _onceki_kpi[k] not in (None, ""):
        try:
            _fark = float(v) - float(_onceki_kpi[k])
            if abs(_fark) > 0.01:
                _delta_metni = f"{'+' if _fark>0 else ''}{_fark:.0f} (30 gün)"
        except Exception as _exc:
            log_swallowed("web.app.refresh_all: beklenmeyen hata", _exc)
            pass
    if k=="Net İhtiyaç":
        # "Net İhtiyaç: -17" gibi işaretli bir sayı kullanıcı için kafa karıştırıcıdır
        # (negatif sayı "17 kişiye ihtiyaç var mı yoksa fazla mı var" belirsizliği
        # yaratır). Bunun yerine yönü açıkça kelimeyle belirten bir gösterim kullanılır.
        if v<0:
            c.metric(k, f"{abs(int(v))} kişi eksik", help="Norm Fazlası - Norm Eksiği < 0: şirket genelinde eksik, fazlasından daha fazla.")
        elif v>0:
            c.metric(k, f"{int(v)} kişi fazla", help="Norm Fazlası - Norm Eksiği > 0: şirket genelinde fazla, eksiğinden daha fazla.")
        else:
            c.metric(k, "Dengede", help="Norm Fazlası ve Norm Eksiği eşit.")
    else:
        c.metric(k,v,delta=_delta_metni,delta_color="normal" if k in ("Norm Fazlası","Aktif Mevcut") else "inverse")
if _onceki_kpi is None:
    st.caption("ℹ️ 30 gün önceki karşılaştırma için henüz yeterli geçmiş birikmedi — sistem her main.py çalıştığında otomatik kayıt tutmaya bugünden itibaren başladı.")

ctx = PageContext(
    root=_root(), input_path=_input(), output_path=_output(), db_path=_db(),
    approvers=APPROVERS, bd_renk=BD_RENK,
    sheets=sheets, acc=acc, fm=fm, detail=detail, stores=stores, kpis=kpis,
    user=user, username=username, role=role, scope=scope, email=email,
    is_global=is_global, can_view_personal_address=can_view_personal_address,
    approval_level=approval_level, can_approve=can_approve,
    db=db, log=log, enqueue=enqueue, job_status=job_status, tenant_code=tenant_code,
    norm_text=norm_text, tr_number=tr_number, tr_money_compact=tr_money_compact,
    set_password=set_password, password_error=password_error,
    refresh_home_proximity=refresh_home_proximity, maps_route=maps_route,
    verify_password=verify_password, transfer_recipients=transfer_recipients,
    cancel_transfer_request=cancel_transfer_request,
    redirect_transfer_request=redirect_transfer_request,
    bulk_branch_mail_panel=bulk_branch_mail_panel,
    enqueue_and_process=_enqueue_and_process, read_input=read_input,
)

PAGE_RENDERERS = {
    "Genel Özet": genel_ozet.render,
    "CEO Özeti": ceo_ozet.render,
    "Bölge & Mağaza": bolge_magaza.render,
    "Personel Kartları": personel_kartlari.render,
    "Unvan Analizi": unvan_analizi.render,
    "Personel Performansı": performans.render,
    "İş Gücü Tahmini": isgucu_tahmini.render,
    "Transfer Optimizasyonu": transfer_optimizasyon.render,
    "Transfer Merkezi": transfer_merkezi.render,
    "Onaylar": onaylar.render,
    "AI Operasyon & Verimlilik": ai_operasyon.render,
    "Operasyon Görselleri": operasyon_gorselleri.render,
    "Verimlilik Görselleri": verimlilik_gorselleri.render,
    "Raporlar": raporlar.render,
    "Şubelere Toplu Mail": toplu_mail.render,
    "Bildirimler": bildirimler.render,
    "AI Geri Bildirim": ai_geri_bildirim.render,
    "Veri Toplama": veri_toplama.render,
    "Ana Veri Yönetimi": ana_veri_yonetimi.render,
    "Tüm Sayfalar (Veritabanı)": tum_sayfalar_veri_yonetimi.render,
    "Ayarlar": ayarlar.render,
}

# Sayfa navigasyonu aynı Streamlit oturumu içinde çalışan bir widget ile yapılır.
# HTML <a href=...> bağlantısı tarayıcıda yeni WebSocket oturumu başlatabildiği
# için session_state kayboluyor ve kullanıcıdan yeniden şifre isteniyordu.
# Radio seçimi yalnız mevcut oturumu yeniden çalıştırır; giriş bilgisi korunur.
_sayfa_adlari = list(PAGE_RENDERERS)

_qp_page = st.query_params.get("page", _sayfa_adlari[0])
if isinstance(_qp_page, list):
    _qp_page = _qp_page[0] if _qp_page else _sayfa_adlari[0]
_qp_page = str(_qp_page)
if _qp_page not in PAGE_RENDERERS:
    _qp_page = _sayfa_adlari[0]

_onceki_sayfa = st.session_state.get("aktif_sayfa", _qp_page)
if _onceki_sayfa not in PAGE_RENDERERS:
    _onceki_sayfa = _sayfa_adlari[0]

aktif_sayfa = st.radio(
    "Uygulama sayfaları",
    _sayfa_adlari,
    index=_sayfa_adlari.index(_onceki_sayfa),
    horizontal=True,
    label_visibility="collapsed",
    key="aktif_sayfa_secimi",
)
st.session_state["aktif_sayfa"] = aktif_sayfa

# Adres çubuğundaki sayfa parametresi paylaşılabilir kalsın; bu atama tam
# sayfa yenilemesi yapmaz ve oturumu düşürmez.
if st.query_params.get("page") != aktif_sayfa:
    st.query_params["page"] = aktif_sayfa

from services.performance_log import track_page_render
with track_page_render(aktif_sayfa):
    PAGE_RENDERERS[aktif_sayfa](ctx)
