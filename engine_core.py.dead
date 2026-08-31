from __future__ import annotations

# OMEHR NORM KADRO RAPORLAMA SİSTEMİ V19.21.2
# ORKESTRASYON KATMANI (P2 — engine_core.py modülerleştirmesi tamamlandı).
# Bu dosya artık SADECE run_all() orkestrasyonunu içerir (~145 satır).
# Gerçek hesaplama/üretim mantığı ayrı, tek-sorumluluklu modüllerde:
#   src/feature_flags.py   — özellik bayrakları (bağımsız)
#   src/data_loading.py    — input okuma + yedekleme/koordinat/formül
#   src/state_engine.py    — mevcut/norm/eksik/fazla durum hesaplama
#   src/kpi_engine.py      — resmi KPI özeti + mutabakat doğrulaması
#   src/scenario_engine.py — transfer havuzu, senaryolar, risk tablosu
#   src/ai_norm.py         — AI norm öneri motoru (kalibrasyon dahil)
#   src/excel_report.py    — Excel rapor üretimi
#   src/pdf_report.py      — PDF rapor üretimi
#   src/pdf_fonts.py       — Türkçe-glif-doğrulamalı TEK font kayıt noktası
# Her modül AYNI İSİMLERLE buradan geri import edilir — main.py, web/app.py,
# tests/ içindeki HİÇBİR çağrı noktası değişmedi (from src.engine_core
# import X hâlâ çalışır).
import json, shutil
from datetime import datetime
import pandas as pd
from services.runtime_paths import runtime_root
PDF_SOURCE_HASH=''
PDF_GENERATED_AT=''

from src.feature_flags import ai_features_enabled, executive_analysis_enabled, data_quality_report_enabled
from src.data_loading import load
from src.state_engine import (
    state, _control_tables, _control_long, _gap_tables, _scope_baseline,
)
from src.kpi_engine import (
    kpis, reconcile_kpis, _reconcile_net_by_store, _yaz_kpi_mutabakat_sayfasi,
)
from src.scenario_engine import compat, transfer_pool, needs, scenarios, risk_table, COMP
from src.text_utils import (
    product_name, _repair_mojibake, txt, canon, _store_key, numeric, col, req,
    unvan_anahtari, unvan_sira_no, unvan_sirali, UNVAN_SIRASI,
    _region_name, _title_key,
)

from src.excel_report import (
    write_df, executive_excel, _store_roster_rows,
    _personnel_names_by_store_title, _title_report_with_names,
    _personnel_detail_report, _surplus_people_report, _gap_text,
    _region_excel, enhanced_excel_reports, _v16_enrich_explanations,
    _v16_scenario_impact, _v16_add_workbook_layers,
    _executive_analysis_frames, _add_executive_analysis_sheets,
    _add_visible_ai_dashboard, _build_admin_report_pack, build_boxed_manager_excel,
)
from src.ai_norm import (
    _transfer_coverage, _decision_reason, ai_norm_table, validate_ai_decisions,
    ai_norm_executive_summary,
)
from src.pdf_report import (
    font, _pdf_text, _pdf_plain_text, pdf_report, _pdf_styles, _footer,
    enhanced_pdf_reports, _chart_label, _tr_chart_value, _pdf_empty_chart,
    _pdf_bar_chart, _pdf_grouped_chart, _pdf_visual_story, _build_store_pdf,
)
from src.veri_kalitesi_raporu import generate_data_quality_report

def run_all():
    """Resmi norm KPI'ları ile ayrı AI karar desteği katmanını birlikte üretir."""
    global PDF_SOURCE_HASH, PDF_GENERATED_AT
    started=datetime.now()
    p,sheets,norm,staff,h=load()
    st,tt=state(norm,staff,sheets)
    kp=kpis(st)
    # KPI MUTABAKAT KATMANI (P0 — üretim öncesi zorunlu, dış denetim önerisi):
    # "Mevcut-Norm", "Norm Fazlası-Eksiği", "norm kapsamındaki mevcut",
    # "toplam aktif mevcut" gibi FARKLI kavramların birbirine karıştırılıp
    # aynı şeymiş gibi raporlanmasını önlemek için, HER çalıştırmada bu üç
    # özdeşlik otomatik doğrulanır ve sonucu ayrı bir Excel sayfasına yazılır.
    mutabakat = reconcile_kpis(staff, tt, kp)
    if not mutabakat['tutarli']:
        _LOGGER_MUTABAKAT_UYARISI = (
            f"KPI MUTABAKAT UYARISI: rakamlar tutmuyor — norm_disi={mutabakat['norm_disi_calisan_sayisi']}, "
            f"net_pozisyon_farki={mutabakat['net_pozisyon_farki']} != net_ihtiyac_kpi={mutabakat['net_ihtiyac_kpi']}"
        )
        print(_LOGGER_MUTABAKAT_UYARISI, flush=True)
    PDF_SOURCE_HASH=h; PDF_GENERATED_AT=datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    empty=pd.DataFrame()
    scens=scenarios(st,tt,staff,sheets)
    risk=risk_table(st)
    ai=ai_norm_table(sheets,tt,scens)
    validation,validation_summary=validate_ai_decisions(ai,kp,st)
    outx,wb=executive_excel(kp,st,tt,scens,risk,h,ai=ai,validation=validation,validation_summary=validation_summary,input_sheets=sheets,staff=staff,return_workbook=True)
    try:
        _yaz_kpi_mutabakat_sayfasi(outx, mutabakat, workbook=wb)
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("KPI_Mutabakat_Kontrolu sayfası Excel'e yazılamadı", _exc, level="ERROR")
    # AI sonuçları ve model açıklamaları aynı yönetici Excel'inde ayrıca sunulur.
    write_df(wb,'AI Norm ve Aksiyon',ai)
    if validation is not None and not validation.empty:write_df(wb,'AI Karar Doğrulama',validation)
    # YÖNETİCİ ÖZETİ (P0 — "AI-resmi norm farkı unvan/mağaza bazında NEDEN
    # açıklanmalı" talebi): AI'nin önerdiği toplam normun resmi normdan neden
    # ve NEREDE farklı olduğunu, aksiyon alınabilir şekilde üç ayrı sayfada
    # sunar (genel özet + unvan bazlı + mağaza bazlı) artı düz metin anlatım.
    try:
        _ai_ozet=ai_norm_executive_summary(ai)
        write_df(wb,'AI Özet - Genel',_ai_ozet['genel'])
        write_df(wb,'AI Özet - Unvan Bazlı',_ai_ozet['unvan_bazli'])
        write_df(wb,'AI Özet - Mağaza Bazlı',_ai_ozet['magaza_bazli'])
        write_df(wb,'AI Özet - Anlatım',pd.DataFrame({'Yönetici Özeti':_ai_ozet['anlatim'].split('\n')}))
        print('AI NORM YÖNETİCİ ÖZETİ:\n'+_ai_ozet['anlatim'], flush=True)
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("AI Norm yönetici özeti üretilemedi", _exc, level="ERROR")
    for source_name,target_name,sheet_name in [
        ('V19_Istatistik_ML_Operasyon_Analizi.xlsx','V19 Model Özeti','Model_Karsilastirma'),
        ('V19_1_Derin_Model_Karsilastirmasi.xlsx','V19.1 Derin Modeller','Regresyon_Model_Karsilastirma'),
        ('V19_1_Derin_Model_Karsilastirmasi.xlsx','V19.1 Sınıflandırma','Siniflandirma_Karsilastirma'),
    ]:
        source=runtime_root()/'output'/source_name
        if source.is_file():
            summary=pd.read_excel(source,sheet_name=sheet_name)
            write_df(wb,target_name,summary)
    # PERFORMANS DÜZELTMESİ (archive/gelistirme_notlari/PERFORMANS_NOTLARI.md'deki
    # planın uygulanması,
    # 02.08.2026): önceden bu üç katman fonksiyonu KENDİ başına dosyayı
    # açıp kaydediyordu (3 ayrı load_workbook+save döngüsü). Artık zaten
    # açık olan `wb` nesnesini paylaşıyorlar, TEK bir save() ile biter.
    # "Yönetim Paneli" katmanı (özet panel + grafik + kritik aksiyon/maliyet
    # sayfaları) — çağrısı önceki bir sürümde kayboldu (fonksiyon import
    # ediliyordu ama hiç çağrılmıyordu, sessiz bir özellik kaybıydı; bkz.
    # tests/test_system_contract.py::test_51, bulgu: kod incelemesi).
    _v16_add_workbook_layers(wb,kp,st,tt,ai,scens,risk)
    if executive_analysis_enabled():
        # DÜZELTME: bu adım önceden try/except'siz çağrılıyordu — "Aylık
        # Operasyon KPI" gibi İSTEĞE BAĞLI kaynak sayfalardan biri
        # eksikse (ör. henüz doldurulmamış yeni bir kurulum) TÜM rapor
        # üretimi (norm/transfer/mail dahil) çöküyordu. Yönetici analizi
        # isteğe bağlı bir eklentidir; eksikliği ana raporu engellememeli.
        try:
            _add_executive_analysis_sheets(wb,p)
        except Exception as _exc:
            from services.safe_exec import log_swallowed
            log_swallowed(
                "engine_core.run_all: yönetici finansal/operasyonel analiz sayfaları "
                "üretilemedi (muhtemelen isteğe bağlı bir kaynak sayfa eksik/boş) — "
                "ana rapor üretimi bundan etkilenmeden devam ediyor",
                _exc, level="ERROR",
            )
    _add_visible_ai_dashboard(wb,kp,ai,p)
    wb.save(outx)
    outp=enhanced_pdf_reports(kp,norm,staff,sheets,scens,ai,validation_summary)
    enhanced_excel_reports(kp,st,tt,ai,staff)
    boxed_manager_excel=build_boxed_manager_excel(st,norm,staff,kp,tt=tt)
    outdir=runtime_root()/'output'
    # VERİ KALİTESİ RAPORU (V19.9 — dış inceleme sonrası eklendi): dummy
    # adres/saha etüdü bekleyen süre/dummy mail/tanımsız unvan işaretleri
    # zaten log'a yazılıyordu ama görünür bir dosya yoktu (bkz. modülün
    # docstring'i). Her çalıştırmada güncel dosya üretilir.
    try:
        kalite_raporu=generate_data_quality_report(sheets,outdir) if data_quality_report_enabled() else None
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("Veri kalitesi raporu üretilemedi", _exc, level="ERROR")
        kalite_raporu=None
    # Kullanıcının eski OMEHR dosyasını yanlışlıkla açmasını önlemek için yeni
    # sürüm adları ayrıca üretilir; OMEHR adları Outlook uyumluluğu için korunur.
    current_excel=outdir/'OMEHR_Executive_Data.xlsx'
    manager_excel=outdir/'OMEHR_Yonetici_Raporu.xlsx'
    current_pdf=outdir/'OMEHR_Yonetici_Raporu.pdf'
    # DÜZELTME: enhanced_pdf_reports() bir önceki sürümde doğrudan
    # OMEHR_Yonetici_Raporu.pdf'e yazacak şekilde yeniden adlandırıldı
    # (outp artık current_pdf ile AYNI dosya) — ama Excel tarafı hâlâ eski
    # OMEHR_Executive_Data.xlsx adını kullanıyor (outx != current_excel). Kaynak
    # ve hedef aynı dosyaysa shutil.copy2 SameFileError ile çöküyordu.
    # Artık yalnız GERÇEKTEN farklı bir dosyaysa kopyalanıyor — ileride
    # isimler tekrar birleştirilse bile güvenli.
    if outx.resolve() != current_excel.resolve():
        shutil.copy2(outx,current_excel)
    # Yönetici PDF'sinin Excel karşılığı açık ve anlaşılır bir adla ayrıca tutulur.
    if outx.resolve() != manager_excel.resolve():
        shutil.copy2(outx, manager_excel)
    if outp.resolve() != current_pdf.resolve():
        shutil.copy2(outp,current_pdf)
    admin_reports=_build_admin_report_pack(kp,st,tt,ai,p,current_pdf,current_excel)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    (runtime_root()/'logs').mkdir(exist_ok=True); (runtime_root()/'backup').mkdir(exist_ok=True); (runtime_root()/'archive').mkdir(exist_ok=True)
    if p.exists():
        shutil.copy2(p,runtime_root()/'backup'/f'{p.stem}_{stamp}.xlsx')
    shutil.copy2(outx,runtime_root()/'archive'/f'OMEHR_Executive_Data_{stamp}.xlsx')
    shutil.copy2(outp,runtime_root()/'archive'/f'OMEHR_Yonetici_Raporu_{stamp}.pdf')
    snap={'version':'V19.1 Derin Model Karşılaştırması','timestamp':datetime.now().isoformat(),'duration_seconds':round((datetime.now()-started).total_seconds(),2),'sha256':h,'kpis':kp,'sources':{'mevcut':'Fact_Mevcut','norm':'Fact_Norm','ai':'V19_AI_Norm_Sonuclari.xlsx','benchmark':'V19_1_Derin_Model_Karsilastirmasi.xlsx'},'engines':{'mevcut_norm_comparison':True,'pdf':True,'excel':True,'region_reports':True,'ai':True,'statistical_tests':True,'machine_learning':True,'group_kfold':True,'operational':True},'files':{'excel':str(outx),'pdf':str(outp),'region_reports':str(outdir/'Bolge_Raporlari')}}
    (outdir/'BASDAS_latest.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8')
    (runtime_root()/'logs'/'BASDAS_Run_Audit.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'path':p,'sheets':sheets,'norm':norm,'staff':staff,'state':st,'titles':tt,'kpis':kp,'scenarios':scens,'risk':risk,'ai_norm':ai,'hash':h,'excel':outx,'pdf':outp,'excel_v18':current_excel,'manager_excel':manager_excel,'boxed_manager_excel':boxed_manager_excel,'pdf_v18':current_pdf,'admin_reports':admin_reports,'veri_kalitesi_raporu':kalite_raporu,'version':'V19.21.28 Kutucuklu Personel Excel Raporu'}

# ============================================================================
# ENTERPRISE RESILIENCE WRAPPER
# Final public run_all definition: single-instance lock, preflight, structured
# logging, postflight verification and atomic runtime audit.
# ============================================================================

_run_all_v16_legacy = run_all
VERSION = "V19.21.2 Görünür AI Operasyon Maliyet"


def run_all():
    from runtime_resilience import (
        VERSION as _runtime_version,
        atomic_write_json,
        configure_logging,
        postflight_validate,
        preflight_validate,
        runtime_metadata,
        single_instance_lock,
    )

    logger = configure_logging(runtime_root())
    started = datetime.now()
    audit = {
        **runtime_metadata(),
        "status": "STARTED",
        "started_at": started.isoformat(timespec="seconds"),
        "stages": {},
    }
    audit_path = runtime_root() / "logs" / "BASDAS_Runtime_Audit.json"

    try:
        from common_veri_okuma import input_file
        source = input_file()
        with single_instance_lock(runtime_root()):
            t0 = datetime.now()
            preflight = preflight_validate(source)
            audit["stages"]["preflight"] = {
                "status": "SUCCESS",
                "duration_seconds": round((datetime.now() - t0).total_seconds(), 3),
                **preflight,
            }
            logger.info("Preflight başarılı: %s sayfa", preflight["sheet_count"])

            t1 = datetime.now()
            result = _run_all_v16_legacy()
            audit["stages"]["core_engine"] = {
                "status": "SUCCESS",
                "duration_seconds": round((datetime.now() - t1).total_seconds(), 3),
            }

            t2 = datetime.now()
            checks = postflight_validate(result)
            audit["stages"]["postflight"] = {
                "status": "SUCCESS",
                "duration_seconds": round((datetime.now() - t2).total_seconds(), 3),
                **checks,
            }
            result["version"] = _runtime_version
            result["runtime_audit"] = audit_path

        audit["status"] = "SUCCESS"
        audit["finished_at"] = datetime.now().isoformat(timespec="seconds")
        audit["duration_seconds"] = round((datetime.now() - started).total_seconds(), 3)
        atomic_write_json(audit_path, audit)
        logger.info("%s başarıyla tamamlandı (%.2f sn)", _runtime_version, audit["duration_seconds"])
        return result
    except Exception as exc:
        logger.exception("OMEHR kritik hata: %s", exc)
        audit["status"] = "FAILED"
        audit["error_type"] = type(exc).__name__
        audit["error"] = str(exc)
        audit["finished_at"] = datetime.now().isoformat(timespec="seconds")
        audit["duration_seconds"] = round((datetime.now() - started).total_seconds(), 3)
        atomic_write_json(audit_path, audit)
        raise
